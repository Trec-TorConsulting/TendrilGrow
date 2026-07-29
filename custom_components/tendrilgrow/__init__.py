"""The TendrilGrow integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store

from .ai.health_checks import AIHealthState, load_history, run_ai_health_check
from .const import (
    CONF_AI_HEALTH_INTERVAL_HOURS,
    DEFAULT_AI_HEALTH_INTERVAL_HOURS,
    DOMAIN,
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
ATTR_ENTRY_ID = "entry_id"
ATTR_REASON = "reason"
_SERVICES_REGISTERED_KEY = "_services_registered"


@dataclass(slots=True)
class RuntimeData:
    """Runtime data for one grow-space config entry."""

    grow_space: GrowSpace
    auto_mapped_sensor_roles: dict[str, str]
    ai_health_state: AIHealthState
    ai_history_store: Store[dict[str, Any]]
    unsubscribe_ai_scheduler: Any
    unsubscribe_update_listener: Any


class _EphemeralStore:
    """Fallback store used when HA storage backend is unavailable in tests."""

    def __init__(self) -> None:
        self._payload: dict[str, Any] = {}

    async def async_load(self) -> dict[str, Any]:
        return self._payload

    async def async_save(self, payload: dict[str, Any]) -> None:
        self._payload = dict(payload)


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

    runtime = RuntimeData(
        grow_space=grow_space,
        auto_mapped_sensor_roles={},
        ai_health_state=ai_state,
        ai_history_store=ai_store,
        unsubscribe_ai_scheduler=unsubscribe_ai_scheduler,
        unsubscribe_update_listener=unsubscribe,
    )
    hass.data[DOMAIN][entry.entry_id] = runtime
    entry.runtime_data = runtime

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Schedule the initial check as a proper coroutine job so HA runs it on the
    # event loop (a plain lambda is treated as an executor job where
    # async_create_task never awaits the coroutine).
    try:
        async_call_later(hass, 120, _async_startup_ai_check)
    except Exception:  # noqa: BLE001
        LOGGER.debug("Unable to schedule delayed startup AI check", exc_info=True)
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

    hass.services.async_register(
        DOMAIN, SERVICE_REBUILD_AUTOMAP, _async_handle_rebuild_automap
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RUN_AI_HEALTH_CHECK,
        _async_handle_run_ai_health_check,
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
