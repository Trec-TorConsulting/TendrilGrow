"""Metric band evaluation and notify-only alerts."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import async_get as get_entity_registry
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AI_NOTIFY_SERVICE,
    DOMAIN,
    SENSOR_ROLE_EC,
    SENSOR_ROLE_PH,
)
from .entry_config import entry_merged_config
from .grow_targets import current_stage, read_band_bounds, stage_has_reservoir_band

LOGGER = logging.getLogger(__name__)

METRIC_PH = "ph"
METRIC_EC = "ec"
METRIC_VPD = "vpd"
METRICS: tuple[str, ...] = (METRIC_PH, METRIC_EC, METRIC_VPD)

DEFAULT_BAND_COOLDOWN_HOURS = 6


def metric_band_dispatcher_signal(entry_id: str) -> str:
    return f"{DOMAIN}_metric_band_update_{entry_id}"


def metric_band_notification_id(entry_id: str, metric: str) -> str:
    return f"{DOMAIN}_metric_band_{metric}_{entry_id}"


@dataclass(slots=True)
class MetricBandRuntimeState:
    """Per-entry band breach tracking for edge notify and binary sensors."""

    out_of_range: dict[str, bool] = field(default_factory=dict)
    source_available: dict[str, bool] = field(default_factory=dict)
    has_band: dict[str, bool] = field(default_factory=dict)
    last_notify_at: dict[str, datetime] = field(default_factory=dict)


def _entry_notify_service(entry: ConfigEntry) -> str:
    merged = entry_merged_config(entry)
    return str(merged.get(CONF_AI_NOTIFY_SERVICE, "") or "").strip()


def _vpd_entity_id(hass: HomeAssistant, entry: ConfigEntry) -> str | None:
    registry = get_entity_registry(hass)
    return registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_vpd")


def _metric_source_entity_id(
    hass: HomeAssistant, entry: ConfigEntry, grow_space: Any, metric: str
) -> str | None:
    if metric == METRIC_VPD:
        return _vpd_entity_id(hass, entry)
    role = SENSOR_ROLE_PH if metric == METRIC_PH else SENSOR_ROLE_EC
    return grow_space.sensor_mappings.get(role)


def _read_metric_value(hass: HomeAssistant, entity_id: str | None) -> float | None:
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state in ("unknown", "unavailable", ""):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _is_out_of_range(value: float, low: float, high: float) -> bool:
    return value < low or value > high


async def _notify_band_breach(
    hass: HomeAssistant,
    entry: ConfigEntry,
    metric: str,
    value: float,
    low: float,
    high: float,
) -> None:
    name = entry.title
    title = f"TendrilGrow {metric.upper()} out of range: {name}"
    message = (
        f"{metric.upper()} is {value} (target band {low}–{high}). "
        "Check the reservoir and environment."
    )
    notification_id = metric_band_notification_id(entry.entry_id, metric)
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {"title": title, "message": message, "notification_id": notification_id},
        blocking=False,
    )
    notify_service = _entry_notify_service(entry)
    if notify_service and "." in notify_service:
        domain, service = notify_service.split(".", 1)
        try:
            await hass.services.async_call(
                domain,
                service,
                {"title": title, "message": message, "data": {"tag": notification_id}},
                blocking=False,
            )
        except Exception:  # noqa: BLE001
            LOGGER.debug("Metric band notify service call failed", exc_info=True)


async def async_evaluate_metric_bands(
    hass: HomeAssistant,
    entry: ConfigEntry,
    runtime: Any,
) -> None:
    """Recompute band state and fire edge-triggered notifications."""
    state: MetricBandRuntimeState = runtime.metric_band_state
    grow_space = runtime.grow_space
    stage = current_stage(hass, entry)
    stage_band = stage_has_reservoir_band(stage)
    now = dt_util.utcnow()
    cooldown = timedelta(hours=DEFAULT_BAND_COOLDOWN_HOURS)

    for metric in METRICS:
        if not stage_band:
            state.has_band[metric] = False
            state.source_available[metric] = True
            state.out_of_range[metric] = False
            continue

        low, high = read_band_bounds(hass, entry, stage, metric)
        if low is None or high is None:
            state.has_band[metric] = False
            state.source_available[metric] = True
            state.out_of_range[metric] = False
            continue

        state.has_band[metric] = True
        source_id = _metric_source_entity_id(hass, entry, grow_space, metric)
        value = _read_metric_value(hass, source_id)
        if value is None:
            state.source_available[metric] = False
            state.out_of_range[metric] = False
            continue

        state.source_available[metric] = True
        out = _is_out_of_range(value, low, high)
        was_out = state.out_of_range.get(metric, False)
        state.out_of_range[metric] = out

        if out and not was_out:
            last = state.last_notify_at.get(metric)
            if last is None or now - last >= cooldown:
                await _notify_band_breach(hass, entry, metric, value, low, high)
                state.last_notify_at[metric] = now

    async_dispatcher_send(hass, metric_band_dispatcher_signal(entry.entry_id))


async def async_setup_metric_band_monitor(
    hass: HomeAssistant,
    entry: ConfigEntry,
    runtime: Any,
) -> list[Any]:
    """Subscribe to mapped metric sources and evaluate bands on change."""
    grow_space = runtime.grow_space
    entity_ids = [
        eid
        for metric in METRICS
        for eid in [_metric_source_entity_id(hass, entry, grow_space, metric)]
        if eid
    ]

    @callback
    def _on_change(_event) -> None:
        hass.async_create_task(async_evaluate_metric_bands(hass, entry, runtime))

    unsubs: list[Any] = []
    if entity_ids:
        unsubs.append(
            async_track_state_change_event(hass, list(set(entity_ids)), _on_change)
        )
    await async_evaluate_metric_bands(hass, entry, runtime)
    return unsubs
