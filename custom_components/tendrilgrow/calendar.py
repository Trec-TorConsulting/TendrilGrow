"""Calendar platform surfacing TendrilGrow grow-space milestones."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get as get_entity_registry
from homeassistant.util import dt as dt_util

from .const import CTX_STAGE, CTX_WEEK_IN_STAGE, DOMAIN
from .entity import grow_device_info
from .flush import flush_status
from .insights import build_grow_events
from .sensor import compute_stage_projection


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
        registry = get_entity_registry(self.hass)
        stage_id = registry.async_get_entity_id(
            "select", DOMAIN, f"{self._entry.entry_id}_{CTX_STAGE}"
        )
        week_id = registry.async_get_entity_id(
            "number", DOMAIN, f"{self._entry.entry_id}_{CTX_WEEK_IN_STAGE}"
        )
        stage_state = self.hass.states.get(stage_id) if stage_id else None
        week_state = self.hass.states.get(week_id) if week_id else None
        projection = compute_stage_projection(
            stage_state.state if stage_state else None,
            week_state.state if week_state else None,
            now,
        )
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
