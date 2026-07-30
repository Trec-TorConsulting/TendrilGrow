# Tasks: add-camera-timelapse

> Implemented. Capture depends on the target directory being in
> `allowlist_external_dirs`; video assembly depends on ffmpeg.

## 1. Config and constants

- [x] 1.1 Add `CONF_TIMELAPSE_ENABLED` (default False), `CONF_TIMELAPSE_INTERVAL_HOURS` (default 24), `CONF_TIMELAPSE_RETENTION_FRAMES` (default 120), and optional `CONF_TIMELAPSE_DIR` (`const.py`)
- [x] 1.2 Add options-flow fields to enable time-lapse, set the interval, set retention, and optionally override the directory (`config_flow.py`)
- [x] 1.3 Unit-test that the time-lapse settings persist and reload (`tests/test_config_flow.py`)

## 2. Capture pipeline (`timelapse.py`)

- [x] 2.1 Implement directory + `/local/` URL resolution (default `<config>/www/tendrilgrow/<slug>/timelapse/`, overridable) as a pure helper
- [x] 2.2 Implement a pure timestamped-filename builder and a pure retention/prune selector (given files + cap → files to delete)
- [x] 2.3 Implement `async_capture_frame`: resolve the mapped camera, call `camera.snapshot` to the resolved path, verify the write, then prune to the retention cap
- [x] 2.4 Unit-test the pure helpers (filename, prune selection, directory/URL resolution) with a temp directory

## 3. Scheduling and triggers

- [x] 3.1 Start a per-space capture scheduler at the configured interval only when enabled; wire start/stop into `async_setup_entry`/`async_unload_entry`
- [x] 3.2 Add `button.<grow>_capture_timelapse_frame` and a `capture_timelapse_frame` service (both call `async_capture_frame`)
- [x] 3.3 Unit-test that the scheduler is not started when disabled and that the button/service invoke a single capture

## 4. Allow-list repair

- [x] 4.1 Detect a not-allow-listed capture failure and raise a `timelapse_not_allowlisted` repair issue naming the path to add
- [x] 4.2 Pause the scheduler while the repair is open; clear the issue and resume once a capture succeeds
- [x] 4.3 Unit-test the allow-list detection and the repair create/clear logic

## 5. Video assembly

- [x] 5.1 Implement a pure ffmpeg command builder (input glob, framerate, output path)
- [x] 5.2 Implement the `build_timelapse` service: run ffmpeg off the event loop (async subprocess) using the Home Assistant ffmpeg binary; degrade to logging the manual command when ffmpeg is missing
- [x] 5.3 Unit-test the command builder and the graceful-degradation path

## 6. Status entities

- [x] 6.1 Add `sensor.<grow>_timelapse_frames` (frame count) with directory + latest-path attributes
- [x] 6.2 Add `sensor.<grow>_timelapse_last_frame` (timestamp of the newest frame)
- [x] 6.3 Add `strings.json`/`translations/en.json` labels for the new fields, entities, services, and the repair issue

## 7. Documentation and validation

- [x] 7.1 Document the one-time `allowlist_external_dirs` step, the ffmpeg dependency, and where frames/videos are written (docs site + `README.md`)
- [x] 7.2 `ruff check .` and `pytest -q` pass; `openspec validate add-camera-timelapse --strict` passes
