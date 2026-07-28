"""Tests for grow-space model and derived metrics."""

from custom_components.tendrilgrow.const import SENSOR_ROLE_HUMIDITY, SENSOR_ROLE_TEMPERATURE
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
