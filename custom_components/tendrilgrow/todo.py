"""To-do platform surfacing actionable TendrilGrow grow tasks."""

from __future__ import annotations

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity, TodoListEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get as get_entity_registry
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import grow_device_info
from .flush import flush_status
from .insights import build_grow_tasks
from .sensor import compute_stage_projection, resolve_stage_clock


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
    _attr_supported_features = TodoListEntityFeature.CREATE_TODO_ITEM | TodoListEntityFeature.UPDATE_TODO_ITEM | TodoListEntityFeature.DELETE_TODO_ITEM
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_tasks"
        self._attr_device_info = grow_device_info(entry)
        # Initialize storage for user‑created tasks
        custom_key = f"{entry.entry_id}_custom_tasks"
        self.hass.data.setdefault(DOMAIN, {}).setdefault(custom_key, [])
    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    def _raw_tasks(self) -> list[dict]:
        now = dt_util.now()
        stage, started, week = resolve_stage_clock(self.hass, self._entry.entry_id)
        projection = compute_stage_projection(stage, week, now, stage_started=started)
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        flush_st = None
        if runtime is not None and getattr(runtime, "flush_state", None) is not None:
            flush_st = flush_status(runtime.flush_state, dt_util.utcnow())
        registry = get_entity_registry(self.hass)
        alert_id = registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{self._entry.entry_id}_ai_health_critical_alert"
        )
        alert_state = self.hass.states.get(alert_id) if alert_id else None
        ai_critical = bool(alert_state and alert_state.state == "on")
        tasks = build_grow_tasks(flush_st, projection, ai_critical, now)
        # Append any user‑created custom tasks
        custom_key = f"{self._entry.entry_id}_custom_tasks"
        custom_tasks = self.hass.data.get(DOMAIN, {}).get(custom_key, [])
        tasks.extend(custom_tasks)
        return tasks
    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a new user‑defined todo item."""
        custom_key = f"{self._entry.entry_id}_custom_tasks"
        custom_tasks = self.hass.data.setdefault(DOMAIN, {}).setdefault(custom_key, [])
        uid = f"custom_{len(custom_tasks)}_{int(dt_util.utcnow().timestamp())}"
        custom_tasks.append({"uid": uid, "summary": item.summary, "due": item.due})

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an existing user‑defined todo item."""
        custom_key = f"{self._entry.entry_id}_custom_tasks"
        custom_tasks = self.hass.data.get(DOMAIN, {}).get(custom_key, [])
        for task in custom_tasks:
            if task["uid"] == item.uid:
                task["summary"] = item.summary
                task["due"] = item.due
                break

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete user‑defined todo items."""
        custom_key = f"{self._entry.entry_id}_custom_tasks"
        custom_tasks = self.hass.data.get(DOMAIN, {}).get(custom_key, [])
        self.hass.data[DOMAIN][custom_key] = [t for t in custom_tasks if t["uid"] not in uids]
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
