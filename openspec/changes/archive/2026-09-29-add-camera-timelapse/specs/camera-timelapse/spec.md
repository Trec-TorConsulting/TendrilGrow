## ADDED Requirements

### Requirement: Opt-in periodic snapshot capture

The integration SHALL provide an opt-in, per-grow-space time-lapse capture that,
when enabled and a camera is mapped, writes a snapshot of the mapped camera to a
per-space directory on a configurable interval. Capture MUST default to disabled
and MUST also be triggerable on demand.

#### Scenario: Scheduled capture when enabled

- **WHEN** time-lapse is enabled, a camera is mapped, and the capture interval elapses
- **THEN** the integration writes a new timestamped snapshot to the space's time-lapse directory

#### Scenario: Disabled by default

- **WHEN** a grow space is set up without enabling time-lapse
- **THEN** the integration captures no frames and starts no capture scheduler

#### Scenario: On-demand capture

- **WHEN** an operator presses the capture button or calls the capture service
- **THEN** the integration writes one snapshot immediately

### Requirement: Bounded frame retention

The integration SHALL bound disk usage by keeping at most the configured number of
most-recent frames per grow space, and MUST prune the oldest frames after each
capture so the stored count never exceeds the cap.

#### Scenario: Prune beyond the cap

- **WHEN** capturing a frame would exceed the configured retention count
- **THEN** the integration deletes the oldest frames so the count stays at or below the cap

### Requirement: Allow-list failure surfaces a repair

The integration SHALL detect when a capture fails because the target directory is not
in Home Assistant's allow-list and MUST raise a repair issue naming the path to add,
rather than silently retrying. The scheduler MUST pause until captures succeed again.

#### Scenario: Directory not allow-listed

- **WHEN** a capture fails because the capture directory is not in `allowlist_external_dirs`
- **THEN** the integration raises a repair issue naming the path to add and stops scheduling captures

#### Scenario: Repair clears when resolved

- **WHEN** the directory is added to the allow-list and a capture then succeeds
- **THEN** the integration clears the repair issue and resumes scheduled captures

### Requirement: ffmpeg video assembly

The integration SHALL provide a service that assembles the captured frames into a
time-lapse video using ffmpeg, run off the event loop. When ffmpeg is unavailable the
service MUST degrade gracefully without raising an error and MUST leave the captured
frames intact.

#### Scenario: Assemble a video

- **WHEN** the build service is called with ffmpeg available and frames present
- **THEN** the integration produces a time-lapse video file from the frames without blocking the event loop

#### Scenario: ffmpeg unavailable

- **WHEN** the build service is called and ffmpeg is not available
- **THEN** the integration logs the equivalent manual command, leaves the frames intact, and raises no error

### Requirement: Time-lapse status entities

The integration SHALL expose per-grow-space time-lapse status: a capture button, a
frame-count sensor, and a last-frame timestamp sensor. The frame-count sensor MUST
expose the capture directory and the latest-frame path as attributes.

#### Scenario: Frame count reflects captures

- **WHEN** frames exist in the space's time-lapse directory
- **THEN** the frame-count sensor reports the number of frames and the last-frame sensor reports the newest frame's time
