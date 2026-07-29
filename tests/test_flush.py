"""Tests for reservoir flush tracking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.tendrilgrow import _EphemeralStore
from custom_components.tendrilgrow.button import FlushNowButton
from custom_components.tendrilgrow.const import DOMAIN
from custom_components.tendrilgrow.flush import (
    FlushState,
    async_record_flush,
    flush_dispatcher_signal,
    flush_notification_id,
    flush_status,
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
    state = FlushState(
        last_flush=datetime(2026, 7, 27, 12, 0, 0), interval_days=7
    )
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
