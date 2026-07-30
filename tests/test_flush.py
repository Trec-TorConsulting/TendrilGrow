"""Tests for reservoir flush tracking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.util import dt as dt_util

from custom_components.tendrilgrow import _EphemeralStore
from custom_components.tendrilgrow.binary_sensor import FlushDueBinarySensor
from custom_components.tendrilgrow.button import FlushNowButton
from custom_components.tendrilgrow.const import (
    CTX_FLUSH_INTERVAL_DAYS,
    DOMAIN,
    FLUSH_DAYS_SINCE_SUFFIX,
    FLUSH_DUE_SUFFIX,
    FLUSH_NEXT_DUE_SUFFIX,
    GROW_CONTEXT_LABELS,
)
from custom_components.tendrilgrow.flush import (
    FlushState,
    async_check_flush_due,
    async_record_flush,
    flush_dispatcher_signal,
    flush_notification_id,
    flush_status,
)
from custom_components.tendrilgrow.number import FlushIntervalNumber
from custom_components.tendrilgrow.sensor import (
    FlushDaysSinceSensor,
    FlushDaysUntilSensor,
    FlushLastSensor,
    FlushNextDueSensor,
)


def _now() -> datetime:
    return datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def test_flush_status_never_flushed() -> None:
    """Never-flushed state reports unknowns and not due."""
    status = flush_status(FlushState(), _now())
    assert status["last_flush"] is None
    assert status["days_since"] is None
    assert status["days_until"] is None
    assert status["next_due"] is None
    assert status["due"] is False
    assert status["interval_days"] == 7


def test_flush_status_within_interval() -> None:
    """Two days into a 7-day interval is not due."""
    state = FlushState(last_flush=_now() - timedelta(days=2), interval_days=7)
    status = flush_status(state, _now())
    assert status["days_since"] == 2
    assert status["days_until"] == 5
    assert status["due"] is False
    assert status["next_due"] == state.last_flush + timedelta(days=7)


def test_flush_status_exactly_at_interval_is_due() -> None:
    """Reaching the interval marks the flush due."""
    state = FlushState(last_flush=_now() - timedelta(days=7), interval_days=7)
    status = flush_status(state, _now())
    assert status["days_since"] == 7
    assert status["days_until"] == 0
    assert status["due"] is True


def test_flush_status_overdue_negative_days_until() -> None:
    """Past the interval reports negative days-until and due."""
    state = FlushState(last_flush=_now() - timedelta(days=10), interval_days=7)
    status = flush_status(state, _now())
    assert status["days_since"] == 10
    assert status["days_until"] == -3
    assert status["due"] is True


def test_flush_status_custom_interval() -> None:
    """A 10-day interval changes the due threshold."""
    state = FlushState(last_flush=_now() - timedelta(days=8), interval_days=10)
    status = flush_status(state, _now())
    assert status["days_since"] == 8
    assert status["days_until"] == 2
    assert status["due"] is False


def test_flush_status_naive_last_flush_treated_as_utc() -> None:
    """A naive stored datetime is treated as UTC without raising."""
    state = FlushState(last_flush=datetime(2026, 7, 27, 12, 0, 0), interval_days=7)
    status = flush_status(state, _now())
    assert status["days_since"] == 2


def test_flush_state_round_trip() -> None:
    """FlushState serializes and deserializes losslessly."""
    state = FlushState(
        last_flush=_now(),
        interval_days=10,
        notified_overdue_for="marker",
    )
    restored = FlushState.from_dict(state.to_dict())
    assert restored.last_flush == state.last_flush
    assert restored.interval_days == 10
    assert restored.notified_overdue_for == "marker"


def test_flush_state_from_dict_clamps_interval() -> None:
    """Out-of-range intervals are clamped to 1-21."""
    assert FlushState.from_dict({"interval_days": 0}).interval_days == 1
    assert FlushState.from_dict({"interval_days": 99}).interval_days == 21
    assert FlushState.from_dict({"interval_days": "bad"}).interval_days == 7


def test_flush_state_from_dict_bad_timestamp() -> None:
    """An unparseable timestamp yields last_flush None."""
    assert FlushState.from_dict({"last_flush": "not-a-date"}).last_flush is None


def test_flush_dispatcher_signal_is_entry_scoped() -> None:
    """Dispatcher signals and notification ids are per-entry."""
    assert flush_dispatcher_signal("a") != flush_dispatcher_signal("b")
    assert "a" in flush_notification_id("a")


def _record_hass(runtime: SimpleNamespace) -> SimpleNamespace:
    """A minimal hass that supports async_record_flush's dispatch + dismiss."""
    return SimpleNamespace(
        data={DOMAIN: {"entry-1": runtime}},
        verify_event_loop_thread=Mock(),
        services=SimpleNamespace(async_call=AsyncMock()),
    )


