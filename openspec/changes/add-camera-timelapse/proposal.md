# Proposal: add-camera-timelapse

> Status: **forward-looking design**. Not yet implemented. Captures the
> file-write (allow-list) and video-encoding (ffmpeg) constraints that make a
> naive implementation fragile, and designs around them.

## Why

A time-lapse of a plant's life is one of the most-requested "delight" features in
indoor growing. TendrilGrow already maps a `camera` per grow space for AI vision
health checks; the same camera can be sampled periodically to build a per-stage or
whole-grow time-lapse with no extra hardware.

Two Home Assistant constraints make a naive implementation unreliable, so they are
designed for up front rather than discovered in production:

1. **File writes are gated.** `camera.snapshot` only writes to a path inside
   `homeassistant.allowlist_external_dirs`. Writing to an arbitrary folder fails,
   and failing silently in a capture loop is worse than not shipping.
2. **Video encoding needs ffmpeg.** Assembling frames into an MP4/GIF requires
   ffmpeg and must run off the event loop so Home Assistant is never blocked.

## What Changes

- Add opt-in, per-space time-lapse capture: periodically (and on demand) write a
  snapshot of the mapped camera to a per-space directory.
- Bound disk use with a frame-retention cap that prunes the oldest frames after
  each capture.
- Expose status entities: a "Capture Frame" button, a frame-count sensor, and a
  last-frame timestamp sensor (with the directory and latest-frame path as
  attributes).
- Add a `build_timelapse` service that assembles the captured frames into a video
  with ffmpeg, run off the event loop, degrading gracefully when ffmpeg is
  unavailable.
- Raise a Home Assistant **Repair** issue when capture fails because the target
  directory is not allow-listed, naming the exact path to add, and pause the
  scheduler until it is resolved.
- Document the one-time `allowlist_external_dirs` step and the ffmpeg dependency.

## Capabilities

### New Capabilities

- `camera-timelapse`: Opt-in periodic camera snapshot capture per grow space,
  bounded retention, status entities, an allow-list repair, and ffmpeg-based
  video assembly.

### Modified Capabilities

<!-- None. Consumes the existing camera sensor-role mapping; no existing
requirement changes. -->

## Impact

- **Depends on**: a mapped `camera` role (already supported).
- **New code**: a `timelapse` module (capture, prune, build); config/options-flow
  fields; a capture button and frame-count / last-frame sensors; `services.yaml`
  and `strings.json`/`translations` labels; a repair issue.
- **Constants/config**: `CONF_TIMELAPSE_ENABLED` (default `False`),
  `CONF_TIMELAPSE_INTERVAL_HOURS` (default `24`),
  `CONF_TIMELAPSE_RETENTION_FRAMES` (default `120`), and optional
  `CONF_TIMELAPSE_DIR` override.
- **Environment**: the capture directory must be listed in
  `homeassistant.allowlist_external_dirs`; video assembly uses the ffmpeg binary
  Home Assistant already ships.
- **Safety/limits**: disabled by default; disk use bounded by retention; ffmpeg
  runs off the event loop; entirely local (no cloud upload).
- **No breaking changes**: additive and inert until enabled with a camera mapped.
