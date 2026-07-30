"""Tests for the TendrilGrow to-do list entity."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from homeassistant.components.todo import TodoItemStatus

from custom_components.tendrilgrow.const import DOMAIN
from custom_components.tendrilgrow.todo import TendrilGrowTodoList


def _todo(runtime: object = object()) -> TendrilGrowTodoList:
    hass = SimpleNamespace(data={DOMAIN: {"e1": runtime}})
    entry = SimpleNamespace(entry_id="e1", title="Tent A")
    return TendrilGrowTodoList(hass, entry)


def test_todo_available_requires_runtime() -> None:
    assert _todo().available is True
    absent = TendrilGrowTodoList(
        SimpleNamespace(data={DOMAIN: {}}),
        SimpleNamespace(entry_id="e1", title="A"),
    )
    assert absent.available is False


def test_todo_items_wraps_tasks(monkeypatch) -> None:
    todo = _todo()
    monkeypatch.setattr(
        todo,
        "_raw_tasks",
        lambda: [{"uid": "flush", "summary": "Flush", "due": date(2026, 8, 5)}],
    )
    items = todo.todo_items
    assert len(items) == 1
    assert items[0].summary == "Flush"
    assert items[0].uid == "e1_flush"
    assert items[0].status == TodoItemStatus.NEEDS_ACTION


def test_todo_items_empty(monkeypatch) -> None:
    todo = _todo()
    monkeypatch.setattr(todo, "_raw_tasks", lambda: [])
    assert todo.todo_items == []
