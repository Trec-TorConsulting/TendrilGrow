"""Calendar platform surfacing TendrilGrow grow-space milestones."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import grow_device_info
from .flush import flush_status
from .insights import build_grow_events
from .sensor import compute_stage_projection, resolve_stage_clock


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the grow-space calendar for one config entry."""
    async_add_entities([TendrilGrowCalendar(hass, entry)])


class TendrilGrowCalendar(CalendarEntity):
    """A read-only calendar of projected grow milestones and flush due dates."""

    _attr_has_entity_name = True
    _attr_name = "Grow Timeline"
    _attr_icon = "mdi:calendar-star"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_device_info = grow_device_info(entry)

    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    def _raw_events(self, now: datetime) -> list[dict]:
        stage, started, week = resolve_stage_clock(self.hass, self._entry.entry_id)
        projection = compute_stage_projection(stage, week, now, stage_started=started)
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        flush_next = None
        if runtime is not None and getattr(runtime, "flush_state", None) is not None:
            flush_next = flush_status(runtime.flush_state, dt_util.utcnow()).get(
                "next_due"
            )
        return build_grow_events(projection, flush_next, now)

    def _calendar_events(self, now: datetime) -> list[CalendarEvent]:
        return [
            CalendarEvent(start=e["start"], end=e["end"], summary=e["summary"])
            for e in self._raw_events(now)
        ]

    @property
    def event(self) -> CalendarEvent | None:
        events = self._calendar_events(dt_util.now())
        return events[0] if events else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        low = start_date.date()
        high = end_date.date()
        return [
            event
            for event in self._calendar_events(dt_util.now())
            if event.start <= high and event.end > low
        ]