@pytest.mark.asyncio
async def test_async_record_flush_sets_state_and_persists() -> None:
    """Recording a flush sets last_flush, clears the reminder flag, and saves."""
    runtime = SimpleNamespace(
        flush_state=FlushState(notified_overdue_for="old"),
        flush_store=_EphemeralStore(),
        grow_space=SimpleNamespace(name="Tent A"),
    )
    hass = _record_hass(runtime)
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A", data={}, options={})

    await async_record_flush(hass, entry, runtime)

    assert runtime.flush_state.last_flush is not None
    assert runtime.flush_state.notified_overdue_for is None
    saved = await runtime.flush_store.async_load()
    assert saved["last_flush"] is not None
    # Dismisses any outstanding overdue notification.
    hass.services.async_call.assert_awaited()


@pytest.mark.asyncio
async def test_flush_now_button_records() -> None:
    """The Flush Now button records a flush via the runtime."""
    runtime = SimpleNamespace(
        flush_state=FlushState(),
        flush_store=_EphemeralStore(),
        grow_space=SimpleNamespace(name="Tent A"),
    )
    hass = _record_hass(runtime)
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A", data={}, options={})

    button = FlushNowButton(hass, entry)
    assert button.available is True
    assert runtime.flush_state.last_flush is None

    await button.async_press()

    assert runtime.flush_state.last_flush is not None


@pytest.mark.asyncio
async def test_flush_now_button_unavailable_without_runtime() -> None:
    """The button is unavailable and a no-op when the entry is not loaded."""
    hass = SimpleNamespace(data={DOMAIN: {}})
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A", data={}, options={})

    button = FlushNowButton(hass, entry)
    assert button.available is False
    # Should not raise even with no runtime present.
    await button.async_press()


@pytest.mark.asyncio
async def test_flush_interval_number_updates_runtime_and_due() -> None:
    """Changing the interval updates runtime state and flips due status."""
    runtime = SimpleNamespace(
        flush_state=FlushState(last_flush=_now() - timedelta(days=8), interval_days=7),
        flush_store=_EphemeralStore(),
        grow_space=SimpleNamespace(name="Tent A"),
    )
    hass = _record_hass(runtime)
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A", data={}, options={})

    number = FlushIntervalNumber(hass, entry)
    number.async_write_ha_state = Mock()

    assert number.native_value == 7.0
    # 8 days elapsed against a 7-day interval => due
    assert flush_status(runtime.flush_state, _now())["due"] is True

    await number.async_set_native_value(10)

    assert runtime.flush_state.interval_days == 10
    assert number.native_value == 10.0
    # 8 days elapsed against a 10-day interval => no longer due
    assert flush_status(runtime.flush_state, _now())["due"] is False
    saved = await runtime.flush_store.async_load()
    assert saved["interval_days"] == 10


@pytest.mark.asyncio
async def test_flush_interval_number_clamps_and_defaults() -> None:
    """Out-of-range values clamp; missing runtime yields the default value."""
    runtime = SimpleNamespace(
        flush_state=FlushState(),
        flush_store=_EphemeralStore(),
        grow_space=SimpleNamespace(name="Tent A"),
    )
    hass = _record_hass(runtime)
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A", data={}, options={})

    number = FlushIntervalNumber(hass, entry)
    number.async_write_ha_state = Mock()
    await number.async_set_native_value(99)
    assert runtime.flush_state.interval_days == 21

    empty = SimpleNamespace(data={DOMAIN: {}})
    number_no_runtime = FlushIntervalNumber(empty, entry)
    assert number_no_runtime.native_value == 7.0
    assert number_no_runtime.available is False


