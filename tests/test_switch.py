"""Tests for pump proxy switches."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.tendrilgrow.const import (
    CONTROL_ROLE_AIR_PUMP,
    CONTROL_ROLE_CHILLER_PUMP,
    CONTROL_ROLE_RDWC_PUMP,
)
from custom_components.tendrilgrow.switch import (
    TendrilGrowPumpSwitch,
    async_setup_entry,
)


@pytest.mark.asyncio
async def test_pump_switch_mirrors_mapped_entity_state() -> None:
    """Verify pump switch mirrors the state of the mapped entity."""
    hass = SimpleNamespace(
        states=SimpleNamespace(get=MagicMock(return_value=SimpleNamespace(state="on"))),
    )

    entry = SimpleNamespace(entry_id="test-entry", title="Tent A")

    switch = TendrilGrowPumpSwitch(
        hass,
        entry,
        CONTROL_ROLE_RDWC_PUMP,
        "switch.rdwc_pump",
    )

    # When mapped entity is on.
    hass.states.get = MagicMock(return_value=SimpleNamespace(state="on"))
    assert switch.is_on is True
    assert switch.available is True

    # When mapped entity is off.
    hass.states.get = MagicMock(return_value=SimpleNamespace(state="off"))
    assert switch.is_on is False
    assert switch.available is True

    # When mapped entity is unavailable.
    hass.states.get = MagicMock(return_value=SimpleNamespace(state="unavailable"))
    assert switch.is_on is False
    assert switch.available is False

    # When mapped entity does not exist.
    hass.states.get = MagicMock(return_value=None)
    assert switch.is_on is False
    assert switch.available is False


@pytest.mark.asyncio
async def test_pump_switch_routes_turn_on_to_switch_domain() -> None:
    """Verify turn_on routes to switch service for switch entities."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.states.get = MagicMock(return_value=SimpleNamespace(state="off"))

    entry = SimpleNamespace(entry_id="test-entry", title="Tent A")

    switch = TendrilGrowPumpSwitch(
        hass, entry, CONTROL_ROLE_RDWC_PUMP, "switch.rdwc_pump"
    )

    # Mock state change event handler.
    switch.async_write_ha_state = MagicMock()

    await switch.async_turn_on()

    # Verify switch service was called.
    hass.services.async_call.assert_called_once_with(
        "switch",
        "turn_on",
        {"entity_id": "switch.rdwc_pump"},
    )


@pytest.mark.asyncio
async def test_pump_switch_routes_turn_on_to_input_boolean_domain() -> None:
    """Verify turn_on routes to input_boolean service for input_boolean entities."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.states.get = MagicMock(return_value=SimpleNamespace(state="off"))

    entry = SimpleNamespace(entry_id="test-entry", title="Tent A")

    switch = TendrilGrowPumpSwitch(
        hass,
        entry,
        CONTROL_ROLE_CHILLER_PUMP,
        "input_boolean.chiller_pump",
    )

    switch.async_write_ha_state = MagicMock()

    await switch.async_turn_on()

    # Verify input_boolean service was called.
    hass.services.async_call.assert_called_once_with(
        "input_boolean",
        "turn_on",
        {"entity_id": "input_boolean.chiller_pump"},
    )


@pytest.mark.asyncio
async def test_pump_switch_toggle() -> None:
    """Verify toggle action works correctly."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.states.get = MagicMock(return_value=SimpleNamespace(state="on"))

    entry = SimpleNamespace(entry_id="test-entry", title="Tent A")

    switch = TendrilGrowPumpSwitch(
        hass, entry, CONTROL_ROLE_AIR_PUMP, "switch.air_pump"
    )

    switch.async_write_ha_state = MagicMock()

    await switch.async_toggle()

    hass.services.async_call.assert_called_once_with(
        "switch",
        "toggle",
        {"entity_id": "switch.air_pump"},
    )


@pytest.mark.asyncio
async def test_async_setup_entry_creates_switches_for_mapped_pumps() -> None:
    """Verify async_setup_entry creates proxy switches for all mapped pumps."""
    entry = SimpleNamespace(
        entry_id="test-entry",
        title="Tent A",
        data={
            "space_id": "space-1",
            "name": "Tent A",
            "grow_type": "rdwc",
            "descriptor": "3x3",
            "sites": [],
            "sensor_mappings": {},
            "control_mappings": {
                CONTROL_ROLE_RDWC_PUMP: "switch.rdwc_pump",
                CONTROL_ROLE_CHILLER_PUMP: "switch.chiller_pump",
                # Air pump not mapped, should not create a switch.
            },
            "targets": {},
            "schedules": {},
        },
    )

    hass = MagicMock()
    hass.states.get = MagicMock(return_value=SimpleNamespace(state="off"))

    async_add_entities = AsyncMock()

    await async_setup_entry(hass, entry, async_add_entities)

    # Should have created 2 switches (RDWC and Chiller).
    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 2
    assert all(isinstance(e, TendrilGrowPumpSwitch) for e in entities)
