"""To-do platform surfacing actionable TendrilGrow grow tasks."""

from __future__ import annotations

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get as get_entity_registry
from homeassistant.util import dt as dt_util

from .const import CTX_STAGE, CTX_WEEK_IN_STAGE, DOMAIN
from .entity import grow_device_info
from .flush import flush_status
from .insights import build_grow_tasks
from .sensor import compute_stage_projection


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the grow-tasks to-do list for one config entry."""
    async_add_entities([TendrilGrowTodoList(hass, entry)])


class TendrilGrowTodoList(TodoListEntity):
    """A read-only, auto-generated list of currently-actionable grow tasks."""

    _attr_has_entity_name = True
    _attr_name = "Grow Tasks"
    _attr_icon = "mdi:clipboard-list-outline"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_tasks"
        self._attr_device_info = grow_device_info(entry)

    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    def _raw_tasks(self) -> list[dict]:
        now = dt_util.now()
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
        flush_st = None
        if runtime is not None and getattr(runtime, "flush_state", None) is not None:
            flush_st = flush_status(runtime.flush_state, dt_util.utcnow())
        alert_id = registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{self._entry.entry_id}_ai_health_critical_alert"
        )
        alert_state = self.hass.states.get(alert_id) if alert_id else None
        ai_critical = bool(alert_state and alert_state.state == "on")
        return build_grow_tasks(flush_st, projection, ai_critical, now)

    @property
    def todo_items(self) -> list[TodoItem]:
        return [
            TodoItem(
                summary=str(task["summary"]),
                uid=f"{self._entry.entry_id}_{task['uid']}",
                status=TodoItemStatus.NEEDS_ACTION,
                due=task["due"],
            )
            for task in self._raw_tasks()
        ]
