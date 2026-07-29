"""Reservoir full-flush tracking helpers for TendrilGrow.

This module records when a grow space's reservoir was last fully flushed, computes
derived status (days since, days until, next due, overdue), persists that state, and
fires a de-duplicated reminder when a flush becomes overdue. It performs NO actuation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AI_NOTIFY_SERVICE,
    DEFAULT_FLUSH_INTERVAL_DAYS,
    DOMAIN,
)

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class FlushState:
    """In-memory and persisted flush state for one grow entry."""

    last_flush: datetime | None = None
    interval_days: int = DEFAULT_FLUSH_INTERVAL_DAYS
    # ISO string of the last_flush value a reminder has already fired for; keeps
    # the overdue notification to once per flush cycle.
    notified_overdue_for: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_flush": self.last_flush.isoformat() if self.last_flush else None,
            "interval_days": self.interval_days,
            "notified_overdue_for": self.notified_overdue_for,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> FlushState:
        last_flush: datetime | None = None
        raw = value.get("last_flush")
        if isinstance(raw, str) and raw:
            try:
                last_flush = datetime.fromisoformat(raw)
                if last_flush.tzinfo is None:
                    last_flush = last_flush.replace(tzinfo=UTC)
            except ValueError:
                last_flush = None
        try:
            interval_days = int(value.get("interval_days", DEFAULT_FLUSH_INTERVAL_DAYS))
        except (TypeError, ValueError):
            interval_days = DEFAULT_FLUSH_INTERVAL_DAYS
        interval_days = max(1, min(21, interval_days))
        notified = value.get("notified_overdue_for")
        return cls(
            last_flush=last_flush,
            interval_days=interval_days,
            notified_overdue_for=notified if isinstance(notified, str) else None,
        )


def flush_dispatcher_signal(entry_id: str) -> str:
    """Dispatcher signal fired when a grow entry's flush state changes."""
    return f"{DOMAIN}_flush_update_{entry_id}"


def flush_notification_id(entry_id: str) -> str:
    """Stable persistent-notification id for a grow entry's overdue reminder."""
    return f"{DOMAIN}_flush_due_{entry_id}"


async def load_flush_state(store: Store[dict[str, Any]]) -> FlushState:
    """Load persisted flush state from HA storage."""
    payload = await store.async_load() or {}
    if not isinstance(payload, dict):
        return FlushState()
    return FlushState.from_dict(payload)


async def async_save_flush_state(
    store: Store[dict[str, Any]], state: FlushState
) -> None:
    """Persist flush state to HA storage."""
    await store.async_save(state.to_dict())


def flush_status(state: FlushState, now: datetime) -> dict[str, Any]:
    """Compute derived flush status from state and the current time.

    Returns a dict with:
    - ``last_flush``: aware datetime or None
    - ``interval_days``: configured cadence
    - ``days_since``: whole days since the last flush, or None if never flushed
    - ``days_until``: interval minus days_since (negative when overdue), or None
    - ``next_due``: last_flush + interval, or None
    - ``due``: True when a flush has been recorded and the interval has elapsed
    """
    interval = max(1, int(state.interval_days))
    if state.last_flush is None:
        return {
            "last_flush": None,
            "interval_days": interval,
            "days_since": None,
            "days_until": None,
            "next_due": None,
            "due": False,
        }

    last = state.last_flush
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    days_since = max(0, (now - last).days)
    days_until = interval - days_since
    next_due = last + timedelta(days=interval)
    return {
        "last_flush": last,
        "interval_days": interval,
        "days_since": days_since,
        "days_until": days_until,
        "next_due": next_due,
        "due": days_since >= interval,
    }


def _entry_notify_service(entry: ConfigEntry) -> str:
    merged = dict(entry.data)
    merged.update(getattr(entry, "options", {}) or {})
    return str(merged.get(CONF_AI_NOTIFY_SERVICE, "")).strip()


async def async_record_flush(
    hass: HomeAssistant, entry: ConfigEntry, runtime: Any
) -> None:
    """Record that a full flush just happened for this grow entry."""
    state: FlushState = runtime.flush_state
    state.last_flush = dt_util.utcnow()
    state.notified_overdue_for = None
    await async_save_flush_state(runtime.flush_store, state)
    async_dispatcher_send(hass, flush_dispatcher_signal(entry.entry_id))

    # Clear any outstanding overdue reminder for this space.
    try:
        await hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": flush_notification_id(entry.entry_id)},
            blocking=False,
        )
    except Exception:  # noqa: BLE001
        LOGGER.debug("Unable to dismiss flush notification", exc_info=True)

    LOGGER.info(
        "Recorded reservoir flush for %s (%s) at %s",
        entry.title,
        entry.entry_id,
        state.last_flush.isoformat(),
    )


async def async_check_flush_due(
    hass: HomeAssistant, entry: ConfigEntry, runtime: Any
) -> None:
    """Fire a de-duplicated overdue reminder when the flush interval has elapsed."""
    state: FlushState = runtime.flush_state
    status = flush_status(state, dt_util.utcnow())
    if not status["due"] or state.last_flush is None:
        return

    marker = state.last_flush.isoformat()
    if state.notified_overdue_for == marker:
        return  # already notified for this flush cycle

    name = getattr(runtime.grow_space, "name", entry.title)
    overdue_by = abs(int(status["days_until"]))
    title = f"TendrilGrow flush due: {name}"
    message = (
        f"Reservoir flush is overdue by {overdue_by} day(s). Last flushed "
        f"{status['days_since']} day(s) ago; interval is {status['interval_days']} "
        "day(s). Flush and refill, then press 'Flush Now'."
    )

    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": title,
            "message": message,
            "notification_id": flush_notification_id(entry.entry_id),
        },
        blocking=False,
    )

    notify_service = _entry_notify_service(entry)
    if notify_service and "." in notify_service:
        domain, service = notify_service.split(".", 1)
        try:
            await hass.services.async_call(
                domain,
                service,
                {"title": title, "message": message},
                blocking=False,
            )
        except Exception:  # noqa: BLE001
            LOGGER.debug("Flush notify service call failed", exc_info=True)

    state.notified_overdue_for = marker
    await async_save_flush_state(runtime.flush_store, state)
    LOGGER.info("Flush overdue reminder sent for %s (%s)", name, entry.entry_id)
