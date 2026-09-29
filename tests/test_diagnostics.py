"""Tests for diagnostics redaction."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.tendrilgrow.const import CONF_WATER_MONITOR_DEVICE_ID
from custom_components.tendrilgrow.diagnostics import async_get_config_entry_diagnostics


@pytest.mark.asyncio
async def test_diagnostics_redacts_api_key() -> None:
    entry = SimpleNamespace(
        entry_id="123",
        title="Tent A",
        data={
            "api_key": "secret",
            "grow_space_name": "Tent A",
            "tuya_access_secret": "tuya-secret",
            CONF_WATER_MONITOR_DEVICE_ID: "ha-device-1",
        },
        options={"api_key": "another-secret"},
    )

    runtime = SimpleNamespace(
        auto_mapped_sensor_roles={"ph": "sensor.tuya_ph"},
        grow_space=SimpleNamespace(
            sensor_mappings={"ph": "sensor.tuya_ph", "ec": "sensor.tuya_ec"}
        ),
    )
    hass = SimpleNamespace(data={"tendrilgrow": {"123": runtime}})

    with patch(
        "custom_components.tendrilgrow.diagnostics.effective_water_source",
        return_value="localtuya",
    ):
        payload = await async_get_config_entry_diagnostics(hass=hass, entry=entry)

    assert payload["data"]["api_key"] == "**REDACTED**"
    assert payload["options"]["api_key"] == "**REDACTED**"
    assert payload["data"]["tuya_access_secret"] == "**REDACTED**"
    assert payload["runtime"]["auto_mapped_sensor_roles"]["ph"] == "sensor.tuya_ph"
    assert payload["runtime"]["effective_sensor_mappings"]["ec"] == "sensor.tuya_ec"
    assert payload["water_source"] == "localtuya"
    assert payload[CONF_WATER_MONITOR_DEVICE_ID] == "ha-device-1"


@pytest.mark.asyncio
async def test_diagnostics_omits_raw_response() -> None:
    entry = SimpleNamespace(
        entry_id="123",
        title="Tent A",
        data={"grow_space_name": "Tent A"},
        options={},
    )
    latest_result = SimpleNamespace(
        to_dict=lambda: {
            "score": 85,
            "summary": "Looks good",
            "raw_response": "SECRET_OR_LARGE_RAW_MODEL_OUTPUT",
        }
    )
    ai_state = SimpleNamespace(
        running=False,
        last_error="",
        history=[latest_result],
        latest=latest_result,
    )
    runtime = SimpleNamespace(
        auto_mapped_sensor_roles={},
        grow_space=SimpleNamespace(sensor_mappings={}, control_mappings={}),
        ai_health_state=ai_state,
    )
    hass = SimpleNamespace(data={"tendrilgrow": {"123": runtime}})

    payload = await async_get_config_entry_diagnostics(hass=hass, entry=entry)
    ai_health = payload["runtime"]["ai_health"]
    assert "raw_response" not in ai_health["latest"]
    assert ai_health["latest"]["score"] == 85
