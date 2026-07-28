"""Smoke tests for config-entry lifecycle."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.tendrilgrow import (
    SERVICE_REBUILD_AUTOMAP,
    async_setup_entry,
    async_unload_entry,
)


@pytest.mark.asyncio
async def test_setup_and_unload_entry_lifecycle() -> None:
    unsub = Mock()
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Tent A",
        data={
            "space_id": "space-1",
            "name": "Tent A",
            "grow_type": "rdwc",
            "descriptor": "3x3",
            "sites": [],
            "sensor_mappings": {},
            "control_mappings": {},
            "targets": {},
            "schedules": {},
        },
        add_update_listener=Mock(return_value=unsub),
    )

    hass = SimpleNamespace(
        data={},
        config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(return_value=True),
            async_unload_platforms=AsyncMock(return_value=True),
            async_reload=AsyncMock(return_value=True),
        ),
        services=SimpleNamespace(async_register=Mock(), async_remove=Mock()),
    )

    assert await async_setup_entry(hass, entry)
    assert "entry-1" in hass.data["tendrilgrow"]
    hass.services.async_register.assert_called_once()

    assert await async_unload_entry(hass, entry)
    assert "entry-1" not in hass.data["tendrilgrow"]
    unsub.assert_called_once()
    hass.services.async_remove.assert_called_once_with("tendrilgrow", SERVICE_REBUILD_AUTOMAP)


@pytest.mark.asyncio
async def test_rebuild_automap_service_reloads_entries() -> None:
    unsub = Mock()
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Tent A",
        data={
            "space_id": "space-1",
            "name": "Tent A",
            "grow_type": "rdwc",
            "descriptor": "3x3",
            "sites": [],
            "sensor_mappings": {},
            "control_mappings": {},
            "targets": {},
            "schedules": {},
        },
        add_update_listener=Mock(return_value=unsub),
    )

    services = SimpleNamespace(async_register=Mock(), async_remove=Mock())
    hass = SimpleNamespace(
        data={},
        config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(return_value=True),
            async_unload_platforms=AsyncMock(return_value=True),
            async_reload=AsyncMock(return_value=True),
        ),
        services=services,
    )

    assert await async_setup_entry(hass, entry)

    handler = services.async_register.call_args.args[2]
    await handler(SimpleNamespace(data={}))
    hass.config_entries.async_reload.assert_called_with("entry-1")

    with pytest.raises(HomeAssistantError):
        await handler(SimpleNamespace(data={"entry_id": "missing"}))
