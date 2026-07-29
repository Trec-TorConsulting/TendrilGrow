# Tasks: add-flush-tracking

> Forward-looking change — **not yet implemented**. Work top to bottom; each task is
> independently verifiable. This change adds **manual recording, status, and reminders
> only**; it performs no actuation. Do not check a box until its verification passes.

## 1. Constants and flush state helper

- [x] 1.1 Add `CTX_FLUSH_INTERVAL_DAYS`, `DEFAULT_FLUSH_INTERVAL_DAYS = 7`, and flush entity unique-id suffix constants (`last_flush`, `days_since_flush`, `days_until_flush`, `next_flush_due`, `flush_due`, `flush_now`) to `const.py`
- [x] 1.2 Add flush status labels to `GROW_CONTEXT_LABELS` (e.g. `days_since_flush`, `flush_interval_days`) so the AI context collector picks them up
- [x] 1.3 Create `flush.py` with `FlushState`, `flush_dispatcher_signal`, `load_flush_state`, `async_save_flush_state`, and pure `flush_status(state, now)` returning days_since/days_until/next_due/due
- [x] 1.4 Unit-test `flush_status`: never-flushed → unknowns; before interval → not due; at interval → due; overdue → negative days_until (`tests/test_flush.py`)

## 2. Runtime wiring and persistence

- [x] 2.1 Extend `RuntimeData` with `flush_state`, `flush_store`, and `unsubscribe_flush_ticker` (`__init__.py`)
- [x] 2.2 On `async_setup_entry`, create the flush `Store` (with `_EphemeralStore` fallback), load `FlushState`, and seed `interval_days` from stored value
- [x] 2.3 Register an hourly `async_track_time_interval` calling `async_check_flush_due`, plus one delayed post-startup check; store the unsub and call it on `async_unload_entry`
- [x] 2.4 Implement `async_record_flush` (set last_flush=now, clear overdue flag, save, dispatch, dismiss persistent notification)

## 3. Record controls (button + service)

- [x] 3.1 Add a "Flush Now" button in `button.py` that calls `async_record_flush`, attached to the grow-space `DeviceInfo`
- [x] 3.2 Register `tendrilgrow.mark_flush` (`entry_id`, required) in `__init__.py` using the existing idempotent service guard; raise for unknown/unloaded entry, else record; document it in `services.yaml`
- [x] 3.3 Unit-test button press and service both record a flush; service raises on unknown entry (`tests/test_flush.py` / `tests/test_init.py`)

## 4. Interval control

- [x] 4.1 Add a `Flush Interval` number (`CTX_FLUSH_INTERVAL_DAYS`, 1–21, step 1, unit `d`, default 7) in `number.py`
- [x] 4.2 On restore and on `async_set_native_value`, update `runtime.flush_state.interval_days`, save the store, and dispatch the flush signal
- [x] 4.3 Unit-test: changing the interval recomputes due status and flips `due` when it crosses the elapsed days (`tests/test_flush.py`)

## 5. Derived sensors and binary sensor

- [x] 5.1 Add `Last Flush` (`device_class: timestamp`) and `Next Flush Due` (`device_class: timestamp`) sensors mirroring `flush_status` (`sensor.py`)
- [x] 5.2 Add `Days Since Flush` and `Days Until Flush` numeric sensors (unit `d`); `None` until first flush
- [x] 5.3 Add a `Flush Due` problem-class binary sensor with days_since/days_until/interval/last_flush/next_due attributes (`binary_sensor.py`)
- [x] 5.4 Each flush entity subscribes to `flush_dispatcher_signal` and an hourly tick, and reports `available` from runtime presence
- [x] 5.5 Unit-test sensor/binary-sensor values for never-flushed, within-interval, and overdue states (`tests/test_flush.py`)

## 6. Reminders and AI integration

- [x] 6.1 Implement `async_check_flush_due`: when due and not already notified for this cycle, raise a stable-id persistent notification and (if configured) send via the notify service; set the de-dupe flag and save
- [x] 6.2 Ensure recording a flush clears the de-dupe flag and dismisses the persistent notification so the next cycle can notify
- [x] 6.3 Confirm `_collect_grow_context` includes the flush status entities in the AI prompt (via the labels from 1.2); adjust suffixes if needed
- [x] 6.4 Unit-test reminder de-duplication (fires once per cycle; re-arms after a new flush) (`tests/test_flush.py`)

## 7. i18n and docs

- [x] 7.1 Add `strings.json` + `translations/en.json` labels for the button, number, sensors, binary sensor, and the `mark_flush` service (both files in sync)
- [x] 7.2 Add help text describing the 7–10-day full-flush cadence and the "press after flushing" workflow
- [x] 7.3 Update `README.md`/`CHANGELOG.md`: flush tracking (button, status, reminders, AI awareness) under shipped features

## 8. Validation

- [x] 8.1 Full test pass for the flush helper, button, number, sensors, binary sensor, and service
- [x] 8.2 `ruff check .` clean and `hassfest`/HACS validation pass
- [x] 8.3 Extend `scripts/validate_live_ha.py` to report per-space last-flush, days-since/until, and due state
- [ ] 8.4 Manual live check: press "Flush Now"; confirm timestamp, days-since/until, next-due, and due binary update; set interval to trip overdue and confirm one reminder fires; record a flush and confirm it clears
