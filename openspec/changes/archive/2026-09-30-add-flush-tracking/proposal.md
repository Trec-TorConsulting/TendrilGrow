# Proposal: add-flush-tracking

## Why

In an RDWC system the operator performs a **full reservoir flush and refill** on a
regular cadence — typically every **7–10 days** — draining the old solution and
recharging with fresh, pH/EC-balanced water and nutrients. Doing this on schedule is
one of the most important recurring maintenance tasks for plant health: stale
solution drifts in pH, accumulates salts, and grows biofilm. Today TendrilGrow has no
way to **record** that a flush happened, **show** when the last one was, or **remind**
the operator when the next one is due. Growers track it in their head or on paper.

Operators want a simple, per-grow-space **"flush now" button** they press right after
completing a flush, plus at-a-glance **status** (days since the last flush, days until
the next, the next due date) and a clear **overdue** signal — with a reminder
notification and the flush status folded into the AI advisor's context so its feeding
and maintenance advice accounts for it. This is a **new, not-yet-built** capability.

## What Changes

- Add a per-grow-space **"Flush Now" button** that records the current time as the
  last full flush, grouped under that space's device alongside its other entities.
- Add an editable **flush interval** control (days; default 7, range 1–21) so each
  space can set its own 7–10-day cadence.
- Add **status sensors**: last-flush timestamp, days since last flush, days until the
  next flush (negative when overdue), and the next-due timestamp.
- Add a **"flush due" binary sensor** (problem class) that turns on when the interval
  has elapsed, so dashboards and automations can react.
- Add **reminders**: a persistent Home Assistant notification when a flush becomes
  overdue (de-duplicated), optionally also sent via the operator's configured notify
  service; cleared when the next flush is recorded.
- Add a **`mark_flush` service** (`entry_id`) so scripts/automations can record a
  flush without pressing the button.
- **Surface flush status to the AI health advisor** so its recommendations account for
  how recently the reservoir was flushed.
- Add **i18n labels** for the button, number, sensors, binary sensor, and service.

## Capabilities

### New Capabilities
- `reservoir-flush-tracking`: Per-grow-space tracking of the full reservoir
  flush/refill cadence — a record button, an editable interval, days-since /
  days-until / next-due sensors, an overdue binary sensor, de-duplicated reminders,
  a `mark_flush` service, and flush status surfaced to the AI advisor.

## Impact

- **New code**: a `flush.py` helper (flush state, persistence, status math,
  dispatcher signal, reminder), a "Flush Now" button in `button.py`, a flush-interval
  number in `number.py`, flush sensors in `sensor.py`, a flush-due binary sensor in
  `binary_sensor.py`, and a `mark_flush` service plus per-entry ticker in
  `__init__.py`.
- **Runtime**: `RuntimeData` gains a persisted flush state (last-flush timestamp +
  interval) backed by a small `Store` (mirroring the AI-history pattern) and an hourly
  ticker that advances the derived sensors and fires the overdue reminder.
- **AI context**: flush status labels are added to `GROW_CONTEXT_LABELS` so the
  existing context collector includes them in the health-check prompt.
- **Constants**: `CTX_FLUSH_INTERVAL_DAYS` and flush entity unique-id suffixes/labels
  added to `const.py`.
- **Persistence**: last-flush time and interval survive restarts; the interval number
  is the single source of truth for cadence and writes through to the flush state.
- **Safety / non-goals**: this change performs **no actuation** — it does not drain,
  fill, or dose anything. It only records timestamps, computes status, and notifies.
  Automated flush execution is out of scope (that belongs to the automations engine).
- **No breaking changes**: all additions are optional and additive; existing entities,
  flows, and config entries load unchanged. A space that never records a flush simply
  shows an "unknown / never flushed" status.
