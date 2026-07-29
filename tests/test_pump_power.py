"""Tests for pump power monitoring sensors."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.tendrilgrow.const import (
    CONTROL_ROLE_RDWC_PUMP,
    SENSOR_ROLE_RDWC_PUMP_POWER,
)
from custom_components.tendrilgrow.sensor import (
    TendrilGrowPumpPowerSensor,
    TendrilGrowTotalPumpPowerSensor,
    _resolve_pump_power_source,
)


@pytest.mark.asyncio
async def test_resolve_pump_power_source_explicit_mapping() -> None:
    """Verify explicit power mapping is found."""
    entry = SimpleNamespace(
        entry_id="test-entry",
        title="Tent A",
        data={
            "control_mappings": {CONTROL_ROLE_RDWC_PUMP: "switch.rdwc_pump"},
            "sensor_mappings": {SENSOR_ROLE_RDWC_PUMP_POWER: "sensor.rdwc_power"},
        },
    )

    hass = MagicMock()

    result = await _resolve_pump_power_source(hass, entry, CONTROL_ROLE_RDWC_PUMP)

    assert result == "sensor.rdwc_power"


@pytest.mark.asyncio
async def test_resolve_pump_power_source_missing_when_unmapped() -> None:
    """Verify None returned when pump not mapped."""
    entry = SimpleNamespace(
        entry_id="test-entry",
        title="Tent A",
        data={
            "control_mappings": {},
            "sensor_mappings": {},
        },
    )

    hass = MagicMock()

    result = await _resolve_pump_power_source(hass, entry, CONTROL_ROLE_RDWC_PUMP)

    assert result is None


def test_pump_power_sensor_state_mirroring() -> None:
    """Verify pump power sensor mirrors resolved power entity state."""
    hass = MagicMock()
    hass.states.get = MagicMock(return_value=SimpleNamespace(state="42.5"))

    entry = SimpleNamespace(entry_id="test-entry", title="Tent A")

    sensor = TendrilGrowPumpPowerSensor(
        hass,
        entry,
        CONTROL_ROLE_RDWC_PUMP,
        "sensor.rdwc_pump_power",
    )

    # Should mirror the power value.
    assert sensor.native_value == 42.5
    assert sensor.available is True

    # When power entity is unavailable.
    hass.states.get = MagicMock(return_value=SimpleNamespace(state="unavailable"))
    assert sensor.native_value is None
    assert sensor.available is False

    # When power entity doesn't exist.
    hass.states.get = MagicMock(return_value=None)
    assert sensor.native_value is None
    assert sensor.available is False


def test_pump_power_sensor_no_source() -> None:
    """Verify pump power sensor handles missing power source."""
    hass = MagicMock()
    entry = SimpleNamespace(entry_id="test-entry", title="Tent A")

    sensor = TendrilGrowPumpPowerSensor(
        hass,
        entry,
        CONTROL_ROLE_RDWC_PUMP,
        None,  # No power source
    )

    assert sensor.native_value is None
    assert sensor.available is False


def test_total_pump_power_sensor_sums_available() -> None:
    """Verify total pump power sensor sums available pump powers."""
    hass = MagicMock()
    hass.states.get = MagicMock(
        side_effect=lambda eid: {
            "sensor.rdwc_power": SimpleNamespace(state="50.0"),
            "sensor.chiller_power": SimpleNamespace(state="30.5"),
            "sensor.air_power": SimpleNamespace(state="10.0"),
        }.get(eid)
    )

    entry = SimpleNamespace(entry_id="test-entry", title="Tent A")

    total_sensor = TendrilGrowTotalPumpPowerSensor(
        hass,
        entry,
        ["sensor.rdwc_power", "sensor.chiller_power", "sensor.air_power"],
    )

    # Should sum all available power values.
    assert total_sensor.native_value == 90.5
    assert total_sensor.available is True


def test_total_pump_power_sensor_skips_unavailable() -> None:
    """Verify total pump power sensor skips unavailable sources."""
    hass = MagicMock()
    hass.states.get = MagicMock(
        side_effect=lambda eid: {
            "sensor.rdwc_power": SimpleNamespace(state="50.0"),
            "sensor.chiller_power": SimpleNamespace(state="unavailable"),
            "sensor.air_power": SimpleNamespace(state="10.0"),
        }.get(eid)
    )

    entry = SimpleNamespace(entry_id="test-entry", title="Tent A")

    total_sensor = TendrilGrowTotalPumpPowerSensor(
        hass,
        entry,
        ["sensor.rdwc_power", "sensor.chiller_power", "sensor.air_power"],
    )

    # Should sum only available values (50 + 10, skipping unavailable).
    assert total_sensor.native_value == 60.0
    assert total_sensor.available is True


def test_total_pump_power_sensor_unavailable_when_no_sources() -> None:
    """Verify total pump power sensor is unavailable when no sources."""
    hass = MagicMock()
    hass.states.get = MagicMock(return_value=None)

    entry = SimpleNamespace(entry_id="test-entry", title="Tent A")

    total_sensor = TendrilGrowTotalPumpPowerSensor(
        hass,
        entry,
        ["sensor.rdwc_power", "sensor.chiller_power"],
    )

    assert total_sensor.native_value is None
    assert total_sensor.available is False


def test_total_pump_power_sensor_empty_list() -> None:
    """Verify total pump power sensor handles empty sensor list."""
    hass = MagicMock()
    entry = SimpleNamespace(entry_id="test-entry", title="Tent A")

    total_sensor = TendrilGrowTotalPumpPowerSensor(hass, entry, [])

    assert total_sensor.native_value is None
    assert total_sensor.available is False
