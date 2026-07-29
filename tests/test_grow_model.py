"""Tests for grow-space model and derived metrics."""

from custom_components.tendrilgrow.const import (
    CONTROL_ROLE_AIR_PUMP,
    CONTROL_ROLE_CHILLER_PUMP,
    CONTROL_ROLE_RDWC_PUMP,
    SENSOR_ROLE_EC_TDS_LEGACY,
    SENSOR_ROLE_HUMIDITY,
    SENSOR_ROLE_TDS,
    SENSOR_ROLE_TEMPERATURE,
)
from custom_components.tendrilgrow.models.grow import GrowSite, GrowSpace


def test_grow_space_round_trip() -> None:
    space = GrowSpace.new(name="Tent A", grow_type="rdwc", descriptor="3x3")
    space.sites.append(GrowSite(site_id="1", name="Mother 1"))
    space.bind_sensor(SENSOR_ROLE_TEMPERATURE, "sensor.tent_a_temp")
    space.bind_sensor(SENSOR_ROLE_HUMIDITY, "sensor.tent_a_humidity")

    restored = GrowSpace.from_dict(space.to_dict())
    assert restored.space_id == space.space_id
    assert restored.name == "Tent A"
    assert restored.sites[0].name == "Mother 1"
    assert restored.sensor_mappings[SENSOR_ROLE_TEMPERATURE] == "sensor.tent_a_temp"


def test_vpd_computation() -> None:
    vpd = GrowSpace.compute_vpd_c_kpa(26.0, 55.0)
    assert vpd is not None
    assert round(vpd, 2) == 1.51


def test_vpd_unavailable_on_missing_inputs() -> None:
    assert GrowSpace.compute_vpd_c_kpa(None, 50.0) is None
    assert GrowSpace.compute_vpd_c_kpa(24.0, None) is None
    assert GrowSpace.compute_vpd_c_kpa(24.0, 0.0) is None


def test_to_celsius_converts_fahrenheit() -> None:
    assert GrowSpace.to_celsius(32.0, "\u00b0F") == 0.0
    assert round(GrowSpace.to_celsius(71.978, "\u00b0F"), 2) == 22.21
    assert GrowSpace.to_celsius(22.0, "\u00b0C") == 22.0
    assert GrowSpace.to_celsius(22.0, None) == 22.0
    assert GrowSpace.to_celsius(None, "\u00b0F") is None


def test_compute_vpd_kpa_is_unit_aware() -> None:
    # 71.978 F == 22.21 C at 70.4% RH -> ~0.79 kPa canopy VPD.
    vpd_f = GrowSpace.compute_vpd_kpa(71.978, "\u00b0F", 70.4)
    vpd_c = GrowSpace.compute_vpd_kpa(22.21, "\u00b0C", 70.4)
    assert vpd_f is not None and vpd_c is not None
    assert round(vpd_f, 2) == round(vpd_c, 2)
    assert 0.7 <= vpd_f <= 0.9


def test_compute_vpd_kpa_missing_inputs() -> None:
    assert GrowSpace.compute_vpd_kpa(None, "\u00b0F", 50.0) is None
    assert GrowSpace.compute_vpd_kpa(70.0, "\u00b0F", None) is None


def test_legacy_ec_tds_mapping_is_migrated_to_tds() -> None:
    restored = GrowSpace.from_dict(
        {
            "space_id": "space-1",
            "name": "Tent A",
            "grow_type": "rdwc",
            "descriptor": "3x3",
            "sites": [],
            "sensor_mappings": {SENSOR_ROLE_EC_TDS_LEGACY: "sensor.bucket_ec_tds"},
            "control_mappings": {},
            "targets": {},
            "schedules": {},
        }
    )

    assert restored.sensor_mappings[SENSOR_ROLE_TDS] == "sensor.bucket_ec_tds"


def test_pump_control_roles_bind_and_round_trip() -> None:
    """Verify pump control roles work with bind_control and from_dict."""
    space = GrowSpace.new(name="Tent A", grow_type="rdwc", descriptor="3x3")
    space.bind_control(CONTROL_ROLE_RDWC_PUMP, "switch.rdwc_pump")
    space.bind_control(CONTROL_ROLE_CHILLER_PUMP, "switch.chiller_pump")
    space.bind_control(CONTROL_ROLE_AIR_PUMP, "switch.air_pump")

    assert space.control_mappings[CONTROL_ROLE_RDWC_PUMP] == "switch.rdwc_pump"
    assert space.control_mappings[CONTROL_ROLE_CHILLER_PUMP] == "switch.chiller_pump"
    assert space.control_mappings[CONTROL_ROLE_AIR_PUMP] == "switch.air_pump"

    # Verify round-trip via from_dict.
    restored = GrowSpace.from_dict(space.to_dict())
    assert restored.control_mappings[CONTROL_ROLE_RDWC_PUMP] == "switch.rdwc_pump"
    assert restored.control_mappings[CONTROL_ROLE_CHILLER_PUMP] == "switch.chiller_pump"
    assert restored.control_mappings[CONTROL_ROLE_AIR_PUMP] == "switch.air_pump"
