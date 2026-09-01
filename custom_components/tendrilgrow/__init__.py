"""The TendrilGrow integration."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .ai.health_checks import AIHealthState, load_history, run_ai_health_check
from .const import (
    CONF_AI_HEALTH_INTERVAL_HOURS,
    CONF_TIMELAPSE_ENABLED,
    CONF_TIMELAPSE_INTERVAL_HOURS,
    CTX_STAGE_STARTED,
    CTX_WEEK_IN_STAGE,
    DEFAULT_AI_HEALTH_INTERVAL_HOURS,
    DEFAULT_TIMELAPSE_ENABLED,
    DEFAULT_TIMELAPSE_INTERVAL_HOURS,
    DOMAIN,
    PUMP_CONTROL_ROLES,
)
from .entity import grow_object_id_prefix, prefix_from_entity_id
from .flush import (
    FlushState,
    async_check_flush_due,
    async_record_flush,
    load_flush_state,
)
from .local_water_source import async_prepare_local_water_source
from .models.grow import GrowSpace
from .repairs import (
    async_clear_repair_issues,
    async_clear_timelapse_allowlist_issue,
    async_evaluate_repair_issues,
    async_raise_timelapse_allowlist_issue,
)
from .timelapse import async_build_timelapse_video, async_capture_frame

LOGGER = logging.getLogger(__name__)
PLATFORMS: list[str] = [
    "sensor",
    "button",
    "binary_sensor",
    "calendar",
    "number",
    "select",
    "date",
    "text",
    "todo",
    "switch",
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
SERVICE_REBUILD_AUTOMAP = "rebuild_automap"
SERVICE_RUN_AI_HEALTH_CHECK = "run_ai_health_check"
SERVICE_SET_PUMP = "set_pump"
SERVICE_MARK_FLUSH = "mark_flush"
SERVICE_CAPTURE_TIMELAPSE_FRAME = "capture_timelapse_frame"
SERVICE_BUILD_TIMELAPSE = "build_timelapse"
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
    unsubscribe_timelapse_scheduler: Any
    timelapse_scheduler_paused: bool
    migrated_stage_started: date | None = None
    grow_object_prefix: str | None = None
    legacy_week_entity_id: str | None = None


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
            LOGGER.debug("Could not migrate %s -> %s", current, desired, exc_info=True)


def _seed_stage_started_from_week_number(
    hass: HomeAssistant, entry: ConfigEntry
) -> date | None:
    """Backdate Stage Started from the retired Week In Stage number.

    Week 2 becomes about 14 days ago. The leftover number entity is removed
    so it does not linger unavailable after the date entity takes over.
    """
    try:
        registry = er.async_get(hass)
    except Exception:  # noqa: BLE001
        return None
    week_id = registry.async_get_entity_id(
        "number", DOMAIN, f"{entry.entry_id}_{CTX_WEEK_IN_STAGE}"
    )
    if not week_id:
        return None
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    prefix = prefix_from_entity_id(week_id, "week_in_stage")
    if runtime is not None:
        runtime.legacy_week_entity_id = week_id
        if prefix:
            runtime.grow_object_prefix = prefix
    week_state = None
    current = hass.states.get(week_id)
    if current is not None and current.state not in (
        None,
        "",
        STATE_UNKNOWN,
        STATE_UNAVAILABLE,
    ):
        week_state = current.state
    if week_state is None:
        try:
            from homeassistant.helpers.restore_state import (
                async_get as async_get_restore,
            )

            stored = async_get_restore(hass).last_states.get(week_id)
            if stored is not None and stored.state.state not in (
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
                "",
            ):
                week_state = stored.state.state
        except Exception:  # noqa: BLE001
            week_state = None
    try:
        registry.async_remove(week_id)
    except Exception:  # noqa: BLE001
        LOGGER.debug("Could not remove legacy week-in-stage number %s", week_id)
    if week_state is None:
        return None
    try:
        weeks = float(week_state)
    except (TypeError, ValueError):
        return None
    return dt_util.now().date() - timedelta(days=max(0, int(round(weeks * 7))))


_STAGE_CLOCK_ENTITY_IDS: tuple[tuple[str, str, str], ...] = (
    ("date", CTX_STAGE_STARTED, "stage_started"),
    ("sensor", CTX_WEEK_IN_STAGE, "week_in_stage"),
)

_LOVELACE_STAGE_CLOCK_SCHEDULED = "_lovelace_stage_clock_scheduled"


def _migrate_stage_clock_entity_ids(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, str]:
    """Rename Stage Started / Week In Stage ids to match Cultivation Plan cards.

    First-load ids are often ``date.stage_started`` / ``date.stage_started_2``
    because the device is not attached yet. Dashboards use
    ``date.<grow_prefix>_stage_started`` like the Growth Stage select.
    """
    renamed: dict[str, str] = {}
    prefix = grow_object_id_prefix(hass, entry)
    if not prefix:
        return renamed
    try:
        registry = er.async_get(hass)
    except Exception:  # noqa: BLE001
        return renamed

    for domain, uid_suffix, obj_suffix in _STAGE_CLOCK_ENTITY_IDS:
        unique_id = f"{entry.entry_id}_{uid_suffix}"
        current = registry.async_get_entity_id(domain, DOMAIN, unique_id)
        if not current:
            continue
        desired = f"{domain}.{prefix}_{obj_suffix}"
        renamed[current] = desired
        if current == desired:
            continue
        current_object = current.split(".", 1)[1]
        generic = current_object == obj_suffix or bool(
            re.fullmatch(rf"{re.escape(obj_suffix)}_\d+", current_object)
        )
        device_prefixed = current_object.endswith(f"_{obj_suffix}")
        if not generic and not device_prefixed:
            continue
        if registry.async_get(desired) is not None:
            continue
        try:
            registry.async_update_entity(current, new_entity_id=desired)
            LOGGER.info(
                "Migrated stage-clock entity %s -> %s for %s",
                current,
                desired,
                entry.entry_id,
            )
        except (ValueError, KeyError):
            LOGGER.debug("Could not migrate %s -> %s", current, desired, exc_info=True)
    return renamed


def rewrite_lovelace_stage_clock(
    config: Any,
    list_replacements: dict[str, list[str]],
    string_replacements: dict[str, str],
) -> tuple[Any, bool]:
    """Swap retired week-in-stage number ids for Stage Started + Week In Stage."""
    ordered_strings = sorted(string_replacements, key=len, reverse=True)

    def _swap_text(value: str) -> tuple[str, bool]:
        updated = value
        for old in ordered_strings:
            updated = updated.replace(old, string_replacements[old])
        return updated, updated != value

    def _entity_id_of(item: Any) -> str | None:
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            entity = item.get("entity")
            if isinstance(entity, str):
                return entity
        return None

    def _walk(value: Any) -> tuple[Any, bool]:
        if isinstance(value, dict):
            changed = False
            out: dict[Any, Any] = {}
            for key, child in value.items():
                if key == "entities" and isinstance(child, list):
                    rewritten, child_changed = _rewrite_entities(child)
                else:
                    rewritten, child_changed = _walk(child)
                out[key] = rewritten
                changed = changed or child_changed
            return out, changed
        if isinstance(value, list):
            changed = False
            out_list = []
            for child in value:
                rewritten, child_changed = _walk(child)
                out_list.append(rewritten)
                changed = changed or child_changed
            return out_list, changed
        if isinstance(value, str):
            return _swap_text(value)
        return value, False

    def _rewrite_entities(rows: list[Any]) -> tuple[list[Any], bool]:
        present: set[str] = set()
        for item in rows:
            eid = _entity_id_of(item)
            if eid:
                present.add(eid)
        out: list[Any] = []
        changed = False
        for item in rows:
            eid = _entity_id_of(item)
            replacements = list_replacements.get(eid or "")
            if replacements:
                changed = True
                for new_id in replacements:
                    if new_id in present:
                        continue
                    out.append(new_id)
                    present.add(new_id)
                continue
            rewritten, child_changed = _walk(item)
            new_eid = _entity_id_of(rewritten)
            if new_eid and new_eid in present and new_eid != eid:
                changed = True
                continue
            out.append(rewritten)
            changed = changed or child_changed
        return out, changed

    return _walk(config)


def _stage_clock_lovelace_replacements(
    hass: HomeAssistant,
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Map retired/guessed Cultivation Plan ids to the live registry ids."""
    list_replacements: dict[str, list[str]] = {}
    string_replacements: dict[str, str] = {}
    try:
        registry = er.async_get(hass)
        entries = hass.config_entries.async_entries(DOMAIN)
    except Exception:  # noqa: BLE001
        return list_replacements, string_replacements

    for entry in entries:
        prefix = grow_object_id_prefix(hass, entry)
        date_id = registry.async_get_entity_id(
            "date", DOMAIN, f"{entry.entry_id}_{CTX_STAGE_STARTED}"
        )
        sensor_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{CTX_WEEK_IN_STAGE}"
        )
        runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        legacy = getattr(runtime, "legacy_week_entity_id", None)
        old_number = legacy or (f"number.{prefix}_week_in_stage" if prefix else None)
        replacements = [eid for eid in (date_id, sensor_id) if eid]
        if old_number and replacements:
            list_replacements[old_number] = replacements
            string_replacements[old_number] = sensor_id or date_id or old_number
        if prefix and date_id:
            guessed = f"date.{prefix}_stage_started"
            if guessed != date_id:
                string_replacements[guessed] = date_id
                list_replacements[guessed] = [date_id]
        if prefix and sensor_id:
            guessed = f"sensor.{prefix}_week_in_stage"
            if guessed != sensor_id:
                string_replacements[guessed] = sensor_id
                list_replacements[guessed] = [sensor_id]
    return list_replacements, string_replacements