def _sensor_hass(runtime: SimpleNamespace | None) -> SimpleNamespace:
    data = {DOMAIN: {"entry-1": runtime}} if runtime is not None else {DOMAIN: {}}
    return SimpleNamespace(data=data)


def test_flush_sensors_never_flushed() -> None:
    """Status sensors report None before any flush is recorded."""
    runtime = SimpleNamespace(flush_state=FlushState())
    hass = _sensor_hass(runtime)
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A")

    assert FlushLastSensor(hass, entry).native_value is None
    assert FlushNextDueSensor(hass, entry).native_value is None
    assert FlushDaysSinceSensor(hass, entry).native_value is None
    assert FlushDaysUntilSensor(hass, entry).native_value is None


def test_flush_sensors_after_flush() -> None:
    """Status sensors reflect a recorded flush within the interval."""
    runtime = SimpleNamespace(
        flush_state=FlushState(
            last_flush=dt_util.utcnow() - timedelta(days=2), interval_days=7
        )
    )
    hass = _sensor_hass(runtime)
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A")

    assert FlushDaysSinceSensor(hass, entry).native_value == 2
    assert FlushDaysUntilSensor(hass, entry).native_value == 5
    next_due = FlushNextDueSensor(hass, entry).native_value
    assert next_due == runtime.flush_state.last_flush + timedelta(days=7)


def test_flush_sensors_unavailable_without_runtime() -> None:
    """Sensors are unavailable and return None when the entry is not loaded."""
    hass = _sensor_hass(None)
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A")
    sensor = FlushDaysSinceSensor(hass, entry)
    assert sensor.available is False
    assert sensor.native_value is None


def test_flush_due_binary_sensor_states() -> None:
    """The binary sensor is on only when overdue and exposes attributes."""
    overdue = SimpleNamespace(
        flush_state=FlushState(
            last_flush=dt_util.utcnow() - timedelta(days=9), interval_days=7
        )
    )
    hass = _sensor_hass(overdue)
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A")
    binary = FlushDueBinarySensor(hass, entry)
    assert binary.is_on is True
    attrs = binary.extra_state_attributes
    assert attrs["days_since"] == 9
    assert attrs["days_until"] == -2
    assert attrs["interval_days"] == 7
    assert attrs["last_flush"] is not None
    assert attrs["next_due"] is not None

    within = SimpleNamespace(
        flush_state=FlushState(
            last_flush=dt_util.utcnow() - timedelta(days=1), interval_days=7
        )
    )
    binary_ok = FlushDueBinarySensor(_sensor_hass(within), entry)
    assert binary_ok.is_on is False


def test_flush_due_binary_sensor_never_flushed() -> None:
    """A never-flushed space is not due and reports null timestamps."""
    runtime = SimpleNamespace(flush_state=FlushState())
    binary = FlushDueBinarySensor(
        _sensor_hass(runtime), SimpleNamespace(entry_id="entry-1", title="Tent A")
    )
    assert binary.is_on is False
    attrs = binary.extra_state_attributes
    assert attrs["last_flush"] is None
    assert attrs["days_since"] is None


def _create_calls(mock: AsyncMock) -> list:
    return [
        call
        for call in mock.await_args_list
        if call.args[:2] == ("persistent_notification", "create")
    ]


def _overdue_runtime() -> SimpleNamespace:
    return SimpleNamespace(
        flush_state=FlushState(
            last_flush=dt_util.utcnow() - timedelta(days=9), interval_days=7
        ),
        flush_store=_EphemeralStore(),
        grow_space=SimpleNamespace(name="Tent A"),
    )


