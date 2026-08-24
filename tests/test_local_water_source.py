"""Tests for LocalTuya / Tuya Local water-source resolution."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.tendrilgrow.const import (
    CONF_TUYA_ACCESS_ID,
    CONF_TUYA_ACCESS_SECRET,
    CONF_TUYA_DEVICE_IDS,
    CONF_TUYA_ENABLED,
    CONF_WATER_MONITOR_DEVICE_ID,
    LOCALTUYA_DOMAIN,
    SENSOR_ROLE_CF,
    SENSOR_ROLE_EC,
    SENSOR_ROLE_HUMIDITY,
    SENSOR_ROLE_ORP,
    SENSOR_ROLE_PH,
    SENSOR_ROLE_TDS,
    SENSOR_ROLE_TEMPERATURE,
    SENSOR_ROLE_WATER_TEMPERATURE,
    TUYA_LOCAL_DOMAIN,
    WATER_SOURCE_CLOUD,
    WATER_SOURCE_LOCALTUYA,
    WATER_SOURCE_NONE,
    WATER_SOURCE_TUYA_LOCAL,
)
from custom_components.tendrilgrow.local_water_source import (
    apply_local_water_automap,
    classify_local_water_sensors,
    effective_water_source,
    find_unique_local_match,
)
from custom_components.tendrilgrow.sensor import (
    _METRIC_TO_ROLE,
    METRICS,
)
from custom_components.tendrilgrow.sensor import (
    async_setup_entry as async_setup_sensors,
)


def _device(device_id: str, domain: str, tuya_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=device_id,
        identifiers={(domain, tuya_id)},
    )


def _entity(
    entity_id: str,
    device_id: str,
    *,
    name: str = "",
    device_class: str | None = None,
    disabled: bool = False,
    hidden: bool = False,
    domain: str = "sensor",
) -> SimpleNamespace:
    return SimpleNamespace(
        entity_id=entity_id,
        device_id=device_id,
        domain=domain,
        name=name,
        original_name=name,
        device_class=device_class,
        original_device_class=device_class,
        disabled=disabled,
        hidden=hidden,
    )


def test_find_unique_local_match_prefers_localtuya() -> None:
    devices = {
        "dev-a": _device("dev-a", LOCALTUYA_DOMAIN, "tuya-1"),
        "dev-b": _device("dev-b", TUYA_LOCAL_DOMAIN, "tuya-1"),
    }
    hass = SimpleNamespace()
    with patch(
        "custom_components.tendrilgrow.local_water_source.dr.async_get",
        return_value=SimpleNamespace(devices=devices, async_get=devices.get),
    ):
        match = find_unique_local_match(hass, ["tuya-1"])
    assert match == ("dev-a", LOCALTUYA_DOMAIN)


def test_find_unique_local_match_ambiguous() -> None:
    devices = {
        "dev-a": _device("dev-a", LOCALTUYA_DOMAIN, "tuya-1"),
        "dev-b": _device("dev-b", LOCALTUYA_DOMAIN, "tuya-1"),
    }
    hass = SimpleNamespace()
    with patch(
        "custom_components.tendrilgrow.local_water_source.dr.async_get",
        return_value=SimpleNamespace(devices=devices, async_get=devices.get),
    ):
        assert find_unique_local_match(hass, ["tuya-1"]) is None


def test_find_unique_local_match_none() -> None:
    devices = {"dev-a": _device("dev-a", LOCALTUYA_DOMAIN, "other")}
    hass = SimpleNamespace()
    with patch(
        "custom_components.tendrilgrow.local_water_source.dr.async_get",
        return_value=SimpleNamespace(devices=devices, async_get=devices.get),
    ):
        assert find_unique_local_match(hass, ["tuya-1"]) is None


def test_find_unique_local_match_tolerates_triple_identifiers() -> None:
    """HA 2026 device identifiers can be 3-tuples; matching must not unpack-crash."""
    devices = {
        "other": SimpleNamespace(
            id="other",
            identifiers={("hue", "bridge", "extra")},
        ),
        "dev-a": SimpleNamespace(
            id="dev-a",
            identifiers={(TUYA_LOCAL_DOMAIN, "tuya-1", "extra")},
        ),
    }
    hass = SimpleNamespace()
    with patch(
        "custom_components.tendrilgrow.local_water_source.dr.async_get",
        return_value=SimpleNamespace(devices=devices, async_get=devices.get),
    ):
        assert find_unique_local_match(hass, ["tuya-1"]) == (
            "dev-a",
            TUYA_LOCAL_DOMAIN,
        )


def test_classify_local_water_sensors_by_class_unit_and_name() -> None:
    entities = {
        "sensor.ph": _entity(
            "sensor.ph", "dev-1", name="pH", device_class="ph"
        ),
        "sensor.ec": _entity("sensor.ec", "dev-1", name="EC"),
        "sensor.tds": _entity("sensor.tds", "dev-1", name="TDS"),
        "sensor.orp": _entity("sensor.orp", "dev-1", name="ORP"),
        "sensor.cf": _entity("sensor.cf", "dev-1", name="CF"),
        "sensor.water_temp": _entity(
            "sensor.water_temp",
            "dev-1",
            name="Water Temperature",
            device_class="temperature",
        ),
        "sensor.humidity": _entity(
            "sensor.humidity",
            "dev-1",
            name="Humidity",
            device_class="humidity",
        ),
        "sensor.battery": _entity(
            "sensor.battery",
            "dev-1",
            name="Battery",
            device_class="battery",
        ),
        "number.ph_cal": SimpleNamespace(
            entity_id="number.ph_cal",
            device_id="dev-1",
            domain="number",
            name="pH Cal",
            original_name="pH Cal",
            device_class=None,
            original_device_class=None,
            disabled=False,
            hidden=False,
        ),
    }

    states = {
        "sensor.ec": SimpleNamespace(
            attributes={"unit_of_measurement": "mS/cm"}
        ),
        "sensor.tds": SimpleNamespace(attributes={"unit_of_measurement": "ppm"}),
        "sensor.orp": SimpleNamespace(attributes={"unit_of_measurement": "mV"}),
    }

    hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda entity_id: states.get(entity_id))
    )
    with patch(
        "custom_components.tendrilgrow.local_water_source.er.async_get",
        return_value=SimpleNamespace(entities=entities),
    ):
        classified = classify_local_water_sensors(hass, "dev-1")

    assert classified[SENSOR_ROLE_PH] == "sensor.ph"
    assert classified[SENSOR_ROLE_EC] == "sensor.ec"
    assert classified[SENSOR_ROLE_WATER_TEMPERATURE] == "sensor.water_temp"
    assert SENSOR_ROLE_HUMIDITY not in classified
    assert SENSOR_ROLE_TEMPERATURE not in classified
    assert "number.ph_cal" not in classified.values()


def test_classify_tuya_local_probe_entity_names() -> None:
    """Tuya Local uses long OEM names and a generic Temperature sensor."""
    entities = {
        "sensor.3x3_water_monitor_ph": _entity(
            "sensor.3x3_water_monitor_ph", "dev-1", name="pH"
        ),
        "sensor.3x3_water_monitor_electrical_conductivity": _entity(
            "sensor.3x3_water_monitor_electrical_conductivity",
            "dev-1",
            name="Electrical conductivity",
        ),
        "sensor.3x3_water_monitor_cf": _entity(
            "sensor.3x3_water_monitor_cf", "dev-1", name="CF"
        ),
        "sensor.3x3_water_monitor_total_dissolved_solids": _entity(
            "sensor.3x3_water_monitor_total_dissolved_solids",
            "dev-1",
            name="Total dissolved solids",
        ),
        "sensor.3x3_water_monitor_oxidation_reduction_potential": _entity(
            "sensor.3x3_water_monitor_oxidation_reduction_potential",
            "dev-1",
            name="Oxidation reduction potential",
        ),
        "sensor.3x3_water_monitor_temperature": _entity(
            "sensor.3x3_water_monitor_temperature",
            "dev-1",
            name="Temperature",
            device_class="temperature",
        ),
        "sensor.3x3_water_monitor_humidity": _entity(
            "sensor.3x3_water_monitor_humidity",
            "dev-1",
            name="Humidity",
            device_class="humidity",
        ),
        "sensor.3x3_water_monitor_battery": _entity(
            "sensor.3x3_water_monitor_battery",
            "dev-1",
            name="Battery",
            device_class="battery",
        ),
    }
    hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda _entity_id: None)
    )
    with patch(
        "custom_components.tendrilgrow.local_water_source.er.async_get",
        return_value=SimpleNamespace(entities=entities),
    ):
        classified = classify_local_water_sensors(hass, "dev-1")

    assert classified == {
        SENSOR_ROLE_PH: "sensor.3x3_water_monitor_ph",
        SENSOR_ROLE_EC: "sensor.3x3_water_monitor_electrical_conductivity",
        SENSOR_ROLE_CF: "sensor.3x3_water_monitor_cf",
        SENSOR_ROLE_TDS: "sensor.3x3_water_monitor_total_dissolved_solids",
        SENSOR_ROLE_ORP: "sensor.3x3_water_monitor_oxidation_reduction_potential",
        SENSOR_ROLE_WATER_TEMPERATURE: "sensor.3x3_water_monitor_temperature",
    }


def test_apply_local_water_automap_preserves_existing() -> None:
    grow_space = SimpleNamespace(
        sensor_mappings={SENSOR_ROLE_PH: "sensor.manual_ph"}
    )
    auto_mapped: dict[str, str] = {}
    entry = SimpleNamespace(
        entry_id="entry-1",
        data={CONF_WATER_MONITOR_DEVICE_ID: "dev-1"},
        options={},
    )
    with patch(
        "custom_components.tendrilgrow.local_water_source.classify_local_water_sensors",
        return_value={
            SENSOR_ROLE_PH: "sensor.auto_ph",
            SENSOR_ROLE_EC: "sensor.auto_ec",
        },
    ):
        newly = apply_local_water_automap(
            SimpleNamespace(),
            entry,
            grow_space,
            auto_mapped,
            device_id="dev-1",
        )

    assert grow_space.sensor_mappings[SENSOR_ROLE_PH] == "sensor.manual_ph"
    assert grow_space.sensor_mappings[SENSOR_ROLE_EC] == "sensor.auto_ec"
    assert newly == {SENSOR_ROLE_EC: "sensor.auto_ec"}
    assert SENSOR_ROLE_PH not in auto_mapped


def test_effective_water_source_local_wins_over_cloud() -> None:
    entry = SimpleNamespace(
        data={
            CONF_WATER_MONITOR_DEVICE_ID: "dev-1",
            CONF_TUYA_ENABLED: True,
            CONF_TUYA_ACCESS_ID: "id",
            CONF_TUYA_ACCESS_SECRET: "secret",
            CONF_TUYA_DEVICE_IDS: ["tuya-1"],
        },
        options={},
    )
    devices = {"dev-1": _device("dev-1", LOCALTUYA_DOMAIN, "tuya-1")}
    hass = SimpleNamespace()
    with patch(
        "custom_components.tendrilgrow.local_water_source.dr.async_get",
        return_value=SimpleNamespace(devices=devices, async_get=devices.get),
    ):
        assert effective_water_source(hass, entry) == WATER_SOURCE_LOCALTUYA


def test_effective_water_source_cloud_fallback() -> None:
    entry = SimpleNamespace(
        data={
            CONF_TUYA_ENABLED: True,
            CONF_TUYA_ACCESS_ID: "id",
            CONF_TUYA_ACCESS_SECRET: "secret",
            CONF_TUYA_DEVICE_IDS: ["tuya-1"],
        },
        options={},
    )
    hass = SimpleNamespace()
    with patch(
        "custom_components.tendrilgrow.local_water_source.dr.async_get",
        return_value=SimpleNamespace(devices={}, async_get=lambda _id: None),
    ):
        assert effective_water_source(hass, entry) == WATER_SOURCE_CLOUD


def test_effective_water_source_none() -> None:
    entry = SimpleNamespace(data={}, options={})
    hass = SimpleNamespace()
    with patch(
        "custom_components.tendrilgrow.local_water_source.dr.async_get",
        return_value=SimpleNamespace(devices={}, async_get=lambda _id: None),
    ):
        assert effective_water_source(hass, entry) == WATER_SOURCE_NONE


def test_effective_water_source_tuya_local() -> None:
    entry = SimpleNamespace(
        data={CONF_WATER_MONITOR_DEVICE_ID: "dev-1"},
        options={},
    )
    devices = {"dev-1": _device("dev-1", TUYA_LOCAL_DOMAIN, "tuya-1")}
    hass = SimpleNamespace()
    with patch(
        "custom_components.tendrilgrow.local_water_source.dr.async_get",
        return_value=SimpleNamespace(devices=devices, async_get=devices.get),
    ):
        assert effective_water_source(hass, entry) == WATER_SOURCE_TUYA_LOCAL


def test_cloud_metric_map_excludes_humidity() -> None:
    assert "ambient_humidity" not in _METRIC_TO_ROLE
    assert "ph" in _METRIC_TO_ROLE


@pytest.mark.asyncio
async def test_sensor_setup_skips_coordinator_when_local() -> None:
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Tent A",
        data={"control_mappings": {}},
        options={},
    )
    async_add_entities = AsyncMock()
    hass = SimpleNamespace(data={"tendrilgrow": {}})
    with (
        patch(
            "custom_components.tendrilgrow.sensor.effective_water_source",
            return_value=WATER_SOURCE_LOCALTUYA,
        ),
        patch(
            "custom_components.tendrilgrow.sensor.TendrilGrowTuyaCoordinator"
        ) as coordinator_cls,
    ):
        await async_setup_sensors(hass, entry, async_add_entities)

    coordinator_cls.assert_not_called()
    entities = async_add_entities.call_args[0][0]
    names = {type(entity).__name__ for entity in entities}
    assert "AIHealthScoreSensor" in names
    assert "TendrilGrowVpdSensor" in names
    assert "TuyaMetricSensor" not in names


@pytest.mark.asyncio
async def test_sensor_setup_creates_tuya_sensors_for_cloud() -> None:
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Tent A",
        data={
            "control_mappings": {},
            CONF_TUYA_DEVICE_IDS: ["abcdef123456"],
        },
        options={},
    )
    async_add_entities = AsyncMock()
    coordinator = SimpleNamespace(
        async_refresh=AsyncMock(),
        device_names={},
        device_last_updated={},
        data={},
    )
    hass = SimpleNamespace(data={"tendrilgrow": {}})
    with (
        patch(
            "custom_components.tendrilgrow.sensor.effective_water_source",
            return_value=WATER_SOURCE_CLOUD,
        ),
        patch(
            "custom_components.tendrilgrow.sensor.tuya_device_ids",
            return_value=["abcdef123456"],
        ),
        patch(
            "custom_components.tendrilgrow.sensor.TendrilGrowTuyaCoordinator",
            return_value=coordinator,
        ),
    ):
        await async_setup_sensors(hass, entry, async_add_entities)

    entities = async_add_entities.call_args[0][0]
    metric_count = sum(
        1 for entity in entities if type(entity).__name__ == "TuyaMetricSensor"
    )
    assert metric_count == len(METRICS)
    assert any(type(entity).__name__ == "TuyaLastUpdatedSensor" for entity in entities)
    assert any(type(entity).__name__ == "TendrilGrowVpdSensor" for entity in entities)
