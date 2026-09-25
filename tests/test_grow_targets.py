"""Tests for grow target bands and light schedule."""

from __future__ import annotations

from datetime import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.tendrilgrow.const import (
    CTX_TARGET_PH_HIGH,
    CTX_TARGET_PH_LOW,
)
from custom_components.tendrilgrow.grow_targets import (
    BAND_OVERRIDDEN_ATTR,
    TARGET_BAND_SPECS,
    compute_photoperiod_hours,
    parse_stage_range,
    read_band_bounds,
    seed_value_for_band,
)
from custom_components.tendrilgrow.number import TargetBandNumber
from custom_components.tendrilgrow.grow_targets import TargetBandSpec


def test_vegetative_stage_seeds_ph_band() -> None:
    low_spec = next(s for s in TARGET_BAND_SPECS if s.key == CTX_TARGET_PH_LOW)
    high_spec = next(s for s in TARGET_BAND_SPECS if s.key == CTX_TARGET_PH_HIGH)
    assert seed_value_for_band("vegetative", low_spec) == 5.6
    assert seed_value_for_band("vegetative", high_spec) == 6.0
    assert parse_stage_range("vegetative", "ph") == (5.6, 6.0)


def test_lights_18_00_to_12_00_is_18_hours() -> None:
    assert compute_photoperiod_hours(time(18, 0), time(12, 0)) == 18.0


@pytest.mark.asyncio
async def test_target_band_marks_overridden_on_edit() -> None:
    spec = next(s for s in TARGET_BAND_SPECS if s.key == CTX_TARGET_PH_HIGH)
    hass = MagicMock()
    entry = SimpleNamespace(entry_id="e1", title="Tent")
    entity = TargetBandNumber(hass, entry, spec)
    entity.hass = hass
    entity.async_get_last_number_data = AsyncMock(return_value=None)
    entity.async_get_last_state = AsyncMock(return_value=None)
    entity.async_write_ha_state = MagicMock()
    hass.states.get = MagicMock(return_value=SimpleNamespace(state="vegetative"))

    await entity.async_added_to_hass()
    await entity.async_set_native_value(6.5)

    assert entity._band_overridden is True
    assert entity.extra_state_attributes[BAND_OVERRIDDEN_ATTR] is True


@pytest.mark.asyncio
async def test_reseed_skips_overridden_band() -> None:
    spec = next(s for s in TARGET_BAND_SPECS if s.key == CTX_TARGET_PH_HIGH)
    hass = MagicMock()
    entry = SimpleNamespace(entry_id="e1", title="Tent")
    entity = TargetBandNumber(hass, entry, spec)
    entity._band_overridden = True
    entity._attr_native_value = 6.5
    entity.async_write_ha_state = MagicMock()
    entity._apply_reseed("seedling")
    assert entity._attr_native_value == 6.5
    entity.async_write_ha_state.assert_not_called()


def test_read_band_bounds_prefers_operator_numbers() -> None:
    hass = MagicMock()
    entry = SimpleNamespace(entry_id="e1", data={}, options={})

    def _entity_id(domain, _d, unique):
        if unique.endswith(CTX_TARGET_PH_LOW):
            return "number.ph_low"
        if unique.endswith(CTX_TARGET_PH_HIGH):
            return "number.ph_high"
        return None

    registry = MagicMock()
    registry.async_get_entity_id = MagicMock(side_effect=_entity_id)
    hass.states.get = MagicMock(
        side_effect=lambda eid: {
            "number.ph_low": SimpleNamespace(state="5.0"),
            "number.ph_high": SimpleNamespace(state="6.2"),
        }.get(eid)
    )

    from homeassistant.helpers import entity_registry as er

    original = er.async_get
    er.async_get = MagicMock(return_value=registry)  # type: ignore[method-assign]
    try:
        low, high = read_band_bounds(hass, entry, "vegetative", "ph")
    finally:
        er.async_get = original  # type: ignore[method-assign]

    assert low == 5.0
    assert high == 6.2


@pytest.mark.asyncio
async def test_editing_target_does_not_touch_config_entry() -> None:
    spec = next(s for s in TARGET_BAND_SPECS if s.key == CTX_TARGET_PH_LOW)
    hass = MagicMock()
    entry = SimpleNamespace(
        entry_id="e1",
        title="Tent",
        data={"water_monitor_device_id": "dev-1", "tuya_access_secret": "secret"},
        options={},
    )
    hass.config_entries = MagicMock()
    entity = TargetBandNumber(hass, entry, spec)
    entity.hass = hass
    entity.async_get_last_number_data = AsyncMock(return_value=None)
    entity.async_get_last_state = AsyncMock(return_value=None)
    entity.async_write_ha_state = MagicMock()
    hass.states.get = MagicMock(return_value=SimpleNamespace(state="vegetative"))

    await entity.async_added_to_hass()
    await entity.async_set_native_value(5.7)

    hass.config_entries.async_update_entry.assert_not_called()
    assert entry.data["water_monitor_device_id"] == "dev-1"
    assert entry.data["tuya_access_secret"] == "secret"