@pytest.mark.asyncio
async def test_check_flush_due_notifies_when_overdue() -> None:
    """An overdue flush raises exactly one persistent notification."""
    runtime = _overdue_runtime()
    hass = SimpleNamespace(services=SimpleNamespace(async_call=AsyncMock()))
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A", data={}, options={})

    await async_check_flush_due(hass, entry, runtime)

    assert len(_create_calls(hass.services.async_call)) == 1
    assert (
        runtime.flush_state.notified_overdue_for
        == runtime.flush_state.last_flush.isoformat()
    )


@pytest.mark.asyncio
async def test_check_flush_due_deduplicates() -> None:
    """A second check in the same cycle does not notify again."""
    runtime = _overdue_runtime()
    hass = SimpleNamespace(services=SimpleNamespace(async_call=AsyncMock()))
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A", data={}, options={})

    await async_check_flush_due(hass, entry, runtime)
    hass.services.async_call.reset_mock()
    await async_check_flush_due(hass, entry, runtime)

    assert len(_create_calls(hass.services.async_call)) == 0


@pytest.mark.asyncio
async def test_check_flush_due_not_due_no_notify() -> None:
    """A within-interval flush does not notify."""
    runtime = SimpleNamespace(
        flush_state=FlushState(
            last_flush=dt_util.utcnow() - timedelta(days=1), interval_days=7
        ),
        flush_store=_EphemeralStore(),
        grow_space=SimpleNamespace(name="Tent A"),
    )
    hass = SimpleNamespace(services=SimpleNamespace(async_call=AsyncMock()))
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A", data={}, options={})

    await async_check_flush_due(hass, entry, runtime)

    assert len(_create_calls(hass.services.async_call)) == 0


@pytest.mark.asyncio
async def test_check_flush_due_rearms_after_flush() -> None:
    """Recording a flush re-arms the reminder for the next overdue cycle."""
    runtime = _overdue_runtime()
    hass = SimpleNamespace(
        data={DOMAIN: {"entry-1": runtime}},
        verify_event_loop_thread=Mock(),
        services=SimpleNamespace(async_call=AsyncMock()),
    )
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A", data={}, options={})

    await async_check_flush_due(hass, entry, runtime)
    assert len(_create_calls(hass.services.async_call)) == 1

    # Operator records a flush (clears the de-dupe flag).
    await async_record_flush(hass, entry, runtime)
    assert runtime.flush_state.notified_overdue_for is None

    # A new overdue cycle notifies again.
    runtime.flush_state.last_flush = dt_util.utcnow() - timedelta(days=9)
    hass.services.async_call.reset_mock()
    await async_check_flush_due(hass, entry, runtime)
    assert len(_create_calls(hass.services.async_call)) == 1


@pytest.mark.asyncio
async def test_check_flush_due_uses_notify_service() -> None:
    """A configured notify service is called in addition to the notification."""
    runtime = _overdue_runtime()
    hass = SimpleNamespace(services=SimpleNamespace(async_call=AsyncMock()))
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Tent A",
        data={"ai_notify_service": "notify.mobile_app"},
        options={},
    )

    await async_check_flush_due(hass, entry, runtime)

    notify_calls = [
        call
        for call in hass.services.async_call.await_args_list
        if call.args[:2] == ("notify", "mobile_app")
    ]
    assert len(notify_calls) == 1


def test_flush_labels_present_for_ai_context() -> None:
    """Flush status labels are exposed to the AI cultivation context."""
    assert FLUSH_DAYS_SINCE_SUFFIX in GROW_CONTEXT_LABELS
    assert CTX_FLUSH_INTERVAL_DAYS in GROW_CONTEXT_LABELS


def test_flush_context_labels_are_collision_safe() -> None:
    """No context label key mislabels the next_flush_due entity via endswith."""
    # flush_due is intentionally excluded because next_flush_due ends with it.
    assert FLUSH_DUE_SUFFIX not in GROW_CONTEXT_LABELS
    for key in GROW_CONTEXT_LABELS:
        assert not FLUSH_NEXT_DUE_SUFFIX.endswith(key)
