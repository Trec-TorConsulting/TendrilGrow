"""Target bands and light schedule helpers for grow spaces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import async_get as get_entity_registry

from .const import (
    CTX_LIGHTS_OFF_TIME,
    CTX_LIGHTS_ON_HOURS,
    CTX_LIGHTS_ON_TIME,
    CTX_STAGE,
    CTX_TARGET_EC_HIGH,
    CTX_TARGET_EC_LOW,
    CTX_TARGET_PH_HIGH,
    CTX_TARGET_PH_LOW,
    CTX_TARGET_VPD_HIGH,
    CTX_TARGET_VPD_LOW,
    DOMAIN,
    STAGE_TARGETS,
)

BAND_OVERRIDDEN_ATTR = "band_overridden"

TARGET_BAND_SUFFIXES: tuple[str, ...] = (
    CTX_TARGET_PH_LOW,
    CTX_TARGET_PH_HIGH,
    CTX_TARGET_EC_LOW,
    CTX_TARGET_EC_HIGH,
    CTX_TARGET_VPD_LOW,
    CTX_TARGET_VPD_HIGH,
)


def reseed_dispatcher_signal(entry_id: str) -> str:
    return f"{DOMAIN}_reseed_target_bands_{entry_id}"


@dataclass(frozen=True, slots=True)
class TargetBandSpec:
    key: str
    name: str
    stage_field: str
    bound: str
    minimum: float
    maximum: float
    step: float
    unit: str
    icon: str


TARGET_BAND_SPECS: tuple[TargetBandSpec, ...] = (
    TargetBandSpec(
        CTX_TARGET_PH_LOW,
        "Target pH Low",
        "ph",
        "low",
        4.0,
        8.0,
        0.1,
        "pH",
        "mdi:ph",
    ),
    TargetBandSpec(
        CTX_TARGET_PH_HIGH,
        "Target pH High",
        "ph",
        "high",
        4.0,
        8.0,
        0.1,
        "pH",
        "mdi:ph",
    ),
    TargetBandSpec(
        CTX_TARGET_EC_LOW,
        "Target EC Low",
        "ec_ms_cm",
        "low",
        0.0,
        5.0,
        0.1,
        "mS/cm",
        "mdi:flash",
    ),
    TargetBandSpec(
        CTX_TARGET_EC_HIGH,
        "Target EC High",
        "ec_ms_cm",
        "high",
        0.0,
        5.0,
        0.1,
        "mS/cm",
        "mdi:flash",
    ),
    TargetBandSpec(
        CTX_TARGET_VPD_LOW,
        "Target VPD Low",
        "vpd_kpa",
        "low",
        0.0,
        3.0,
        0.1,
        "kPa",
        "mdi:weather-windy",
    ),
    TargetBandSpec(
        CTX_TARGET_VPD_HIGH,
        "Target VPD High",
        "vpd_kpa",
        "high",
        0.0,
        3.0,
        0.1,
        "kPa",
        "mdi:weather-windy",
    ),
)


def parse_stage_range(
    stage: str, stage_field: str
) -> tuple[float | None, float | None]:
    """Parse a STAGE_TARGETS range like ``5.6-6.0`` into low and high floats."""
    raw = STAGE_TARGETS.get(stage, {}).get(stage_field, "")
    if not raw or "-" not in str(raw):
        return None, None
    low_s, high_s = str(raw).split("-", 1)
    try:
        return float(low_s.strip()), float(high_s.strip())
    except ValueError:
        return None, None


def seed_value_for_band(stage: str, spec: TargetBandSpec) -> float | None:
    low, high = parse_stage_range(stage, spec.stage_field)
    if low is None or high is None:
        return None
    return low if spec.bound == "low" else high


def current_stage(hass: HomeAssistant, entry: ConfigEntry) -> str:
    registry = get_entity_registry(hass)
    stage_id = registry.async_get_entity_id(
        "select", DOMAIN, f"{entry.entry_id}_{CTX_STAGE}"
    )
    if not stage_id:
        return "vegetative"
    state = hass.states.get(stage_id)
    if state is None or state.state in ("unknown", "unavailable", ""):
        return "vegetative"
    return str(state.state).strip().lower()


def compute_photoperiod_hours(on_time: time, off_time: time) -> float:
    """Hours lights are on, including an overnight span (off after midnight)."""
    on_minutes = on_time.hour * 60 + on_time.minute
    off_minutes = off_time.hour * 60 + off_time.minute
    if off_minutes <= on_minutes:
        duration_minutes = (24 * 60 - on_minutes) + off_minutes
    else:
        duration_minutes = off_minutes - on_minutes
    return round(duration_minutes / 60.0, 2)


def _number_entity_id(hass: HomeAssistant, entry: ConfigEntry, suffix: str) -> str | None:
    registry = get_entity_registry(hass)
    return registry.async_get_entity_id("number", DOMAIN, f"{entry.entry_id}_{suffix}")


@callback
def sync_lights_on_hours_from_schedule(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update the lights-on-hours number from the on/off time entities."""
    registry = get_entity_registry(hass)
    on_id = registry.async_get_entity_id(
        "time", DOMAIN, f"{entry.entry_id}_{CTX_LIGHTS_ON_TIME}"
    )
    off_id = registry.async_get_entity_id(
        "time", DOMAIN, f"{entry.entry_id}_{CTX_LIGHTS_OFF_TIME}"
    )
    if not on_id or not off_id:
        return
    on_state = hass.states.get(on_id)
    off_state = hass.states.get(off_id)
    if on_state is None or off_state is None:
        return
    if on_state.state in ("unknown", "unavailable") or off_state.state in (
        "unknown",
        "unavailable",
    ):
        return
    try:
        on_parts = [int(p) for p in str(on_state.state).split(":")]
        off_parts = [int(p) for p in str(off_state.state).split(":")]
        on_time = time(on_parts[0], on_parts[1], on_parts[2] if len(on_parts) > 2 else 0)
        off_time = time(
            off_parts[0], off_parts[1], off_parts[2] if len(off_parts) > 2 else 0
        )
    except (ValueError, IndexError):
        return
    hours = compute_photoperiod_hours(on_time, off_time)
    hours_id = _number_entity_id(hass, entry, CTX_LIGHTS_ON_HOURS)
    if not hours_id:
        return
    hass.async_create_task(
        hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": hours_id, "value": hours},
            blocking=False,
        )
    )


