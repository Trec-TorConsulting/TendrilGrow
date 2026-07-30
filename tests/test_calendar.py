"""Tests for the TendrilGrow calendar entity."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from custom_components.tendrilgrow.calendar import TendrilGrowCalendar
from custom_components.tendrilgrow.const import DOMAIN

_RAW = [
    {"summary": "Flush", "start": date(2026, 8, 5), "end": date(2026, 8, 6)},
    {"summary": "Harvest", "start": date(2026, 9, 1), "end": date(2026, 9, 2)},
]


def _cal(runtime: object = object()):
    hass = SimpleNamespace(data={DOMAIN: {"e1": runtime}})
    entry = SimpleNamespace(entry_id="e1", title="Tent A")
    return TendrilGrowCalendar(hass, entry), hass


def test_calendar_available_requires_runtime() -> None:
    cal, _ = _cal()
    assert cal.available is True
    absent = TendrilGrowCalendar(
        SimpleNamespace(data={DOMAIN: {}}),
        SimpleNamespace(entry_id="e1", title="A"),
    )
    assert absent.available is False


def test_calendar_event_is_next_upcoming(monkeypatch) -> None:
    cal, _ = _cal()
    monkeypatch.setattr(cal, "_raw_events", lambda now: list(_RAW))
    event = cal.event
    assert event is not None
    assert event.summary == "Flush"


def test_calendar_no_events(monkeypatch) -> None:
    cal, _ = _cal()
    monkeypatch.setattr(cal, "_raw_events", lambda now: [])
    assert cal.event is None


async def test_calendar_get_events_filters_window(monkeypatch) -> None:
    cal, hass = _cal()
    monkeypatch.setattr(cal, "_raw_events", lambda now: list(_RAW))
    events = await cal.async_get_events(
        hass,
        datetime(2026, 8, 1, tzinfo=UTC),
        datetime(2026, 8, 31, tzinfo=UTC),
    )
    assert [event.summary for event in events] == ["Flush"]
