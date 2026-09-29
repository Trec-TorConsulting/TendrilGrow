"""Unit tests for TendrilGrow water safety monitoring."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.const import STATE_OFF, STATE_ON

from custom_components.tendrilgrow.const import (
    CONF_LEAK_DEBOUNCE_SECONDS,
    CONF_LEAK_SHUTOFF_ENABLED,
    CONF_NO_FLOW_GRACE_SECONDS,
    CONTROL_ROLE_RDWC_PUMP,
    DOMAIN,
    SENSOR_ROLE_LEAK,
    SENSOR_ROLE_WATER_FLOW,
    WATER_SAFETY_STATUS_LEAK,
    WATER_SAFETY_STATUS_NO_FLOW,
    WATER_SAFETY_STATUS_OK,
)
from custom_components.tendrilgrow.models.grow import GrowSpace
from custom_components.tendrilgrow.water_safety import (
    WaterSafetyMonitor,
    parse_leak_entities,
)


def test_parse_leak_entities() -> None:
    assert parse_leak_entities(None) == []
    assert parse_leak_entities("") == []
    assert parse_leak_entities("binary_sensor.leak1") == ["binary_sensor.leak1"]
    assert parse_leak_entities("binary_sensor.leak1, binary_sensor.leak2") == [
        "binary_sensor.leak1",
        "binary_sensor.leak2",
    ]
    assert parse_leak_entities(["binary_sensor.leak1", "binary_sensor.leak2"]) == [
        "binary_sensor.leak1",
        "binary_sensor.leak2",
    ]


@pytest.fixture
def mock_hass():
    states = {}
    bus_events = []

    def get_state(entity_id):
        return states.get(entity_id)

    def async_fire(event_name, data):
        bus_events.append((event_name, data))

    def async_listen(event_type, listener, event_filter=None):
        return lambda: None

    hass = SimpleNamespace(
        states=SimpleNamespace(get=get_state, _data=states),
        bus=SimpleNamespace(
            async_fire=async_fire,
            async_listen=async_listen,
            _events=bus_events,
        ),
        services=SimpleNamespace(async_call=AsyncMock()),
        async_create_task=Mock(side_effect=lambda coro: asyncio.create_task(coro)),
        verify_event_loop_thread=Mock(),
        data={DOMAIN: {}},
    )
    return hass


@pytest.mark.asyncio
async def test_water_safety_idle_when_pump_off(mock_hass) -> None:
    grow_space = GrowSpace.new("Tent A", "rdwc")
    grow_space.sensor_mappings[SENSOR_ROLE_WATER_FLOW] = "sensor.water_flow"
    grow_space.sensor_mappings[SENSOR_ROLE_LEAK] = "binary_sensor.tent_leak"
    grow_space.control_mappings[CONTROL_ROLE_RDWC_PUMP] = "switch.rdwc_pump"

    mock_hass.states._data["switch.rdwc_pump"] = SimpleNamespace(state=STATE_OFF)
    mock_hass.states._data["sensor.water_flow"] = SimpleNamespace(state="0.0")
    mock_hass.states._data["binary_sensor.tent_leak"] = SimpleNamespace(state=STATE_OFF)

    entry = SimpleNamespace(entry_id="entry-1")
    config = {
        CONF_NO_FLOW_GRACE_SECONDS: 60,
        CONF_LEAK_DEBOUNCE_SECONDS: 5,
        CONF_LEAK_SHUTOFF_ENABLED: True,
    }

    monitor = WaterSafetyMonitor(mock_hass, entry, grow_space, config)
    await monitor.async_start()

    assert monitor.flow_ok is True
    assert monitor.leak_detected is False
    assert monitor.status == WATER_SAFETY_STATUS_OK
    assert monitor.active_leaks == []


@pytest.mark.asyncio
async def test_flow_verification_success_when_pump_on_and_flowing(mock_hass) -> None:
    grow_space = GrowSpace.new("Tent A", "rdwc")
    grow_space.sensor_mappings[SENSOR_ROLE_WATER_FLOW] = "sensor.water_flow"
    grow_space.control_mappings[CONTROL_ROLE_RDWC_PUMP] = "switch.rdwc_pump"

    mock_hass.states._data["switch.rdwc_pump"] = SimpleNamespace(state=STATE_ON)
    mock_hass.states._data["sensor.water_flow"] = SimpleNamespace(state="2.5")

    entry = SimpleNamespace(entry_id="entry-1")
    monitor = WaterSafetyMonitor(mock_hass, entry, grow_space, {})
    await monitor.async_start()

    assert monitor.flow_ok is True
    assert monitor.status == WATER_SAFETY_STATUS_OK
    assert monitor.flow_rate == 2.5


@pytest.mark.asyncio
async def test_flow_verification_failure_after_grace(mock_hass) -> None:
    grow_space = GrowSpace.new("Tent A", "rdwc")
    grow_space.sensor_mappings[SENSOR_ROLE_WATER_FLOW] = "sensor.water_flow"
    grow_space.control_mappings[CONTROL_ROLE_RDWC_PUMP] = "switch.rdwc_pump"

    mock_hass.states._data["switch.rdwc_pump"] = SimpleNamespace(state=STATE_ON)
    mock_hass.states._data["sensor.water_flow"] = SimpleNamespace(state="0.0")

    entry = SimpleNamespace(entry_id="entry-1")
    config = {CONF_NO_FLOW_GRACE_SECONDS: 0}  # Immediate for test

    monitor = WaterSafetyMonitor(mock_hass, entry, grow_space, config)
    await monitor.async_start()

    assert monitor.flow_ok is False
    assert monitor.status == WATER_SAFETY_STATUS_NO_FLOW

    # Resuming flow restores flow_ok
    mock_hass.states._data["sensor.water_flow"] = SimpleNamespace(state="1.8")
    monitor._evaluate_state()

    assert monitor.flow_ok is True
    assert monitor.status == WATER_SAFETY_STATUS_OK


@pytest.mark.asyncio
async def test_leak_detection_multiple_sensors_and_precedence(mock_hass) -> None:
    grow_space = GrowSpace.new("Tent A", "rdwc")
    grow_space.sensor_mappings[SENSOR_ROLE_WATER_FLOW] = "sensor.water_flow"
    grow_space.sensor_mappings[SENSOR_ROLE_LEAK] = (
        "binary_sensor.tent_floor, binary_sensor.chiller_pan"
    )
    grow_space.control_mappings[CONTROL_ROLE_RDWC_PUMP] = "switch.rdwc_pump"

    # Pump on with no flow (would be no_flow)
    mock_hass.states._data["switch.rdwc_pump"] = SimpleNamespace(state=STATE_ON)
    mock_hass.states._data["sensor.water_flow"] = SimpleNamespace(state="0.0")
    # But one leak sensor trips
    mock_hass.states._data["binary_sensor.tent_floor"] = SimpleNamespace(
        state=STATE_OFF
    )
    mock_hass.states._data["binary_sensor.chiller_pan"] = SimpleNamespace(
        state=STATE_ON
    )

    entry = SimpleNamespace(entry_id="entry-1")
    config = {
        CONF_NO_FLOW_GRACE_SECONDS: 0,
        CONF_LEAK_DEBOUNCE_SECONDS: 0,
        CONF_LEAK_SHUTOFF_ENABLED: False,
    }

    monitor = WaterSafetyMonitor(mock_hass, entry, grow_space, config)
    await monitor.async_start()

    assert monitor.leak_detected is True
    assert monitor.active_leaks == ["binary_sensor.chiller_pan"]
    assert monitor.flow_ok is False
    # Leak takes precedence over no_flow
    assert monitor.status == WATER_SAFETY_STATUS_LEAK


@pytest.mark.asyncio
async def test_opt_in_pump_shutoff_on_leak(mock_hass) -> None:
    grow_space = GrowSpace.new("Tent A", "rdwc")
    grow_space.sensor_mappings[SENSOR_ROLE_LEAK] = "binary_sensor.tent_floor"
    grow_space.control_mappings[CONTROL_ROLE_RDWC_PUMP] = "switch.tent_rdwc_pump"

    mock_hass.states._data["switch.tent_rdwc_pump"] = SimpleNamespace(state=STATE_ON)
    mock_hass.states._data["binary_sensor.tent_floor"] = SimpleNamespace(state=STATE_ON)

    tasks = []

    def _track_task(coro):
        tasks.append(coro)
        return coro

    mock_hass.async_create_task = Mock(side_effect=_track_task)

    entry = SimpleNamespace(entry_id="entry-1")
    config = {
        CONF_LEAK_DEBOUNCE_SECONDS: 0,
        CONF_LEAK_SHUTOFF_ENABLED: True,
    }

    monitor = WaterSafetyMonitor(mock_hass, entry, grow_space, config)
    await monitor.async_start()

    assert monitor.leak_detected is True
    assert monitor.shutoff_triggered is True
    mock_hass.async_create_task.assert_called_once()
    assert len(tasks) == 1
    await tasks[0]

    mock_hass.services.async_call.assert_awaited_once_with(
        "switch",
        "turn_off",
        {"entity_id": "switch.tent_rdwc_pump"},
        blocking=False,
    )


@pytest.mark.asyncio
async def test_pump_shutoff_disabled_does_not_call_service(mock_hass) -> None:
    grow_space = GrowSpace.new("Tent A", "rdwc")
    grow_space.sensor_mappings[SENSOR_ROLE_LEAK] = "binary_sensor.tent_floor"
    grow_space.control_mappings[CONTROL_ROLE_RDWC_PUMP] = "switch.tent_rdwc_pump"

    mock_hass.states._data["binary_sensor.tent_floor"] = SimpleNamespace(state=STATE_ON)

    entry = SimpleNamespace(entry_id="entry-1")
    config = {
        CONF_LEAK_DEBOUNCE_SECONDS: 0,
        CONF_LEAK_SHUTOFF_ENABLED: False,  # Disabled
    }

    monitor = WaterSafetyMonitor(mock_hass, entry, grow_space, config)
    await monitor.async_start()

    assert monitor.leak_detected is True
    assert monitor.shutoff_triggered is False
    mock_hass.services.async_call.assert_not_called()
