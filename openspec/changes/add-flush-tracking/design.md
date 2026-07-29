# Design: add-flush-tracking

## Context

Operators flush and refill the RDWC reservoir on a 7–10-day cadence. TendrilGrow
already persists per-entry runtime state through a small `Store` and surfaces
cross-entity updates through dispatcher signals (see `ai/health_checks.py`,
`RuntimeData`, and `binary_sensor.py`). It also exposes editable cultivation-context
helpers as `RestoreNumber`/`RestoreSensor` entities and collects those entities'
states into the AI prompt via `GROW_CONTEXT_LABELS`. This change reuses all of that
plumbing to add flush tracking with no new hardware or external dependencies.

## Goals / Non-Goals

**Goals**
- One-press recording of a completed full flush, per grow space.
- Clear status: last flush, days since, days until next, next-due date, overdue flag.
- Editable per-space interval (default 7 days) driving the "due" math.
- A de-duplicated overdue reminder and flush status surfaced to the AI advisor.
- A service so scripts/automations can record a flush.

**Non-Goals**
- No actuation: nothing drains, fills, or doses (that is the automations engine).
- No multi-event flush history/analytics beyond the last flush (MVP keeps last-only).
- No new config-flow entity mappings (flush state is runtime + entity state).

## State model and persistence (`flush.py`)

A dedicated helper module mirrors the AI-health pattern:

```python
@dataclass(slots=True)
class FlushState:
    last_flush: datetime | None = None      # UTC; None => never recorded
    interval_days: int = DEFAULT_FLUSH_INTERVAL_DAYS   # 7
    notified_overdue_for: str | None = None  # ISO of last_flush a reminder fired for

def flush_dispatcher_signal(entry_id: str) -> str: ...
async def load_flush_state(store) -> FlushState: ...
async def async_save_flush_state(store, state) -> None: ...
def flush_status(state: FlushState, now: datetime) -> dict[str, Any]: ...
async def async_record_flush(hass, entry, runtime) -> None: ...
async def async_check_flush_due(hass, entry, runtime) -> None: ...
```

- `RuntimeData` gains `flush_state: FlushState`, `flush_store` (a `Store`, with the
  `_EphemeralStore` fallback used elsewhere for tests), and
  `unsubscribe_flush_ticker`.
- The **interval number entity is the source of truth for cadence**: on restore and on
  change it writes `runtime.flush_state.interval_days`, saves the store, and dispatches
  the flush signal. `last_flush` is written only by the button/service.
- `flush_status(state, now)` returns a plain dict so the button, sensors, binary
  sensor, and service all compute identically:
  - `days_since` = whole days between `last_flush` and `now` (None if never flushed)
  - `days_until` = `interval_days - days_since` (may be negative = overdue)
  - `next_due` = `last_flush + interval_days` (None if never flushed)
  - `due` = `last_flush is not None and days_since >= interval_days`

## Recording a flush

- **Button** `Flush Now` (`button.py`): on press calls `async_record_flush`, which sets
  `last_flush = dt_util.utcnow()`, clears `notified_overdue_for`, saves the store,
  dispatches `flush_dispatcher_signal(entry_id)`, and dismisses the persistent
  reminder notification for that space.
- **Service** `tendrilgrow.mark_flush` (`entry_id`, required): same path as the button,
  for scripts/automations. Unknown/unloaded entry raises `HomeAssistantError`; a loaded
  entry records the flush.

## Interval control

- **Number** `Flush Interval` (`number.py`): a `RestoreNumber` reusing the existing
  context-number pattern (`CTX_FLUSH_INTERVAL_DAYS`, min 1, max 21, step 1, unit `d`,
  default 7, icon `mdi:calendar-refresh`). On `async_added_to_hass` (restore) and
  `async_set_native_value` it updates `runtime.flush_state.interval_days`, saves the
  store, and dispatches the flush signal so derived entities recompute immediately.

## Derived entities

All read from `runtime.flush_state` via `flush_status(...)`, subscribe to the flush
dispatcher signal, and register an **hourly** `async_track_time_interval` tick so
"days since / until" advance and "due" flips without user action. `available` is
`True` when the entry's runtime is loaded.

- **Sensor** `Last Flush` — `device_class: timestamp`; value is `last_flush`; `None`
  (unknown) when never recorded.
- **Sensor** `Days Since Flush` — numeric (`d`), `state_class: measurement`; `None`
  until first flush.
- **Sensor** `Days Until Flush` — numeric (`d`); `interval - days_since` (negative when
  overdue); `None` until first flush.
- **Sensor** `Next Flush Due` — `device_class: timestamp`; `next_due`; `None` until
  first flush.
- **Binary sensor** `Flush Due` (`binary_sensor.py`) — `device_class: problem`; `is_on`
  when `due`; extra attributes expose `days_since`, `days_until`, `interval_days`,
  `last_flush`, `next_due`.

## Reminders (`async_check_flush_due`)

- Invoked by the hourly ticker (and once shortly after setup). When `due` is `True` and
  `notified_overdue_for != last_flush.isoformat()`, create a **persistent notification**
  (stable id per entry, e.g. `tendrilgrow_flush_due_<entry_id>`) and, if the operator
  has configured a notify service (reuse the existing `ai_notify_service` option when
  set), send it there too; then set `notified_overdue_for` and save so it fires once per
  flush cycle.
- Recording a new flush clears `notified_overdue_for` and dismisses the persistent
  notification, so the next cycle can notify again.

## AI advisor integration

- Add flush labels to `GROW_CONTEXT_LABELS` keyed by the flush entities' unique-id
  suffixes (e.g. `days_since_flush`, `flush_due`). The existing `_collect_grow_context`
  then includes their states in the health-check prompt automatically, so AI feeding and
  maintenance advice accounts for how recently the reservoir was flushed. No prompt
  rewrite is required.

## Lifecycle (`__init__.py`)

- On `async_setup_entry`: create `flush_store` (with fallback), `load_flush_state`, and
  seed `interval_days` from stored value; register an hourly
  `async_track_time_interval` calling `async_check_flush_due`; schedule one delayed
  check shortly after startup (like the AI startup check). Store unsub on `RuntimeData`.
- On `async_unload_entry`: call `unsubscribe_flush_ticker` if set.
- Register/deregister the `mark_flush` service alongside the existing services using the
  same idempotent registration guard.

## Testing strategy

- `flush_status` math: never-flushed → unknowns; exactly-at-interval → due; before
  interval → not due; overdue → negative `days_until`, `due` True.
- Button/service record path: sets `last_flush`, clears prior notification flag, saves,
  dispatches.
- Interval number: setting the value updates runtime interval and flips `due` when it
  crosses the elapsed days.
- Binary sensor `is_on` and attributes reflect state; sensors return timestamps/numbers
  or `None` when never flushed.
- Reminder de-duplication: fires once per cycle; recording a new flush re-arms it.
- Service raises for unknown/unloaded entry; records for a loaded entry.

## Migration

None. All additions are optional and additive. Existing config entries load unchanged;
a space with no recorded flush reports "never flushed / unknown" until the first press.
