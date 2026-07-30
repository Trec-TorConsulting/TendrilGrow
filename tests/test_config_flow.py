"""Tests for TendrilGrow config and options flows."""

from __future__ import annotations

from types import MethodType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.tendrilgrow import async_unload_entry
from custom_components.tendrilgrow.ai.providers import ProviderDiscoveryError
from custom_components.tendrilgrow.config_flow import (
    TendrilGrowConfigFlow,
    TendrilGrowOptionsFlow,
)
from custom_components.tendrilgrow.const import (
    CONF_AI_HEALTH_INTERVAL_HOURS,
    CONF_AI_PROVIDER,
    CONF_AI_RESULT_RETENTION_DAYS,
    CONF_AI_SEVERE_THRESHOLD,
    CONF_BASE_URL,
    CONF_CONTROL_MAPPINGS,
    CONF_GROW_SIZE,
    CONF_GROW_SPACE_NAME,
    CONF_GROW_TYPE,
    CONF_SENSOR_MAPPINGS,
    CONF_TIMELAPSE_DIR,
    CONF_TIMELAPSE_ENABLED,
    CONF_TIMELAPSE_INTERVAL_HOURS,
    CONF_TIMELAPSE_RETENTION_FRAMES,
    CONF_TUYA_ACCESS_ID,
    CONF_TUYA_DEVICE_IDS,
    CONF_TUYA_ENABLED,
    CONF_TUYA_REGION,
    CONF_TUYA_SCAN_INTERVAL,
    DEFAULT_TIMELAPSE_INTERVAL_HOURS,
    DEFAULT_TIMELAPSE_RETENTION_FRAMES,
    PROVIDER_NONE,
    SENSOR_ROLE_CAMERA,
    SENSOR_ROLE_CF,
    SENSOR_ROLE_EC,
    SENSOR_ROLE_ORP,
    SENSOR_ROLE_PH,
    SENSOR_ROLE_TDS,
)


def _patch_show_form(flow):
    def _show_form(self, *, step_id, data_schema, errors):
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors,
        }

    flow.async_show_form = MethodType(_show_form, flow)


def _patch_create_entry(flow):
    def _create_entry(self, *, title, data):
        return {"type": "create_entry", "title": title, "data": data}

    flow.async_create_entry = MethodType(_create_entry, flow)