async def _async_migrate_lovelace_stage_clock(hass: HomeAssistant) -> None:
    """Rewrite storage-mode dashboards that still reference deleted number ids."""
    lovelace = hass.data.get("lovelace")
    dashboards = getattr(lovelace, "dashboards", None)
    if dashboards is None and isinstance(lovelace, dict):
        dashboards = lovelace.get("dashboards")
    if not isinstance(dashboards, dict) or not dashboards:
        return
    list_replacements, string_replacements = _stage_clock_lovelace_replacements(hass)
    if not list_replacements and not string_replacements:
        return
    for url_path, dash in dashboards.items():
        if (
            dash is None
            or not hasattr(dash, "async_load")
            or not hasattr(dash, "async_save")
        ):
            continue
        try:
            config = await dash.async_load(False)
        except Exception:  # noqa: BLE001
            LOGGER.debug(
                "Could not load Lovelace dashboard %s", url_path, exc_info=True
            )
            continue
        new_config, changed = rewrite_lovelace_stage_clock(
            config, list_replacements, string_replacements
        )
        if not changed:
            continue
        try:
            await dash.async_save(new_config)
            LOGGER.info(
                "Updated Cultivation Plan entities on Lovelace dashboard %s",
                url_path,
            )
        except Exception:  # noqa: BLE001
            LOGGER.debug(
                "Could not save Lovelace dashboard %s", url_path, exc_info=True
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
        unsubscribe_timelapse_scheduler=None,
        timelapse_scheduler_paused=False,
    )
    hass.data[DOMAIN][entry.entry_id] = runtime
    entry.runtime_data = runtime

    # Prefer LocalTuya / Tuya Local: bind + auto-map before platforms load.
    try:
        await async_prepare_local_water_source(
            hass,
            entry,
            grow_space,
            runtime.auto_mapped_sensor_roles,
        )
    except Exception:  # noqa: BLE001
        LOGGER.debug(
            "Unable to prepare local water source for %s",
            entry.entry_id,
            exc_info=True,
        )

    if bool(merged_config.get(CONF_TIMELAPSE_ENABLED, DEFAULT_TIMELAPSE_ENABLED)):
        runtime.unsubscribe_timelapse_scheduler = _async_start_timelapse_scheduler(
            hass,
            entry,
            merged_config,
        )

    _migrate_ai_entity_ids(hass, entry)
    runtime.migrated_stage_started = _seed_stage_started_from_week_number(hass, entry)
    try:
        async_evaluate_repair_issues(hass, entry, merged_config, grow_space)
    except Exception:  # noqa: BLE001
        LOGGER.debug("Unable to evaluate repair issues", exc_info=True)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _migrate_stage_clock_entity_ids(hass, entry)
    try:
        if not hass.data[DOMAIN].get(_LOVELACE_STAGE_CLOCK_SCHEDULED):
            hass.data[DOMAIN][_LOVELACE_STAGE_CLOCK_SCHEDULED] = True

            async def _async_lovelace_stage_clock(_now) -> None:
                await _async_migrate_lovelace_stage_clock(hass)

            async_call_later(hass, 15, _async_lovelace_stage_clock)
    except Exception:  # noqa: BLE001
        LOGGER.debug("Unable to schedule Lovelace stage-clock migration", exc_info=True)
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
    try:
        async_clear_repair_issues(hass, entry)
    except Exception:  # noqa: BLE001
        LOGGER.debug("Unable to clear repair issues", exc_info=True)
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
    unsubscribe_timelapse_scheduler = (
        getattr(runtime, "unsubscribe_timelapse_scheduler", None) if runtime else None
    )
    if unsubscribe_timelapse_scheduler:
        unsubscribe_timelapse_scheduler()
    await _async_maybe_unregister_services(hass)
    LOGGER.info("Unloaded grow space entry '%s' (%s)", entry.title, entry.entry_id)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading only the changed entry."""
    await hass.config_entries.async_reload(entry.entry_id)


def _entry_merged_config(entry: ConfigEntry) -> dict[str, Any]:
    """Return merged entry config with options overriding data."""
    merged_config = dict(entry.data)
    merged_config.update(getattr(entry, "options", {}))
    return merged_config


def _async_stop_timelapse_scheduler(runtime: RuntimeData) -> None:
    unsubscribe = getattr(runtime, "unsubscribe_timelapse_scheduler", None)
    if unsubscribe:
        unsubscribe()
    runtime.unsubscribe_timelapse_scheduler = None


def _async_start_timelapse_scheduler(
    hass: HomeAssistant,
    entry: ConfigEntry,
    merged_config: dict[str, Any],
):
    """Start periodic timelapse capture for one entry when enabled."""
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if runtime is None or runtime.timelapse_scheduler_paused:
        return None

    interval_hours = int(
        merged_config.get(
            CONF_TIMELAPSE_INTERVAL_HOURS,
            DEFAULT_TIMELAPSE_INTERVAL_HOURS,
        )
        or DEFAULT_TIMELAPSE_INTERVAL_HOURS
    )

    async def _async_timelapse_tick(_now) -> None:
        await _async_capture_timelapse_frame(hass, entry, reason="scheduled")

    try:
        return async_track_time_interval(
            hass,
            _async_timelapse_tick,
            timedelta(hours=max(1, interval_hours)),
        )
    except Exception:  # noqa: BLE001
        LOGGER.debug("Unable to start timelapse scheduler", exc_info=True)
        return None


async def _async_capture_timelapse_frame(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    reason: str,
) -> bool:
    """Capture one timelapse frame and manage allow-list repairs/scheduler state."""
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if runtime is None:
        return False

    merged_config = _entry_merged_config(entry)
    enabled = bool(merged_config.get(CONF_TIMELAPSE_ENABLED, DEFAULT_TIMELAPSE_ENABLED))
    if reason == "scheduled" and not enabled:
        return False

    result = await async_capture_frame(hass, entry, runtime.grow_space, merged_config)
    if result.success:
        if runtime.timelapse_scheduler_paused:
            runtime.timelapse_scheduler_paused = False
            async_clear_timelapse_allowlist_issue(hass, entry)
        else:
            async_clear_timelapse_allowlist_issue(hass, entry)

        if (
            enabled
            and runtime.unsubscribe_timelapse_scheduler is None
            and not runtime.timelapse_scheduler_paused
        ):
            runtime.unsubscribe_timelapse_scheduler = _async_start_timelapse_scheduler(
                hass,
                entry,
                merged_config,
            )
        LOGGER.debug(
            "Timelapse capture succeeded for %s via %s",
            entry.entry_id,
            reason,
        )
        return True

    if result.allowlist_error:
        runtime.timelapse_scheduler_paused = True
        _async_stop_timelapse_scheduler(runtime)
        async_raise_timelapse_allowlist_issue(hass, entry, str(result.capture_dir))
        LOGGER.warning(
            "Timelapse capture paused for %s: add %s to allowlist_external_dirs (%s)",
            entry.entry_id,
            result.capture_dir,
            result.error,
        )
        return False

    LOGGER.warning(
        "Timelapse capture failed for %s (%s): %s",
        entry.entry_id,
        reason,
        result.error,
    )
    return False


async def _async_build_timelapse(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Build a timelapse video for one entry if possible."""
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if runtime is None:
        return
    merged_config = _entry_merged_config(entry)
    await async_build_timelapse_video(hass, entry, runtime.grow_space, merged_config)


