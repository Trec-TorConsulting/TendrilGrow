"""Tests for cultivation intelligence sensors and binary sensors."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from homeassistant.const import UnitOfTemperature

from custom_components.tendrilgrow.binary_sensor import TendrilGrowMoldRiskBinarySensor
from custom_components.tendrilgrow.const import (
    CTX_LIGHTS_OFF_TIME,
    CTX_LIGHTS_ON_HOURS,
    CTX_LIGHTS_ON_TIME,
    CTX_STAGE,
    CTX_STAGE_STARTED,
    DOMAIN,
    DRIFT_DILUTE,
    DRIFT_ROOT_CHECK,
    SENSOR_ROLE_EC,
    SENSOR_ROLE_HUMIDITY,
    SENSOR_ROLE_LEAF_TEMPERATURE,
    SENSOR_ROLE_PH,
    SENSOR_ROLE_TEMPERATURE,
    SENSOR_ROLE_WATER_LEVEL,
)
from custom_components.tendrilgrow.models.grow import GrowSpace
from custom_components.tendrilgrow.sensors.environment import (
    TendrilGrowDewPointMarginSensor,
    TendrilGrowLeafVpdSensor,
    TendrilGrowPhotoperiodSensor,
    TendrilGrowReservoirDriftSensor,
    TendrilGrowTranspirationRateSensor,
)
from custom_components.tendrilgrow.sensors.stage import TendrilGrowDaysSinceFlipSensor


def _make_hass_and_entry():
    hass = MagicMock()
    entry = SimpleNamespace(
        entry_id="test_entry",
        title="Tent A",
        data={},
        options={},
    )
    grow_space = GrowSpace.new("Tent A", "rdwc")
    runtime = SimpleNamespace(grow_space=grow_space)
    hass.data = {DOMAIN: {entry.entry_id: runtime}}
    return hass, entry, grow_space


def test_leaf_vpd_sensor_fallback_and_measured() -> None:
    hass, entry, grow_space = _make_hass_and_entry()
    grow_space.sensor_mappings[SENSOR_ROLE_TEMPERATURE] = "sensor.air_temp"
    grow_space.sensor_mappings[SENSOR_ROLE_HUMIDITY] = "sensor.air_hum"

    # Air 25 C (77 F), 60% RH. Default offset -3.0 F -> Leaf ~23.33 C
    hass.states.get = MagicMock(
        side_effect=lambda eid: {
            "sensor.air_temp": SimpleNamespace(
                state="25.0", attributes={"unit_of_measurement": "°C"}
            ),
            "sensor.air_hum": SimpleNamespace(state="60.0", attributes={}),
        }.get(eid)
    )

    sensor = TendrilGrowLeafVpdSensor(hass, entry)
    val = sensor.native_value
    assert val is not None
    assert 0.90 <= val <= 1.05
    attrs = sensor.extra_state_attributes
    assert attrs["leaf_temperature_source"] == "offset"
    assert attrs["leaf_temp_offset_applied"] == -3.0

    # Now add measured leaf sensor reporting 22.0 C
    grow_space.sensor_mappings[SENSOR_ROLE_LEAF_TEMPERATURE] = "sensor.leaf_temp"
    hass.states.get = MagicMock(
        side_effect=lambda eid: {
            "sensor.air_temp": SimpleNamespace(
                state="25.0", attributes={"unit_of_measurement": "°C"}
            ),
            "sensor.air_hum": SimpleNamespace(state="60.0", attributes={}),
            "sensor.leaf_temp": SimpleNamespace(
                state="22.0", attributes={"unit_of_measurement": "°C"}
            ),
        }.get(eid)
    )

    val_measured = sensor.native_value
    assert val_measured is not None
    assert 0.70 <= val_measured <= 0.80
    assert sensor.extra_state_attributes["leaf_temperature_source"] == "sensor"


def test_dew_point_margin_sensor() -> None:
    hass, entry, grow_space = _make_hass_and_entry()
    grow_space.sensor_mappings[SENSOR_ROLE_TEMPERATURE] = "sensor.air_temp"
    grow_space.sensor_mappings[SENSOR_ROLE_HUMIDITY] = "sensor.air_hum"

    # 20 C, 50% RH -> Dew point ~9.3 C -> Margin ~10.7 C
    hass.states.get = MagicMock(
        side_effect=lambda eid: {
            "sensor.air_temp": SimpleNamespace(
                state="20.0", attributes={"unit_of_measurement": "°C"}
            ),
            "sensor.air_hum": SimpleNamespace(state="50.0", attributes={}),
        }.get(eid)
    )

    sensor = TendrilGrowDewPointMarginSensor(hass, entry)
    assert sensor.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert sensor.native_value == 10.7

    # If ambient temp is in Fahrenheit
    hass.states.get = MagicMock(
        side_effect=lambda eid: {
            "sensor.air_temp": SimpleNamespace(
                state="68.0", attributes={"unit_of_measurement": "°F"}
            ),
            "sensor.air_hum": SimpleNamespace(state="50.0", attributes={}),
        }.get(eid)
    )
    assert sensor.native_unit_of_measurement == UnitOfTemperature.FAHRENHEIT
    assert sensor.native_value == round(10.7 * 1.8, 1)


def test_reservoir_drift_sensor() -> None:
    hass, entry, grow_space = _make_hass_and_entry()
    grow_space.sensor_mappings[SENSOR_ROLE_EC] = "sensor.ec"
    grow_space.sensor_mappings[SENSOR_ROLE_PH] = "sensor.ph"

    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    t_old = now - timedelta(hours=18)

    sensor = TendrilGrowReservoirDriftSensor(hass, entry)
    # Seed historical baseline
    sensor._samples = [(t_old, 1.2, 6.0, 10.0)]

    # 1. Transpiration outstrips feeding: EC rises 0.2, pH drops 0.3
    hass.states.get = MagicMock(
        side_effect=lambda eid: {
            "sensor.ec": SimpleNamespace(state="1.4"),
            "sensor.ph": SimpleNamespace(state="5.7"),
        }.get(eid)
    )

    with patch("homeassistant.util.dt.now", return_value=now):
        assert sensor.native_value == DRIFT_DILUTE

    # 2. Acid plunge: pH plunges to 5.0 (< 5.2)
    hass.states.get = MagicMock(
        side_effect=lambda eid: {
            "sensor.ec": SimpleNamespace(state="1.4"),
            "sensor.ph": SimpleNamespace(state="5.0"),
        }.get(eid)
    )
    with patch("homeassistant.util.dt.now", return_value=now):
        assert sensor.native_value == DRIFT_ROOT_CHECK


def test_transpiration_rate_sensor() -> None:
    hass, entry, grow_space = _make_hass_and_entry()
    grow_space.sensor_mappings[SENSOR_ROLE_WATER_LEVEL] = "sensor.water_level"

    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    t_old = now - timedelta(hours=24)

    sensor = TendrilGrowTranspirationRateSensor(hass, entry)
    sensor._water_samples = [(t_old, 10.0)]

    hass.states.get = MagicMock(
        side_effect=lambda eid: {
            "sensor.water_level": SimpleNamespace(
                state="8.5", attributes={"unit_of_measurement": "gal"}
            ),
        }.get(eid)
    )

    with patch("homeassistant.util.dt.now", return_value=now):
        assert sensor.native_unit_of_measurement == "gal/d"
        assert sensor.native_value == 1.5
        assert sensor.extra_state_attributes["consumption_status"] == "normal"
        assert sensor.extra_state_attributes["stalled_alert"] is False


def test_photoperiod_sensor() -> None:
    hass, entry, grow_space = _make_hass_and_entry()
    registry = MagicMock()
    registry.async_get_entity_id = MagicMock(
        side_effect=lambda domain, d, unique_id: {
            f"test_entry_{CTX_LIGHTS_ON_TIME}": "time.lights_on",
            f"test_entry_{CTX_LIGHTS_OFF_TIME}": "time.lights_off",
            f"test_entry_{CTX_LIGHTS_ON_HOURS}": "number.lights_on_hours",
        }.get(unique_id)
    )

    hass.states.get = MagicMock(
        side_effect=lambda eid: {
            "time.lights_on": SimpleNamespace(state="18:00"),
            "time.lights_off": SimpleNamespace(state="12:00"),
            "number.lights_on_hours": SimpleNamespace(state="18.0"),
        }.get(eid)
    )

    with patch(
        "custom_components.tendrilgrow.sensors.environment.get_entity_registry",
        return_value=registry,
    ):
        sensor = TendrilGrowPhotoperiodSensor(hass, entry)
        assert sensor.native_value == 18.0


def test_days_since_flip_sensor() -> None:
    hass, entry, grow_space = _make_hass_and_entry()
    registry = MagicMock()
    registry.async_get_entity_id = MagicMock(
        side_effect=lambda domain, d, unique_id: {
            f"test_entry_{CTX_STAGE}": "select.growth_stage",
            f"test_entry_{CTX_STAGE_STARTED}": "date.stage_started",
        }.get(unique_id)
    )

    hass.states.get = MagicMock(
        side_effect=lambda eid: {
            "select.growth_stage": SimpleNamespace(state="mid_flower"),
            "date.stage_started": SimpleNamespace(state="2026-07-10"),
        }.get(eid)
    )

    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    with (
        patch(
            "custom_components.tendrilgrow.sensors.stage.get_entity_registry",
            return_value=registry,
        ),
        patch("homeassistant.util.dt.now", return_value=now),
    ):
        sensor = TendrilGrowDaysSinceFlipSensor(hass, entry)
        assert sensor.native_value == 20
        assert sensor.extra_state_attributes["in_flower"] is True


def test_mold_risk_binary_sensor() -> None:
    hass, entry, grow_space = _make_hass_and_entry()
    grow_space.sensor_mappings[SENSOR_ROLE_TEMPERATURE] = "sensor.air_temp"
    grow_space.sensor_mappings[SENSOR_ROLE_HUMIDITY] = "sensor.air_hum"

    registry = MagicMock()
    registry.async_get_entity_id = MagicMock(
        side_effect=lambda domain, d, unique_id: {
            f"test_entry_{CTX_STAGE}": "select.growth_stage",
        }.get(unique_id)
    )

    # 1. Critical margin: 20 C, 92% RH -> Margin < 2.0 C
    hass.states.get = MagicMock(
        side_effect=lambda eid: {
            "sensor.air_temp": SimpleNamespace(
                state="20.0", attributes={"unit_of_measurement": "°C"}
            ),
            "sensor.air_hum": SimpleNamespace(state="92.0", attributes={}),
            "select.growth_stage": SimpleNamespace(state="vegetative"),
        }.get(eid)
    )

    with patch(
        "custom_components.tendrilgrow.binary_sensor.get_entity_registry",
        return_value=registry,
    ):
        sensor = TendrilGrowMoldRiskBinarySensor(hass, entry)
        assert sensor.is_on is True
        assert (
            "dew_point_margin_critical" in sensor.extra_state_attributes["risk_factors"]
        )

    # 2. High humidity in late flower: 24 C, 68% RH
    hass.states.get = MagicMock(
        side_effect=lambda eid: {
            "sensor.air_temp": SimpleNamespace(
                state="24.0", attributes={"unit_of_measurement": "°C"}
            ),
            "sensor.air_hum": SimpleNamespace(state="68.0", attributes={}),
            "select.growth_stage": SimpleNamespace(state="late_flower"),
        }.get(eid)
    )
    with patch(
        "custom_components.tendrilgrow.binary_sensor.get_entity_registry",
        return_value=registry,
    ):
        assert sensor.is_on is True
        assert (
            "high_humidity_in_vulnerable_stage"
            in sensor.extra_state_attributes["risk_factors"]
        )

    # 3. Safe climate: 24 C, 50% RH in vegetative
    hass.states.get = MagicMock(
        side_effect=lambda eid: {
            "sensor.air_temp": SimpleNamespace(
                state="24.0", attributes={"unit_of_measurement": "°C"}
            ),
            "sensor.air_hum": SimpleNamespace(state="50.0", attributes={}),
            "select.growth_stage": SimpleNamespace(state="vegetative"),
        }.get(eid)
    )
    with patch(
        "custom_components.tendrilgrow.binary_sensor.get_entity_registry",
        return_value=registry,
    ):
        assert sensor.is_on is False
        assert sensor.extra_state_attributes["risk_factors"] == []
