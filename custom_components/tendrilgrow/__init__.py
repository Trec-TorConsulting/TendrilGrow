"""The TendrilGrow integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store

from .ai.health_checks import AIHealthState, load_history, run_ai_health_check
from .const import (
    CONF_AI_HEALTH_INTERVAL_HOURS,
    CONF_AI_MODEL,
    CONF_AI_PROVIDER,
    CONF_TIMELAPSE_ENABLED,
    CONF_TIMELAPSE_INTERVAL_HOURS,
    DEFAULT_AI_HEALTH_INTERVAL_HOURS,
    DEFAULT_TIMELAPSE_ENABLED,
    DEFAULT_TIMELAPSE_INTERVAL_HOURS,
    DOMAIN,
    PROVIDER_NONE,
)
from .flush import (
    FlushState,
    async_check_flush_due,
    load_flush_state,
)
from .local_water_source import async_prepare_local_water_source
from .metric_bands import MetricBandRuntimeState, async_setup_metric_band_monitor
from .models.grow import GrowSpace
from .pump_energy import (
    PumpEnergyState,
    async_setup_pump_energy_tracking,
    load_pump_energy_state,
)
from .repairs import (
    async_clear_repair_issues,
    async_clear_timelapse_allowlist_issue,
    async_evaluate_repair_issues,
    async_raise_timelapse_allowlist_issue,
)
from .services import (
    _SERVICES_REGISTERED_KEY,
    ATTR_ACTION,
    ATTR_ENTRY_ID,
    ATTR_PUMP,
    ATTR_REASON,
    SERVICE_BUILD_TIMELAPSE,
    SERVICE_CAPTURE_TIMELAPSE_FRAME,
    SERVICE_MARK_FLUSH,
    SERVICE_REBUILD_AUTOMAP,
    SERVICE_RUN_AI_HEALTH_CHECK,
    SERVICE_SET_PUMP,
    _async_maybe_unregister_services,
    _async_register_services,
    _parse_mobile_action,
)
from .stage_migration import (
    _AI_ENTITY_IDS,
    _STAGE_CLOCK_ENTITY_IDS,
    _async_scan_lovelace_stage_clock_repairs,
    _migrate_ai_entity_ids,
    _migrate_stage_clock_entity_ids,
    _seed_stage_started_from_week_number,
    _stage_clock_lovelace_replacements,
    find_stale_stage_clock_references,
    rewrite_lovelace_stage_clock,
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
    "time",
    "text",
    "todo",
    "switch",
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

__all__ = [
    "ATTR_ACTION",
    "ATTR_ENTRY_ID",
    "ATTR_PUMP",
    "ATTR_REASON",
    "CONFIG_SCHEMA",
    "DOMAIN",
    "PLATFORMS",
    "RuntimeData",
    "SERVICE_BUILD_TIMELAPSE",
    "SERVICE_CAPTURE_TIMELAPSE_FRAME",
    "SERVICE_MARK_FLUSH",
    "SERVICE_REBUILD_AUTOMAP",
    "SERVICE_RUN_AI_HEALTH_CHECK",
    "SERVICE_SET_PUMP",
    "_AI_ENTITY_IDS",
    "_STAGE_CLOCK_ENTITY_IDS",
    "_EphemeralStore",
    "_SERVICES_REGISTERED_KEY",
    "_async_build_timelapse",
    "_async_capture_timelapse_frame",
    "_async_maybe_unregister_services",
    "_async_register_services",
    "_async_run_ai_health_check",
    "_async_scan_lovelace_stage_clock_repairs",
    "_entry_merged_config",
    "_migrate_ai_entity_ids",
    "_migrate_stage_clock_entity_ids",
    "_parse_mobile_action",
    "_seed_stage_started_from_week_number",
    "_stage_clock_lovelace_replacements",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
    "async_update_options",
    "er",
    "find_stale_stage_clock_references",
    "rewrite_lovelace_stage_clock",
]


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
    pump_energy_state: PumpEnergyState
    pump_energy_store: Any
    unsubscribe_pump_energy: list[Any]
    metric_band_state: MetricBandRuntimeState
    unsubscribe_metric_bands: list[Any]
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

    try:
        pump_energy_store: Any = Store(
            hass, 1, f"{DOMAIN}_pump_energy_{entry.entry_id}"
        )
        pump_energy_state = await load_pump_energy_state(pump_energy_store)
    except Exception:  # noqa: BLE001
        pump_energy_store = _EphemeralStore()
        pump_energy_state = PumpEnergyState()

    ai_provider = str(merged_config.get(CONF_AI_PROVIDER) or "").strip().lower()
    ai_model = str(merged_config.get(CONF_AI_MODEL) or "").strip()
    ai_enabled = bool(ai_provider and ai_provider != PROVIDER_NONE and ai_model)

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
    if ai_enabled:
        try:
            unsubscribe_ai_scheduler = async_track_time_interval(
                hass,
                _async_scheduled_ai_check,
                timedelta(hours=max(1, interval_hours)),
            )
        except Exception:  # noqa: BLE001
            LOGGER.debug("Unable to start AI health check scheduler", exc_info=True)

    async def _async_flush_tick(_now) -> None:
        await async_check_flush_due(hass, entry)

    try:
        unsubscribe_flush_ticker = async_track_time_interval(
            hass,
            _async_flush_tick,
            timedelta(hours=1),
        )
    except Exception:  # noqa: BLE001
        LOGGER.debug("Unable to start reservoir flush ticker", exc_info=True)
        unsubscribe_flush_ticker = None

    try:
        async_evaluate_repair_issues(hass, entry, merged_config, grow_space)
    except Exception:  # noqa: BLE001
        LOGGER.debug("Unable to evaluate repair issues on setup", exc_info=True)

    migrated_stage_started = _seed_stage_started_from_week_number(hass, entry)
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
        pump_energy_state=pump_energy_state,
        pump_energy_store=pump_energy_store,
        unsubscribe_pump_energy=[],
        metric_band_state=MetricBandRuntimeState(),
        unsubscribe_metric_bands=[],
        unsubscribe_timelapse_scheduler=None,
        timelapse_scheduler_paused=False,
        migrated_stage_started=migrated_stage_started,
    )
    if bool(merged_config.get(CONF_TIMELAPSE_ENABLED, DEFAULT_TIMELAPSE_ENABLED)):
        runtime.unsubscribe_timelapse_scheduler = _async_start_timelapse_scheduler(
            hass,
            entry,
            merged_config,
        )

    try:
        await async_prepare_local_water_source(
            hass,
            entry,
            grow_space,
            runtime.auto_mapped_sensor_roles,
        )
    except Exception:  # noqa: BLE001
        LOGGER.debug(
            "Local water source preparation failed for %s",
            entry.entry_id,
            exc_info=True,
        )

    hass.data[DOMAIN][entry.entry_id] = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    try:
        runtime.unsubscribe_pump_energy = await async_setup_pump_energy_tracking(
            hass,
            entry,
            runtime.pump_energy_state,
            runtime.pump_energy_store,
        )
    except Exception:  # noqa: BLE001
        LOGGER.debug(
            "Unable to start pump energy tracking for %s",
            entry.entry_id,
            exc_info=True,
        )
    try:
        runtime.unsubscribe_metric_bands = await async_setup_metric_band_monitor(
            hass, entry, runtime
        )
    except Exception:  # noqa: BLE001
        LOGGER.debug(
            "Unable to start metric band monitor for %s",
            entry.entry_id,
            exc_info=True,
        )
    _migrate_stage_clock_entity_ids(hass, entry)
    try:
        await _async_scan_lovelace_stage_clock_repairs(hass)
    except Exception:  # noqa: BLE001
        LOGGER.debug("Unable to scan Lovelace stage-clock repairs", exc_info=True)
    # Schedule the initial check as a proper coroutine job so HA runs it on the
    # event loop (a plain lambda is treated as an executor job where
    # async_create_task never awaits the coroutine).
    if ai_enabled:
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
    if unload_ok:
        runtime = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if runtime is not None:
            if getattr(runtime, "unsubscribe_ai_scheduler", None):
                runtime.unsubscribe_ai_scheduler()
            if getattr(runtime, "unsubscribe_update_listener", None):
                runtime.unsubscribe_update_listener()
            if getattr(runtime, "unsubscribe_flush_ticker", None):
                runtime.unsubscribe_flush_ticker()
            if getattr(runtime, "unsubscribe_pump_energy", None):
                for unsub in runtime.unsubscribe_pump_energy:
                    unsub()
            if getattr(runtime, "unsubscribe_metric_bands", None):
                for unsub in runtime.unsubscribe_metric_bands:
                    unsub()
            _async_stop_timelapse_scheduler(runtime)
    await _async_maybe_unregister_services(hass)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options updates."""
    await hass.config_entries.async_reload(entry.entry_id)


def _entry_merged_config(entry: ConfigEntry) -> dict[str, Any]:
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
