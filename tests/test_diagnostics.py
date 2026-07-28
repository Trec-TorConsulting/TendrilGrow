"""Tests for diagnostics redaction."""

from types import SimpleNamespace

import pytest

from custom_components.tendrilgrow.diagnostics import async_get_config_entry_diagnostics


@pytest.mark.asyncio
async def test_diagnostics_redacts_api_key() -> None:
    entry = SimpleNamespace(
        entry_id="123",
        title="Tent A",
        data={"api_key": "secret", "grow_space_name": "Tent A"},
        options={"api_key": "another-secret"},
    )

    runtime = SimpleNamespace(
        auto_mapped_sensor_roles={"ph": "sensor.tuya_ph"},
        grow_space=SimpleNamespace(
            sensor_mappings={"ph": "sensor.tuya_ph", "ec": "sensor.tuya_ec"}
        ),
    )
    hass = SimpleNamespace(data={"tendrilgrow": {"123": runtime}})

    payload = await async_get_config_entry_diagnostics(hass=hass, entry=entry)

    assert payload["data"]["api_key"] == "**REDACTED**"
    assert payload["options"]["api_key"] == "**REDACTED**"
    assert payload["runtime"]["auto_mapped_sensor_roles"]["ph"] == "sensor.tuya_ph"
    assert payload["runtime"]["effective_sensor_mappings"]["ec"] == "sensor.tuya_ec"
