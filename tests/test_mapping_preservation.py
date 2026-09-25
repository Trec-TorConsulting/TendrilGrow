"""Tests for mapping merge and credential preservation on options save."""

from __future__ import annotations

from types import MethodType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from custom_components.tendrilgrow.config_flow import TendrilGrowOptionsFlow
from custom_components.tendrilgrow.const import (
    CONF_CONTROL_MAPPINGS,
    CONF_SENSOR_MAPPINGS,
    CONF_TUYA_ACCESS_ID,
    CONF_TUYA_ACCESS_SECRET,
    CONF_TUYA_DEVICE_IDS,
    CONF_TUYA_ENABLED,
    CONF_WATER_MONITOR_DEVICE_ID,
    CONTROL_ROLE_RDWC_PUMP,
    SENSOR_ROLE_PH,
)
from custom_components.tendrilgrow.local_water_source import async_resolve_water_monitor_device
from custom_components.tendrilgrow.switch import async_setup_entry


def _patch_create_entry(flow):
    def _create_entry(self, *, title, data):
        return {"type": "create_entry", "title": title, "data": data}

    flow.async_create_entry = MethodType(_create_entry, flow)


def _minimal_options_payload(**overrides):
    base = {
        "grow_type": "rdwc",
        "grow_size": "3x3",
        CONF_TUYA_ENABLED: True,
        CONF_TUYA_ACCESS_ID: "",
        CONF_TUYA_REGION: "us",
        CONF_TUYA_UID: "",
        CONF_TUYA_DEVICE_IDS: "",
        CONF_TUYA_SCAN_INTERVAL: 60,
        "ai_health_interval_hours": 12,
        "ai_severe_threshold": 20,
        "ai_result_retention_days": 30,
        "timelapse_enabled": False,
        "timelapse_interval_hours": 24,
        "timelapse_retention_frames": 30,
        "timelapse_dir": "",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_options_save_keeps_ph_when_water_roles_hidden() -> None:
    entry = SimpleNamespace(
        data={
            "grow_type": "rdwc",
            "grow_size": "3x3",
            CONF_SENSOR_MAPPINGS: {SENSOR_ROLE_PH: "sensor.stored_ph"},
            CONF_CONTROL_MAPPINGS: {},
            CONF_TUYA_ENABLED: True,
        },
        options={},
    )
    flow = TendrilGrowOptionsFlow(entry)
    _patch_create_entry(flow)

    result = await flow.async_step_init(
        _minimal_options_payload(temperature="sensor.temp_only")
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_SENSOR_MAPPINGS][SENSOR_ROLE_PH] == "sensor.stored_ph"
    assert result["data"][CONF_SENSOR_MAPPINGS]["temperature"] == "sensor.temp_only"


@pytest.mark.asyncio
async def test_options_save_blank_secret_and_device_keep_stored() -> None:
    entry = SimpleNamespace(
        data={
            "grow_type": "rdwc",
            CONF_SENSOR_MAPPINGS: {},
            CONF_CONTROL_MAPPINGS: {},
            CONF_TUYA_ENABLED: False,
            CONF_TUYA_ACCESS_SECRET: "stored-secret",
            CONF_TUYA_ACCESS_ID: "stored-access",
            CONF_TUYA_DEVICE_IDS: ["dev-abc"],
            CONF_WATER_MONITOR_DEVICE_ID: "ha-device-bound",
        },
        options={},
    )
    flow = TendrilGrowOptionsFlow(entry)
    _patch_create_entry(flow)

    result = await flow.async_step_init(
        _minimal_options_payload(
            CONF_TUYA_ENABLED=False,
            CONF_TUYA_ACCESS_SECRET="",
            CONF_TUYA_ACCESS_ID="",
            CONF_TUYA_DEVICE_IDS="",
            CONF_WATER_MONITOR_DEVICE_ID="",
        )
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_TUYA_ACCESS_SECRET] == "stored-secret"
    assert result["data"][CONF_TUYA_ACCESS_ID] == "stored-access"
    assert result["data"][CONF_TUYA_DEVICE_IDS] == ["dev-abc"]
    assert result["data"][CONF_WATER_MONITOR_DEVICE_ID] == "ha-device-bound"


@pytest.mark.asyncio
async def test_pump_mapped_only_in_options_creates_switch() -> None:
    entry = SimpleNamespace(
        entry_id="test-entry",
        title="Tent A",
        data={
            "sensor_mappings": {},
            "control_mappings": {},
        },
        options={
            CONF_CONTROL_MAPPINGS: {
                CONTROL_ROLE_RDWC_PUMP: "switch.rdwc_from_options",
            },
        },
    )
    hass = MagicMock()
    hass.states.get = MagicMock(return_value=SimpleNamespace(state="off"))
    async_add_entities = AsyncMock()

    await async_setup_entry(hass, entry, async_add_entities)

    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 1
    assert entities[0]._mapped_entity_id == "switch.rdwc_from_options"


@pytest.mark.asyncio
async def test_auto_bind_does_not_replace_existing_water_monitor_device() -> None:
    from unittest.mock import patch

    from custom_components.tendrilgrow.const import LOCALTUYA_DOMAIN

    entry = SimpleNamespace(
        entry_id="entry-1",
        data={
            CONF_WATER_MONITOR_DEVICE_ID: "stored-device",
            CONF_TUYA_DEVICE_IDS: ["tuya-1"],
        },
        options={},
    )
    hass = MagicMock()
    hass.config_entries.async_update_entry = Mock()
    stored_device = SimpleNamespace(identifiers={(LOCALTUYA_DOMAIN, "tuya-1")})
    device_registry = MagicMock()
    device_registry.async_get = Mock(return_value=stored_device)

    with patch(
        "custom_components.tendrilgrow.local_water_source.dr.async_get",
        return_value=device_registry,
    ), patch(
        "custom_components.tendrilgrow.local_water_source.find_unique_local_match",
        Mock(return_value=("other-device", LOCALTUYA_DOMAIN)),
    ) as find_match:
        result = await async_resolve_water_monitor_device(hass, entry, persist=True)

    assert result == ("stored-device", LOCALTUYA_DOMAIN)
    find_match.assert_not_called()
    hass.config_entries.async_update_entry.assert_not_called()
