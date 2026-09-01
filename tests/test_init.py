"""Smoke tests for config-entry lifecycle."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

import custom_components.tendrilgrow as tg
from custom_components.tendrilgrow import (
    SERVICE_BUILD_TIMELAPSE,
    SERVICE_CAPTURE_TIMELAPSE_FRAME,
    SERVICE_MARK_FLUSH,
    SERVICE_REBUILD_AUTOMAP,
    SERVICE_RUN_AI_HEALTH_CHECK,
    SERVICE_SET_PUMP,
    _migrate_ai_entity_ids,
    _migrate_stage_clock_entity_ids,
    async_setup_entry,
    async_unload_entry,
    rewrite_lovelace_stage_clock,
)


def _consume_task(coro):
    coro.close()


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
        async_create_task=Mock(side_effect=_consume_task),
        services=SimpleNamespace(async_register=Mock(), async_remove=Mock()),
    )

    assert await async_setup_entry(hass, entry)
    assert "entry-1" in hass.data["tendrilgrow"]
    assert hass.services.async_register.call_count == 6

    assert await async_unload_entry(hass, entry)
    assert "entry-1" not in hass.data["tendrilgrow"]
    unsub.assert_called_once()
    hass.services.async_remove.assert_any_call("tendrilgrow", SERVICE_REBUILD_AUTOMAP)
    hass.services.async_remove.assert_any_call(
        "tendrilgrow", SERVICE_RUN_AI_HEALTH_CHECK
    )
    hass.services.async_remove.assert_any_call("tendrilgrow", SERVICE_SET_PUMP)
    hass.services.async_remove.assert_any_call("tendrilgrow", SERVICE_MARK_FLUSH)
    hass.services.async_remove.assert_any_call(
        "tendrilgrow", SERVICE_CAPTURE_TIMELAPSE_FRAME
    )
    hass.services.async_remove.assert_any_call("tendrilgrow", SERVICE_BUILD_TIMELAPSE)


@pytest.mark.asyncio
async def test_setup_entry_does_not_start_timelapse_scheduler_when_disabled() -> None:
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
        async_create_task=Mock(side_effect=_consume_task),
        services=SimpleNamespace(async_register=Mock(), async_remove=Mock()),
    )

    assert await async_setup_entry(hass, entry)
    runtime = hass.data["tendrilgrow"]["entry-1"]
    assert runtime.unsubscribe_timelapse_scheduler is None


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
        async_create_task=Mock(side_effect=_consume_task),
        services=services,
    )

    assert await async_setup_entry(hass, entry)

    handlers_by_service = {
        call.args[1]: call.args[2] for call in services.async_register.call_args_list
    }
    handler = handlers_by_service[SERVICE_REBUILD_AUTOMAP]
    await handler(SimpleNamespace(data={}))
    hass.config_entries.async_reload.assert_called_with("entry-1")

    with pytest.raises(HomeAssistantError):
        await handler(SimpleNamespace(data={"entry_id": "missing"}))


@pytest.mark.asyncio
async def test_set_pump_service_routes_to_switch() -> None:
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
            "control_mappings": {"rdwc_pump": "switch.pump_1"},
            "targets": {},
            "schedules": {},
        },
        add_update_listener=Mock(return_value=unsub),
    )

    services = SimpleNamespace(async_register=Mock(), async_remove=Mock())
    hass = SimpleNamespace(
        data={},
        states=SimpleNamespace(
            get=Mock(return_value=SimpleNamespace(state="on", attributes={}))
        ),
        config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(return_value=True),
            async_unload_platforms=AsyncMock(return_value=True),
            async_reload=AsyncMock(return_value=True),
        ),
        async_create_task=Mock(side_effect=_consume_task),
        services=SimpleNamespace(
            async_call=AsyncMock(),
            async_register=services.async_register,
            async_remove=services.async_remove,
        ),
    )

    assert await async_setup_entry(hass, entry)

    handlers_by_service = {
        call.args[1]: call.args[2] for call in services.async_register.call_args_list
    }
    handler = handlers_by_service[SERVICE_SET_PUMP]
    await handler(
        SimpleNamespace(
            data={"entry_id": "entry-1", "pump": "rdwc_pump", "action": "on"}
        )
    )
    hass.services.async_call.assert_called_once_with(
        "switch", "turn_on", {"entity_id": "switch.pump_1"}
    )


@pytest.mark.asyncio
async def test_set_pump_service_routes_to_input_boolean() -> None:
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
            "control_mappings": {"chiller_pump": "input_boolean.chiller"},
            "targets": {},
            "schedules": {},
        },
        add_update_listener=Mock(return_value=unsub),
    )

    services = SimpleNamespace(async_register=Mock(), async_remove=Mock())
    hass = SimpleNamespace(
        data={},
        states=SimpleNamespace(
            get=Mock(return_value=SimpleNamespace(state="off", attributes={}))
        ),
        config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(return_value=True),
            async_unload_platforms=AsyncMock(return_value=True),
            async_reload=AsyncMock(return_value=True),
        ),
        async_create_task=Mock(side_effect=_consume_task),
        services=SimpleNamespace(
            async_call=AsyncMock(),
            async_register=services.async_register,
            async_remove=services.async_remove,
        ),
    )

    assert await async_setup_entry(hass, entry)

    handlers_by_service = {
        call.args[1]: call.args[2] for call in services.async_register.call_args_list
    }
    handler = handlers_by_service[SERVICE_SET_PUMP]
    await handler(
        SimpleNamespace(
            data={"entry_id": "entry-1", "pump": "chiller_pump", "action": "off"}
        )
    )
    hass.services.async_call.assert_called_once_with(
        "input_boolean", "turn_off", {"entity_id": "input_boolean.chiller"}
    )


@pytest.mark.asyncio
async def test_set_pump_service_skip_when_unmapped() -> None:
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
        states=SimpleNamespace(get=Mock()),
        config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(return_value=True),
            async_unload_platforms=AsyncMock(return_value=True),
            async_reload=AsyncMock(return_value=True),
        ),
        async_create_task=Mock(side_effect=_consume_task),
        services=SimpleNamespace(
            async_call=AsyncMock(),
            async_register=services.async_register,
            async_remove=services.async_remove,
        ),
    )

    assert await async_setup_entry(hass, entry)

    handlers_by_service = {
        call.args[1]: call.args[2] for call in services.async_register.call_args_list
    }
    handler = handlers_by_service[SERVICE_SET_PUMP]
    await handler(
        SimpleNamespace(
            data={"entry_id": "entry-1", "pump": "rdwc_pump", "action": "on"}
        )
    )
    # Service should not be called when pump is unmapped
    hass.services.async_call.assert_not_called()
    # But state should not have been checked
    hass.states.get.assert_not_called()


@pytest.mark.asyncio
async def test_set_pump_service_skip_when_unavailable() -> None:
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
            "control_mappings": {"rdwc_pump": "switch.pump_1"},
            "targets": {},
            "schedules": {},
        },
        add_update_listener=Mock(return_value=unsub),
    )

    services = SimpleNamespace(async_register=Mock(), async_remove=Mock())
    hass = SimpleNamespace(
        data={},
        states=SimpleNamespace(
            get=Mock(return_value=SimpleNamespace(state="unavailable", attributes={}))
        ),
        config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(return_value=True),
            async_unload_platforms=AsyncMock(return_value=True),
            async_reload=AsyncMock(return_value=True),
        ),
        async_create_task=Mock(side_effect=_consume_task),
        services=SimpleNamespace(
            async_call=AsyncMock(),
            async_register=services.async_register,
            async_remove=services.async_remove,
        ),
    )

    assert await async_setup_entry(hass, entry)

    handlers_by_service = {
        call.args[1]: call.args[2] for call in services.async_register.call_args_list
    }
    handler = handlers_by_service[SERVICE_SET_PUMP]
    await handler(
        SimpleNamespace(
            data={"entry_id": "entry-1", "pump": "rdwc_pump", "action": "on"}
        )
    )
    # Service should not be called when entity is unavailable
    hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_set_pump_service_toggle_action() -> None:
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
            "control_mappings": {"rdwc_pump": "switch.pump_1"},
            "targets": {},
            "schedules": {},
        },
        add_update_listener=Mock(return_value=unsub),
    )

    services = SimpleNamespace(async_register=Mock(), async_remove=Mock())
    hass = SimpleNamespace(
        data={},
        states=SimpleNamespace(
            get=Mock(return_value=SimpleNamespace(state="on", attributes={}))
        ),
        config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(return_value=True),
            async_unload_platforms=AsyncMock(return_value=True),
            async_reload=AsyncMock(return_value=True),
        ),
        async_create_task=Mock(side_effect=_consume_task),
        services=SimpleNamespace(
            async_call=AsyncMock(),
            async_register=services.async_register,
            async_remove=services.async_remove,
        ),
    )

    assert await async_setup_entry(hass, entry)

    handlers_by_service = {
        call.args[1]: call.args[2] for call in services.async_register.call_args_list
    }
    handler = handlers_by_service[SERVICE_SET_PUMP]
    await handler(
        SimpleNamespace(
            data={"entry_id": "entry-1", "pump": "rdwc_pump", "action": "toggle"}
        )
    )
    hass.services.async_call.assert_called_once_with(
        "switch", "toggle", {"entity_id": "switch.pump_1"}
    )


@pytest.mark.asyncio
async def test_set_pump_service_validation() -> None:
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
            "control_mappings": {"rdwc_pump": "switch.pump_1"},
            "targets": {},
            "schedules": {},
        },
        add_update_listener=Mock(return_value=unsub),
    )

    services = SimpleNamespace(async_register=Mock(), async_remove=Mock())
    hass = SimpleNamespace(
        data={},
        states=SimpleNamespace(get=Mock()),
        config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(return_value=True),
            async_unload_platforms=AsyncMock(return_value=True),
            async_reload=AsyncMock(return_value=True),
        ),
        async_create_task=Mock(side_effect=_consume_task),
        services=SimpleNamespace(
            async_call=AsyncMock(),
            async_register=services.async_register,
            async_remove=services.async_remove,
        ),
    )

    assert await async_setup_entry(hass, entry)

    handlers_by_service = {
        call.args[1]: call.args[2] for call in services.async_register.call_args_list
    }
    handler = handlers_by_service[SERVICE_SET_PUMP]

    # Test missing entry_id
    with pytest.raises(HomeAssistantError):
        await handler(SimpleNamespace(data={"pump": "rdwc_pump", "action": "on"}))

    # Test invalid pump
    with pytest.raises(HomeAssistantError):
        await handler(
            SimpleNamespace(
                data={"entry_id": "entry-1", "pump": "invalid_pump", "action": "on"}
            )
        )

    # Test invalid action
    with pytest.raises(HomeAssistantError):
        await handler(
            SimpleNamespace(
                data={
                    "entry_id": "entry-1",
                    "pump": "rdwc_pump",
                    "action": "invalid",
                }
            )
        )


@pytest.mark.asyncio
async def test_mark_flush_service_records() -> None:
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
        options={},
        add_update_listener=Mock(return_value=unsub),
    )

    services = SimpleNamespace(async_register=Mock(), async_remove=Mock())
    hass = SimpleNamespace(
        data={},
        verify_event_loop_thread=Mock(),
        config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(return_value=True),
            async_unload_platforms=AsyncMock(return_value=True),
            async_reload=AsyncMock(return_value=True),
            async_get_entry=Mock(return_value=entry),
        ),
        async_create_task=Mock(side_effect=_consume_task),
        services=SimpleNamespace(
            async_call=AsyncMock(),
            async_register=services.async_register,
            async_remove=services.async_remove,
        ),
    )

    assert await async_setup_entry(hass, entry)

    runtime = hass.data["tendrilgrow"]["entry-1"]
    assert runtime.flush_state.last_flush is None

    handlers_by_service = {
        call.args[1]: call.args[2] for call in services.async_register.call_args_list
    }
    handler = handlers_by_service[SERVICE_MARK_FLUSH]
    await handler(SimpleNamespace(data={"entry_id": "entry-1"}))

    assert runtime.flush_state.last_flush is not None


@pytest.mark.asyncio
async def test_mark_flush_service_validation() -> None:
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
        options={},
        add_update_listener=Mock(return_value=unsub),
    )

    services = SimpleNamespace(async_register=Mock(), async_remove=Mock())
    hass = SimpleNamespace(
        data={},
        verify_event_loop_thread=Mock(),
        config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(return_value=True),
            async_unload_platforms=AsyncMock(return_value=True),
            async_reload=AsyncMock(return_value=True),
            async_get_entry=Mock(return_value=None),
        ),
        async_create_task=Mock(side_effect=_consume_task),
        services=SimpleNamespace(
            async_call=AsyncMock(),
            async_register=services.async_register,
            async_remove=services.async_remove,
        ),
    )

    assert await async_setup_entry(hass, entry)

    handlers_by_service = {
        call.args[1]: call.args[2] for call in services.async_register.call_args_list
    }
    handler = handlers_by_service[SERVICE_MARK_FLUSH]

    # Missing entry_id
    with pytest.raises(HomeAssistantError):
        await handler(SimpleNamespace(data={}))

    # Unknown/unloaded entry
    with pytest.raises(HomeAssistantError):
        await handler(SimpleNamespace(data={"entry_id": "missing"}))


@pytest.mark.asyncio
async def test_capture_timelapse_service_invokes_single_capture() -> None:
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
            "sensor_mappings": {"camera": "camera.tent_a"},
            "control_mappings": {},
            "targets": {},
            "schedules": {},
        },
        options={},
        add_update_listener=Mock(return_value=unsub),
    )

    services = SimpleNamespace(async_register=Mock(), async_remove=Mock())
    hass = SimpleNamespace(
        data={},
        config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(return_value=True),
            async_unload_platforms=AsyncMock(return_value=True),
            async_reload=AsyncMock(return_value=True),
            async_get_entry=Mock(return_value=entry),
        ),
        async_create_task=Mock(side_effect=_consume_task),
        services=SimpleNamespace(
            async_call=AsyncMock(),
            async_register=services.async_register,
            async_remove=services.async_remove,
        ),
    )

    assert await async_setup_entry(hass, entry)

    handlers_by_service = {
        call.args[1]: call.args[2] for call in services.async_register.call_args_list
    }
    handler = handlers_by_service[SERVICE_CAPTURE_TIMELAPSE_FRAME]
    with patch.object(tg, "_async_capture_timelapse_frame", AsyncMock()) as capture:
        await handler(SimpleNamespace(data={"entry_id": "entry-1"}))
        capture.assert_awaited_once()


def test_migrate_ai_entity_ids_renames_generic_to_per_tent() -> None:
    """Legacy generic AI ids migrate to per-grow-space ids (incl. _2 dedup)."""
    current_ids = {
        ("sensor", "tendrilgrow", "e1_ai_health_score"): "sensor.ai_health_score",
        ("sensor", "tendrilgrow", "e1_ai_health_summary"): ("sensor.ai_health_summary"),
        ("sensor", "tendrilgrow", "e1_ai_health_last_check"): (
            "sensor.ai_last_health_check_2"
        ),
        ("binary_sensor", "tendrilgrow", "e1_ai_health_critical_alert"): (
            "binary_sensor.ai_health_critical_alert"
        ),
        ("button", "tendrilgrow", "e1_run_ai_health_check"): (
            "button.run_ai_health_check_2"
        ),
    }
    registry = Mock()
    registry.async_get_entity_id.side_effect = lambda d, p, u: current_ids.get(
        (d, p, u)
    )
    registry.async_get.return_value = None
    registry.async_update_entity = Mock()

    entry = SimpleNamespace(entry_id="e1", title="3x3 Mothers Tent")
    with patch.object(tg.er, "async_get", return_value=registry):
        _migrate_ai_entity_ids(SimpleNamespace(), entry)

    renames = {
        call.args[0]: call.kwargs["new_entity_id"]
        for call in registry.async_update_entity.call_args_list
    }
    assert renames["sensor.ai_health_score"] == (
        "sensor.3x3_mothers_tent_ai_health_score"
    )
    assert renames["sensor.ai_last_health_check_2"] == (
        "sensor.3x3_mothers_tent_ai_last_health_check"
    )
    assert renames["button.run_ai_health_check_2"] == (
        "button.3x3_mothers_tent_run_ai_health_check"
    )


def test_migrate_ai_entity_ids_skips_customized_and_taken() -> None:
    """Customized ids are left alone and taken targets are not overwritten."""
    # Customized id (not the auto-generated name) must be preserved.
    customized = {
        ("sensor", "tendrilgrow", "e1_ai_health_score"): "sensor.my_custom_score",
    }
    registry = Mock()
    registry.async_get_entity_id.side_effect = lambda d, p, u: customized.get((d, p, u))
    registry.async_get.return_value = None
    registry.async_update_entity = Mock()

    entry = SimpleNamespace(entry_id="e1", title="Tent A")
    with patch.object(tg.er, "async_get", return_value=registry):
        _migrate_ai_entity_ids(SimpleNamespace(), entry)

    registry.async_update_entity.assert_not_called()


def test_migrate_stage_clock_entity_ids_uses_growth_stage_prefix() -> None:
    """Generic date.stage_started becomes date.<grow>_stage_started."""
    current_ids = {
        ("select", "tendrilgrow", "e1_ctx_stage"): "select.clone_growth_stage",
        ("date", "tendrilgrow", "e1_ctx_stage_started"): "date.stage_started",
        ("sensor", "tendrilgrow", "e1_ctx_week_in_stage"): "sensor.week_in_stage_2",
    }
    registry = Mock()
    registry.async_get_entity_id.side_effect = lambda d, p, u: current_ids.get(
        (d, p, u)
    )
    registry.async_get.return_value = None
    registry.async_update_entity = Mock()

    entry = SimpleNamespace(entry_id="e1", title="Basement Clone")
    hass = SimpleNamespace(data={"tendrilgrow": {}})
    with (
        patch.object(tg.er, "async_get", return_value=registry),
        patch(
            "custom_components.tendrilgrow.entity.er.async_get",
            return_value=registry,
        ),
    ):
        _migrate_stage_clock_entity_ids(hass, entry)

    renames = {
        call.args[0]: call.kwargs["new_entity_id"]
        for call in registry.async_update_entity.call_args_list
    }
    assert renames["date.stage_started"] == "date.clone_stage_started"
    assert renames["sensor.week_in_stage_2"] == "sensor.clone_week_in_stage"


def test_rewrite_lovelace_replaces_retired_week_number() -> None:
    """Cultivation Plan number.week_in_stage becomes date + computed sensor."""
    config = {
        "views": [
            {
                "cards": [
                    {
                        "type": "entities",
                        "title": "Cultivation Plan",
                        "entities": [
                            "select.3x3_mothers_tent_growth_stage",
                            "number.3x3_mothers_tent_week_in_stage",
                            "number.3x3_mothers_tent_target_ph",
                        ],
                    },
                    {
                        "type": "markdown",
                        "content": (
                            "{{ states('number.3x3_mothers_tent_week_in_stage') }}"
                        ),
                    },
                ]
            }
        ]
    }
    updated, changed = rewrite_lovelace_stage_clock(
        config,
        {
            "number.3x3_mothers_tent_week_in_stage": [
                "date.3x3_mothers_tent_stage_started",
                "sensor.3x3_mothers_tent_week_in_stage",
            ]
        },
        {
            "number.3x3_mothers_tent_week_in_stage": (
                "sensor.3x3_mothers_tent_week_in_stage"
            )
        },
    )
    assert changed is True
    entities = updated["views"][0]["cards"][0]["entities"]
    assert entities == [
        "select.3x3_mothers_tent_growth_stage",
        "date.3x3_mothers_tent_stage_started",
        "sensor.3x3_mothers_tent_week_in_stage",
        "number.3x3_mothers_tent_target_ph",
    ]
    assert "number.3x3_mothers_tent_week_in_stage" not in entities
    assert (
        "sensor.3x3_mothers_tent_week_in_stage"
        in updated["views"][0]["cards"][1]["content"]
    )


def test_rewrite_lovelace_does_not_duplicate_existing_date() -> None:
    """Already-migrated Cultivation Plan cards stay a single date + week pair."""
    config = {
        "entities": [
            "date.3x3_mothers_tent_stage_started",
            "sensor.3x3_mothers_tent_week_in_stage",
            "number.3x3_mothers_tent_week_in_stage",
        ]
    }
    updated, changed = rewrite_lovelace_stage_clock(
        config,
        {
            "number.3x3_mothers_tent_week_in_stage": [
                "date.3x3_mothers_tent_stage_started",
                "sensor.3x3_mothers_tent_week_in_stage",
            ]
        },
        {},
    )
    assert changed is True
    assert updated["entities"] == [
        "date.3x3_mothers_tent_stage_started",
        "sensor.3x3_mothers_tent_week_in_stage",
    ]