def _parse_mobile_action(action: str) -> tuple[str, str] | None:
    """Parse a TendrilGrow mobile-notification action into (verb, entry_id)."""
    prefix = "TENDRILGROW_"
    if not action.startswith(prefix) or ":" not in action:
        return None
    verb, entry_id = action[len(prefix) :].split(":", 1)
    if not verb or not entry_id:
        return None
    return verb, entry_id


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

    async def _async_handle_capture_timelapse_frame(call: ServiceCall) -> None:
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
            await _async_capture_timelapse_frame(
                hass,
                entry,
                reason="manual_service",
            )

    async def _async_handle_build_timelapse(call: ServiceCall) -> None:
        entry_id = str(call.data.get(ATTR_ENTRY_ID, "")).strip()
        if not entry_id:
            raise HomeAssistantError("entry_id is required")

        if entry_id not in hass.data.get(DOMAIN, {}):
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

        await _async_build_timelapse(hass, entry)

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
    hass.services.async_register(
        DOMAIN,
        SERVICE_CAPTURE_TIMELAPSE_FRAME,
        _async_handle_capture_timelapse_frame,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_BUILD_TIMELAPSE,
        _async_handle_build_timelapse,
    )

    async def _async_handle_mobile_action(event: Any) -> None:
        parsed = _parse_mobile_action(str(event.data.get("action", "")))
        if parsed is None:
            return
        verb, entry_id = parsed
        if verb == "MARK_FLUSH":
            await hass.services.async_call(
                DOMAIN, SERVICE_MARK_FLUSH, {ATTR_ENTRY_ID: entry_id}, blocking=False
            )
        elif verb == "RUN_CHECK":
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RUN_AI_HEALTH_CHECK,
                {ATTR_ENTRY_ID: entry_id},
                blocking=False,
            )

    try:
        domain_data["_mobile_action_unsub"] = hass.bus.async_listen(
            "mobile_app_notification_action", _async_handle_mobile_action
        )
    except Exception:  # noqa: BLE001
        LOGGER.debug("Unable to register mobile action listener", exc_info=True)

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
    hass.services.async_remove(DOMAIN, SERVICE_CAPTURE_TIMELAPSE_FRAME)
    hass.services.async_remove(DOMAIN, SERVICE_BUILD_TIMELAPSE)
    unsub = domain_data.pop("_mobile_action_unsub", None)
    if unsub:
        try:
            unsub()
        except Exception:  # noqa: BLE001
            LOGGER.debug("Unable to remove mobile action listener", exc_info=True)
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