def dispatch_reseed_target_bands(hass: HomeAssistant, entry: ConfigEntry, stage: str) -> None:
    async_dispatcher_send(
        hass,
        reseed_dispatcher_signal(entry.entry_id),
        {"stage": stage},
    )


def read_band_bounds(
    hass: HomeAssistant,
    entry: ConfigEntry,
    stage: str,
    metric: str,
) -> tuple[float | None, float | None]:
    """Return low/high bounds for ph, ec, or vpd from operator entities or stage."""
    suffix_map = {
        "ph": (CTX_TARGET_PH_LOW, CTX_TARGET_PH_HIGH, "ph"),
        "ec": (CTX_TARGET_EC_LOW, CTX_TARGET_EC_HIGH, "ec_ms_cm"),
        "vpd": (CTX_TARGET_VPD_LOW, CTX_TARGET_VPD_HIGH, "vpd_kpa"),
    }
    if metric not in suffix_map:
        return None, None
    low_key, high_key, stage_field = suffix_map[metric]
    low = _read_number_state(hass, entry, low_key)
    high = _read_number_state(hass, entry, high_key)
    if low is not None and high is not None:
        return low, high
    return parse_stage_range(stage, stage_field)


def _read_number_state(
    hass: HomeAssistant, entry: ConfigEntry, suffix: str
) -> float | None:
    entity_id = _number_entity_id(hass, entry, suffix)
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state in ("unknown", "unavailable", ""):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def stage_has_reservoir_band(stage: str) -> bool:
    return stage in STAGE_TARGETS
