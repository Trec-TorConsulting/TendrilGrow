"""The TendrilGrow integration."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify

from .ai.health_checks import AIHealthState, load_history, run_ai_health_check
from .const import (
    CONF_AI_HEALTH_INTERVAL_HOURS,
    DEFAULT_AI_HEALTH_INTERVAL_HOURS,
    DOMAIN,
    PUMP_CONTROL_ROLES,
)
from .flush import (
    FlushState,
    async_check_flush_due,
    async_record_flush,
    load_flush_state,
)
from .models.grow import GrowSpace

LOGGER = logging.getLogger(__name__)
PLATFORMS: list[str] = [
    "sensor",
    "button",
    "binary_sensor",
    "number",
    "select",
    "text",
    "switch",
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
SERVICE_REBUILD_AUTOMAP = "rebuild_automap"
SERVICE_RUN_AI_HEALTH_CHECK = "run_ai_health_check"
SERVICE_SET_PUMP = "set_pump"
SERVICE_MARK_FLUSH = "mark_flush"
ATTR_ENTRY_ID = "entry_id"
ATTR_REASON = "reason"
ATTR_PUMP = "pump"
ATTR_ACTION = "action"
_SERVICES_REGISTERED_KEY = "_services_registered"

# Legacy AI health entities were created without a device, so Home Assistant
# generated global ids (e.g. sensor.ai_health_score, and _2 for a second entry).
# (domain, unique_id suffix, per-device object-id suffix == entity name slug).
_AI_ENTITY_IDS: tuple[tuple[str, str, str], ...] = (
    ("sensor", "ai_health_score", "ai_health_score"),
    ("sensor", "ai_health_summary", "ai_health_summary"),
    ("sensor", "ai_feeding_schedule", "ai_feeding_schedule"),
    ("sensor", "ai_health_last_check", "ai_last_health_check"),
    ("binary_sensor", "ai_health_critical_alert", "ai_health_critical_alert"),
    ("button", "run_ai_health_check", "run_ai_health_check"),
)


@dataclass(slots=True)
class RuntimeData:
    """Runtime data for one grow-space config entry."""

    grow_space: GrowSpace
    auto_mapped_sensor_roles: dict[str, str]
    ai_health_state: AIHealthState
    ai_history_store: Store[dict[str, Any]]
    unsubscribe_ai_scheduler: Any
    unsubscribe_update_listener: Any
    flush_state: FlushState
    flush_store: Any
    unsubscribe_flush_ticker: Any


class _EphemeralStore:
    """Fallback store used when HA storage backend is unavailable in tests."""

    def __init__(self) -> None:
        self._payload: dict[str, Any] = {}

    async def async_load(self) -> dict[str, Any]:
        return self._payload

    async def async_save(self, payload: dict[str, Any]) -> None:
        self._payload = dict(payload)


def _migrate_ai_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Rename legacy generic AI entity ids to per-grow-space ids.

    Now that the AI health entities are attached to the grow-space device, an
    auto-generated global id such as ``sensor.ai_health_score`` (or ``_2`` for a
    second entry) is migrated to ``<domain>.<grow_slug>_<name>``. Ids the user
    has customized are left untouched, and an already-migrated id is a no-op.
    """
    slug = slugify(getattr(entry, "title", "") or "")
    if not slug:
        return
    try:
        registry = er.async_get(hass)
    except Exception:  # noqa: BLE001
        return

    for domain, uid_suffix, obj_suffix in _AI_ENTITY_IDS:
        unique_id = f"{entry.entry_id}_{uid_suffix}"
        current = registry.async_get_entity_id(domain, DOMAIN, unique_id)
        if not current:
            continue
        desired = f"{domain}.{slug}_{obj_suffix}"
        if current == desired:
            continue
        current_object = current.split(".", 1)[1]
        # Only migrate auto-generated ids ("<name>" or "<name>_<n>").
        if current_object != obj_suffix and not re.fullmatch(
            rf"{re.escape(obj_suffix)}_\d+", current_object
        ):
            continue
        if registry.async_get(desired) is not None:
            continue
        try:
            registry.async_update_entity(current, new_entity_id=desired)
            LOGGER.info(
                "Migrated AI entity %s -> %s for %s",
                current,
                desired,
                entry.entry_id,
            )
        except (ValueError, KeyError):
            LOGGER.debug(
                "Could not migrate %s -> %s", current, desired, exc_info=True
            )


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up from yaml (unused)."""
    _ = config
    hass.data.setdefault(DOMAIN, {})
    await _async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TendrilGrow from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    await _async_register_services(hass)

    merged_config = dict(entry.data)
    merged_config.update(getattr(entry, "options", {}))
    grow_space = GrowSpace.from_dict(merged_config)
    unsubscribe = entry.add_update_listener(async_update_options)
    try:
        ai_store: Any = Store(hass, 1, f"{DOMAIN}_ai_history_{entry.entry_id}")
        ai_history = await load_history(ai_store)
    except Exception:  # noqa: BLE001
        ai_store = _EphemeralStore()
        ai_history = []
    ai_state = AIHealthState(
        latest=ai_history[-1] if ai_history else None, history=ai_history
    )

    try:
        flush_store: Any = Store(hass, 1, f"{DOMAIN}_flush_{entry.entry_id}")
        flush_state = await load_flush_state(flush_store)
    except Exception:  # noqa: BLE001
        flush_store = _EphemeralStore()
        flush_state = FlushState()

    interval_hours = int(
        merged_config.get(
            CONF_AI_HEALTH_INTERVAL_HOURS, DEFAULT_AI_HEALTH_INTERVAL_HOURS
        )
        or DEFAULT_AI_HEALTH_INTERVAL_HOURS
    )

    async def _async_scheduled_ai_check(_now) -> None:
        await _async_run_ai_health_check(hass, entry, reason="scheduled")

    async def _async_startup_ai_check(_now) -> None:
        await _async_run_ai_health_check(hass, entry, reason="startup_delayed")

    unsubscribe_ai_scheduler = None
    try:
        unsubscribe_ai_scheduler = async_track_time_interval(
            hass,
            _async_scheduled_ai_check,
            timedelta(hours=max(1, interval_hours)),
        )
    except Exception:  # noqa: BLE001
        unsubscribe_ai_scheduler = None

    async def _async_flush_tick(_now) -> None:
        rt = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if rt is not None:
            await async_check_flush_due(hass, entry, rt)

    unsubscribe_flush_ticker = None
    try:
        unsubscribe_flush_ticker = async_track_time_interval(
            hass, _async_flush_tick, timedelta(hours=1)
        )
    except Exception:  # noqa: BLE001
        unsubscribe_flush_ticker = None

    runtime = RuntimeData(
        grow_space=grow_space,
        auto_mapped_sensor_roles={},
        ai_health_state=ai_state,
        ai_history_store=ai_store,
        unsubscribe_ai_scheduler=unsubscribe_ai_scheduler,
        unsubscribe_update_listener=unsubscribe,
        flush_state=flush_state,
        flush_store=flush_store,
        unsubscribe_flush_ticker=unsubscribe_flush_ticker,
    )
    hass.data[DOMAIN][entry.entry_id] = runtime
    entry.runtime_data = runtime

    _migrate_ai_entity_ids(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Schedule the initial check as a proper coroutine job so HA runs it on the
    # event loop (a plain lambda is treated as an executor job where
    # async_create_task never awaits the coroutine).
    try:
        async_call_later(hass, 120, _async_startup_ai_check)
    except Exception:  # noqa: BLE001
        LOGGER.debug("Unable to schedule delayed startup AI check", exc_info=True)
    try:
        async_call_later(hass, 150, _async_flush_tick)
    except Exception:  # noqa: BLE001
        LOGGER.debug("Unable to schedule delayed flush check", exc_info=True)
    LOGGER.info("Configured grow space entry '%s' (%s)", entry.title, entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    runtime = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if runtime and runtime.unsubscribe_update_listener:
        runtime.unsubscribe_update_listener()
    unsubscribe_ai_scheduler = (
        getattr(runtime, "unsubscribe_ai_scheduler", None) if runtime else None
    )
    if unsubscribe_ai_scheduler:
        unsubscribe_ai_scheduler()
    unsubscribe_flush_ticker = (
        getattr(runtime, "unsubscribe_flush_ticker", None) if runtime else None
    )
    if unsubscribe_flush_ticker:
        unsubscribe_flush_ticker()
    await _async_maybe_unregister_services(hass)
    LOGGER.info("Unloaded grow space entry '%s' (%s)", entry.title, entry.entry_id)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading only the changed entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_services(hass: HomeAssistant) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_SERVICES_REGISTERED_KEY):
        return
    if not hasattr(hass, "services"):
        return

    async def _async_handle_rebuild_automap(call: ServiceCall) -> None:
        requested_entry_id = str(call.data.get(ATTR_ENTRY_ID, "")).strip()
        loaded_entries = [
            entry_id
            for entry_id in hass.data.get(DOMAIN, {})
            if not str(entry_id).startswith("_")
        ]

        if requested_entry_id:
            if requested_entry_id not in loaded_entries:
                raise HomeAssistantError(
                    f"TendrilGrow entry not loaded: {requested_entry_id}"
                )
            target_entries = [requested_entry_id]
        else:
            target_entries = loaded_entries

        for entry_id in target_entries:
            await hass.config_entries.async_reload(entry_id)

        LOGGER.info(
            "Rebuilt TendrilGrow auto-mapping for %d entr%s",
            len(target_entries),
            "y" if len(target_entries) == 1 else "ies",
        )

    async def _async_handle_run_ai_health_check(call: ServiceCall) -> None:
        requested_entry_id = str(call.data.get(ATTR_ENTRY_ID, "")).strip()
        reason = str(call.data.get(ATTR_REASON, "manual")).strip() or "manual"
        loaded_entries = [
            entry_id
            for entry_id in hass.data.get(DOMAIN, {})
            if not str(entry_id).startswith("_")
        ]

        if requested_entry_id:
            if requested_entry_id not in loaded_entries:
                raise HomeAssistantError(
                    f"TendrilGrow entry not loaded: {requested_entry_id}"
                )
            target_entries = [requested_entry_id]
        else:
            target_entries = loaded_entries

        for entry_id in target_entries:
            entry = None
            if hasattr(hass.config_entries, "async_get_entry"):
                entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None:
                entry = next(
                    (
                        loaded
                        for loaded in getattr(
                            hass.config_entries, "async_entries", lambda _domain: []
                        )(DOMAIN)
                        if loaded.entry_id == entry_id
                    ),
                    None,
                )
            if entry is None:
                continue
            await _async_run_ai_health_check(hass, entry, reason=reason)

        LOGGER.info(
            "Ran TendrilGrow AI health checks for %d entr%s",
            len(target_entries),
            "y" if len(target_entries) == 1 else "ies",
        )

    async def _async_handle_set_pump(call: ServiceCall) -> None:
        entry_id = str(call.data.get(ATTR_ENTRY_ID, "")).strip()
        pump = str(call.data.get(ATTR_PUMP, "")).strip()
        action = str(call.data.get(ATTR_ACTION, "")).strip().lower()

        if not entry_id:
            raise HomeAssistantError("entry_id is required")
        if not pump:
            raise HomeAssistantError("pump is required")
        if action not in ("on", "off", "toggle"):
            raise HomeAssistantError(
                f"action must be 'on', 'off', or 'toggle', got '{action}'"
            )

        loaded_entries = [
            entry_id_item
            for entry_id_item in hass.data.get(DOMAIN, {})
            if not str(entry_id_item).startswith("_")
        ]

        if entry_id not in loaded_entries:
            raise HomeAssistantError(f"TendrilGrow entry not loaded: {entry_id}")

        runtime = hass.data.get(DOMAIN, {}).get(entry_id)
        if runtime is None:
            raise HomeAssistantError(f"TendrilGrow entry not loaded: {entry_id}")

        if pump not in PUMP_CONTROL_ROLES:
            raise HomeAssistantError(
                f"pump must be one of {PUMP_CONTROL_ROLES}, got '{pump}'"
            )

        grow_space = runtime.grow_space
        mapped_entity_id = grow_space.control_mappings.get(pump)

        if not mapped_entity_id:
            LOGGER.warning(
                "Skipping set_pump for entry %s pump %s: pump role not mapped",
                entry_id,
                pump,
            )
            return

        state = hass.states.get(mapped_entity_id)
        if state is None:
            LOGGER.warning(
                "Skipping set_pump for entry %s pump %s: entity %s not found",
                entry_id,
                pump,
                mapped_entity_id,
            )
            return

        if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            LOGGER.warning(
                "Skipping set_pump for entry %s pump %s: entity %s is %s",
                entry_id,
                pump,
                mapped_entity_id,
                state.state,
            )
            return

        # Determine the domain and action
        domain = mapped_entity_id.split(".")[0]
        action_name = action if action == "toggle" else f"turn_{action}"

        if domain not in ("switch", "input_boolean"):
            LOGGER.warning(
                "Skipping set_pump for entry %s pump %s: unsupported domain %s",
                entry_id,
                pump,
                domain,
            )
            return

        try:
            await hass.services.async_call(
                domain,
                action_name,
                {"entity_id": mapped_entity_id},
            )
            LOGGER.info(
                "Set pump %s (%s) to %s for entry %s",
                pump,
                mapped_entity_id,
                action,
                entry_id,
            )
        except Exception as err:  # noqa: BLE001
            LOGGER.error(
                "Failed to set pump %s (%s) to %s for entry %s: %s",
                pump,
                mapped_entity_id,
                action,
                entry_id,
                err,
            )
            raise HomeAssistantError(
                f"Failed to set pump {pump} ({mapped_entity_id}) to {action}: {err}"
            ) from err

    async def _async_handle_mark_flush(call: ServiceCall) -> None:
        entry_id = str(call.data.get(ATTR_ENTRY_ID, "")).strip()
        if not entry_id:
            raise HomeAssistantError("entry_id is required")

        runtime = hass.data.get(DOMAIN, {}).get(entry_id)
        if runtime is None or str(entry_id).startswith("_"):
            raise HomeAssistantError(f"TendrilGrow entry not loaded: {entry_id}")

        entry = None
        if hasattr(hass.config_entries, "async_get_entry"):
            entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            entry = next(
                (
                    loaded
                    for loaded in getattr(
                        hass.config_entries, "async_entries", lambda _domain: []
                    )(DOMAIN)
                    if loaded.entry_id == entry_id
                ),
                None,
            )
        if entry is None:
            raise HomeAssistantError(f"TendrilGrow entry not found: {entry_id}")

        await async_record_flush(hass, entry, runtime)
        LOGGER.info("Recorded reservoir flush via service for entry %s", entry_id)

    hass.services.async_register(
        DOMAIN, SERVICE_REBUILD_AUTOMAP, _async_handle_rebuild_automap
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RUN_AI_HEALTH_CHECK,
        _async_handle_run_ai_health_check,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PUMP,
        _async_handle_set_pump,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MARK_FLUSH,
        _async_handle_mark_flush,
    )
    domain_data[_SERVICES_REGISTERED_KEY] = True


async def _async_maybe_unregister_services(hass: HomeAssistant) -> None:
    if not hasattr(hass, "services"):
        return

    domain_data = hass.data.get(DOMAIN, {})
    if not domain_data.get(_SERVICES_REGISTERED_KEY):
        return

    has_loaded_entries = any(not str(key).startswith("_") for key in domain_data)
    if has_loaded_entries:
        return

    hass.services.async_remove(DOMAIN, SERVICE_REBUILD_AUTOMAP)
    hass.services.async_remove(DOMAIN, SERVICE_RUN_AI_HEALTH_CHECK)
    hass.services.async_remove(DOMAIN, SERVICE_SET_PUMP)
    hass.services.async_remove(DOMAIN, SERVICE_MARK_FLUSH)
    domain_data[_SERVICES_REGISTERED_KEY] = False


async def _async_run_ai_health_check(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    reason: str,
) -> None:
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if runtime is None:
        return

    try:
        result = await run_ai_health_check(
            hass,
            entry,
            runtime.grow_space,
            runtime.ai_health_state,
            runtime.ai_history_store,
            reason=reason,
        )
        LOGGER.info(
            "AI health check complete for %s (%s): score=%s severity=%s",
            entry.title,
            entry.entry_id,
            result.score,
            result.severity,
        )
    except Exception as err:  # noqa: BLE001
        runtime.ai_health_state.last_error = str(err)
        LOGGER.warning(
            "AI health check failed for %s (%s): %s",
            entry.title,
            entry.entry_id,
            err,
        )