@pytest.mark.asyncio
async def test_user_step_rejects_duplicate_name() -> None:
    flow = TendrilGrowConfigFlow()
    _patch_show_form(flow)
    flow._async_current_entries = Mock(return_value=[SimpleNamespace(title="Tent A")])

    result = await flow.async_step_user(
        {CONF_GROW_SPACE_NAME: "Tent A", CONF_GROW_TYPE: "rdwc", CONF_GROW_SIZE: "3x3"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "duplicate_name"


@pytest.mark.asyncio
async def test_create_entry_with_optional_mappings_skipped() -> None:
    flow = TendrilGrowConfigFlow()
    _patch_show_form(flow)
    _patch_create_entry(flow)
    flow._async_current_entries = Mock(return_value=[])

    await flow.async_step_user(
        {CONF_GROW_SPACE_NAME: "Tent B", CONF_GROW_TYPE: "soil", CONF_GROW_SIZE: "4x4"}
    )
    await flow.async_step_entity_mapping({})
    result = await flow.async_step_ai_provider({CONF_AI_PROVIDER: PROVIDER_NONE})

    assert result["type"] == "create_entry"
    assert result["title"] == "Tent B"
    assert result["data"]["sensor_mappings"] == {}
    assert result["data"]["control_mappings"] == {}
    assert result["data"][CONF_TIMELAPSE_ENABLED] is False
    assert (
        result["data"][CONF_TIMELAPSE_INTERVAL_HOURS]
        == DEFAULT_TIMELAPSE_INTERVAL_HOURS
    )
    assert (
        result["data"][CONF_TIMELAPSE_RETENTION_FRAMES]
        == DEFAULT_TIMELAPSE_RETENTION_FRAMES
    )


@pytest.mark.asyncio
async def test_provider_discovery_failure_accepts_manual_model() -> None:
    flow = TendrilGrowConfigFlow()
    _patch_show_form(flow)
    _patch_create_entry(flow)

    flow.hass = SimpleNamespace()
    flow._data = {
        CONF_GROW_SPACE_NAME: "Tent C",
        CONF_GROW_TYPE: "rdwc",
        CONF_GROW_SIZE: "4x4",
        CONF_AI_PROVIDER: "ollama",
    }

    async def _raise_discovery(hass, provider, config):
        _ = hass
        _ = provider
        _ = config
        raise ProviderDiscoveryError("cannot discover")

    from custom_components.tendrilgrow import config_flow as cfg

    original = cfg.discover_models
    cfg.discover_models = AsyncMock(side_effect=_raise_discovery)
    try:
        result = await flow.async_step_ai_credentials(
            {CONF_BASE_URL: "http://localhost:11434", "model": "llama3.1"}
        )
    finally:
        cfg.discover_models = original

    assert result["type"] == "create_entry"
    assert result["data"]["ai_model"] == "llama3.1"


@pytest.mark.asyncio
async def test_options_flow_edit_creates_options_payload() -> None:
    entry = SimpleNamespace(
        data={
            "grow_type": "rdwc",
            "grow_size": "3x3",
            "sensor_mappings": {"temperature": "sensor.old"},
            "control_mappings": {"lights": "light.old"},
        }
    )
    flow = TendrilGrowOptionsFlow(entry)
    _patch_show_form(flow)
    _patch_create_entry(flow)

    form = await flow.async_step_init()
    assert form["type"] == "form"

    result = await flow.async_step_init(
        {
            "grow_type": "soil",
            "grow_size": "5x5",
            "temperature": "sensor.new",
            SENSOR_ROLE_CAMERA: "camera.tent_a",
            CONF_TUYA_ENABLED: True,
            CONF_TUYA_ACCESS_ID: "abc123",
            CONF_TUYA_REGION: "us",
            CONF_TUYA_DEVICE_IDS: "dev-1,dev-2",
            CONF_TUYA_SCAN_INTERVAL: 120,
            CONF_AI_HEALTH_INTERVAL_HOURS: 12,
            CONF_AI_SEVERE_THRESHOLD: 20,
            CONF_AI_RESULT_RETENTION_DAYS: 30,
            CONF_TIMELAPSE_ENABLED: True,
            CONF_TIMELAPSE_INTERVAL_HOURS: 8,
            CONF_TIMELAPSE_RETENTION_FRAMES: 300,
            CONF_TIMELAPSE_DIR: "/config/www/tendrilgrow/tent-a/timelapse",
        }
    )
    assert result["type"] == "create_entry"
    assert result["data"]["grow_type"] == "soil"
    assert result["data"][CONF_SENSOR_MAPPINGS] == {
        "temperature": "sensor.new",
        SENSOR_ROLE_CAMERA: "camera.tent_a",
    }
    assert result["data"][CONF_TUYA_ENABLED] is True
    assert result["data"][CONF_TUYA_DEVICE_IDS] == ["dev-1", "dev-2"]
    assert result["data"][CONF_TIMELAPSE_ENABLED] is True
    assert result["data"][CONF_TIMELAPSE_INTERVAL_HOURS] == 8
    assert result["data"][CONF_TIMELAPSE_RETENTION_FRAMES] == 300
    assert (
        result["data"][CONF_TIMELAPSE_DIR]
        == "/config/www/tendrilgrow/tent-a/timelapse"
    )


@pytest.mark.asyncio
async def test_entity_mapping_form_includes_water_quality_roles() -> None:
    flow = TendrilGrowConfigFlow()
    _patch_show_form(flow)

    result = await flow.async_step_entity_mapping()

    assert result["type"] == "form"
    schema_keys = {key.schema for key in result["data_schema"].schema}
    assert SENSOR_ROLE_PH in schema_keys
    assert SENSOR_ROLE_EC in schema_keys
    assert SENSOR_ROLE_CF in schema_keys
    assert SENSOR_ROLE_ORP in schema_keys
    assert SENSOR_ROLE_TDS in schema_keys
    assert CONF_TUYA_ENABLED in schema_keys
    assert CONF_TUYA_ACCESS_ID in schema_keys
    assert CONF_TUYA_REGION in schema_keys


@pytest.mark.asyncio
async def test_entity_mapping_form_hides_sensor_roles_when_tuya_enabled() -> None:
    flow = TendrilGrowConfigFlow()
    _patch_show_form(flow)
    flow._data[CONF_TUYA_ENABLED] = True

    result = await flow.async_step_entity_mapping()

    schema_keys = {key.schema for key in result["data_schema"].schema}
    assert SENSOR_ROLE_PH not in schema_keys
    assert SENSOR_ROLE_EC not in schema_keys
    assert SENSOR_ROLE_CF not in schema_keys
    assert SENSOR_ROLE_ORP not in schema_keys
    assert SENSOR_ROLE_TDS not in schema_keys
    assert SENSOR_ROLE_CAMERA in schema_keys
    assert CONF_TUYA_ENABLED in schema_keys


@pytest.mark.asyncio
async def test_options_form_hides_sensor_roles_when_tuya_enabled() -> None:
    entry = SimpleNamespace(
        data={
            "grow_type": "rdwc",
            "grow_size": "3x3",
            "sensor_mappings": {"ph": "sensor.old_ph"},
            "control_mappings": {},
            CONF_TUYA_ENABLED: True,
        }
    )
    flow = TendrilGrowOptionsFlow(entry)
    _patch_show_form(flow)

    result = await flow.async_step_init()

    schema_keys = {key.schema for key in result["data_schema"].schema}
    assert SENSOR_ROLE_PH not in schema_keys
    assert SENSOR_ROLE_EC not in schema_keys
    assert SENSOR_ROLE_CF not in schema_keys
    assert SENSOR_ROLE_ORP not in schema_keys
    assert SENSOR_ROLE_TDS not in schema_keys
    assert SENSOR_ROLE_CAMERA in schema_keys
    assert CONF_TUYA_ENABLED in schema_keys


@pytest.mark.asyncio
async def test_unload_entry_keeps_other_entries_intact() -> None:
    unsub_one = Mock()
    unsub_two = Mock()

    hass = SimpleNamespace(
        data={
            "tendrilgrow": {
                "entry-1": SimpleNamespace(unsubscribe_update_listener=unsub_one),
                "entry-2": SimpleNamespace(unsubscribe_update_listener=unsub_two),
            }
        },
        config_entries=SimpleNamespace(
            async_unload_platforms=AsyncMock(return_value=True)
        ),
    )

    entry = SimpleNamespace(entry_id="entry-1", title="Tent A")
    assert await async_unload_entry(hass, entry)
    assert "entry-1" not in hass.data["tendrilgrow"]
    assert "entry-2" in hass.data["tendrilgrow"]
    unsub_one.assert_called_once()
    unsub_two.assert_not_called()


@pytest.mark.asyncio
async def test_options_flow_pump_control_and_power_mappings() -> None:
    """Verify pump control and power sensor mappings are stored correctly."""
    from custom_components.tendrilgrow.const import (
        CONTROL_ROLE_AIR_PUMP,
        CONTROL_ROLE_CHILLER_PUMP,
        CONTROL_ROLE_RDWC_PUMP,
        SENSOR_ROLE_AIR_PUMP_POWER,
        SENSOR_ROLE_CHILLER_PUMP_POWER,
        SENSOR_ROLE_RDWC_PUMP_POWER,
    )

    entry = SimpleNamespace(
        data={
            "grow_type": "rdwc",
            "grow_size": "3x3",
            "sensor_mappings": {"temperature": "sensor.old"},
            "control_mappings": {},
        }
    )
    flow = TendrilGrowOptionsFlow(entry)
    _patch_show_form(flow)
    _patch_create_entry(flow)

    # Show the options form.
    form = await flow.async_step_init()
    assert form["type"] == "form"

    # Submit pump control and power mappings.
    result = await flow.async_step_init(
        {
            "grow_type": "rdwc",
            "grow_size": "3x3",
            "temperature": "sensor.old",
            CONTROL_ROLE_RDWC_PUMP: "switch.rdwc_pump",
            SENSOR_ROLE_RDWC_PUMP_POWER: "sensor.rdwc_pump_power",
            CONTROL_ROLE_CHILLER_PUMP: "switch.chiller_pump",
            SENSOR_ROLE_CHILLER_PUMP_POWER: "sensor.chiller_pump_power",
            CONTROL_ROLE_AIR_PUMP: "switch.air_pump",
            # Air pump has no power mapping.
            CONF_TUYA_ENABLED: False,
            CONF_TUYA_ACCESS_ID: "",
            CONF_TUYA_REGION: "us",
            CONF_TUYA_DEVICE_IDS: "",
            CONF_TUYA_SCAN_INTERVAL: 60,
            CONF_AI_HEALTH_INTERVAL_HOURS: 12,
            CONF_AI_SEVERE_THRESHOLD: 20,
            CONF_AI_RESULT_RETENTION_DAYS: 30,
        }
    )

    assert result["type"] == "create_entry"
    # Verify pump controls are in control_mappings.
    control_mappings = result["data"][CONF_CONTROL_MAPPINGS]
    assert control_mappings[CONTROL_ROLE_RDWC_PUMP] == "switch.rdwc_pump"
    assert control_mappings[CONTROL_ROLE_CHILLER_PUMP] == "switch.chiller_pump"
    assert control_mappings[CONTROL_ROLE_AIR_PUMP] == "switch.air_pump"

    # Verify power sensors are in sensor_mappings.
    sensor_mappings = result["data"][CONF_SENSOR_MAPPINGS]
    assert sensor_mappings[SENSOR_ROLE_RDWC_PUMP_POWER] == "sensor.rdwc_pump_power"
    assert (
        sensor_mappings[SENSOR_ROLE_CHILLER_PUMP_POWER] == "sensor.chiller_pump_power"
    )
    # Air pump power not submitted, should not be in mappings.
    assert SENSOR_ROLE_AIR_PUMP_POWER not in sensor_mappings
