## ADDED Requirements

### Requirement: Record a full flush
The integration SHALL provide a per-grow-space control that records the current time
as the moment the reservoir was last fully flushed, grouped under that grow space's
device. Recording a flush MUST persist across restarts and MUST update the derived
flush status immediately.

#### Scenario: Operator records a flush
- **WHEN** the operator presses the grow space's "Flush Now" button
- **THEN** the integration stores the current time as that space's last-flush time and the flush status updates

#### Scenario: Recorded flush survives restart
- **WHEN** a flush has been recorded and Home Assistant restarts
- **THEN** the last-flush time is restored and the derived status reflects it

#### Scenario: Record a flush via service
- **WHEN** the `mark_flush` service is called for a loaded grow-space entry
- **THEN** the integration records the current time as that space's last-flush time

#### Scenario: Service rejects an unknown entry
- **WHEN** `mark_flush` is called with an entry id that is not loaded
- **THEN** the service raises an error and records nothing

### Requirement: Configurable flush interval
The integration SHALL expose a per-grow-space editable flush interval in days, with a
sensible default of 7 and a supported range of 1 to 21, that determines when the next
flush is due. Changing the interval MUST persist and MUST recompute the flush status
immediately. The interval is the single source of truth for the flush cadence.

#### Scenario: Default interval
- **WHEN** a grow space is loaded and no interval has been set
- **THEN** the flush interval defaults to 7 days

#### Scenario: Operator changes the interval
- **WHEN** the operator sets the flush interval to 10 days
- **THEN** the integration persists 10 days and recomputes days-until and due status against it

### Requirement: Flush status reporting
For each grow space the integration SHALL expose flush status derived from the
last-flush time and interval: the last-flush timestamp, the whole number of days since
the last flush, the number of days until the next flush (negative when overdue), and
the next-due timestamp. Before any flush is recorded these values MUST report an
unknown state rather than a misleading number.

#### Scenario: Status after a recent flush
- **WHEN** a flush was recorded two days ago with a 7-day interval
- **THEN** days-since reports 2, days-until reports 5, and next-due reports five days from now

#### Scenario: Never flushed
- **WHEN** no flush has ever been recorded for a grow space
- **THEN** the last-flush, days-since, days-until, and next-due values report unknown

#### Scenario: Status advances over time
- **WHEN** a day passes without recording a flush
- **THEN** days-since increases and days-until decreases without any operator action

### Requirement: Flush due indicator
The integration SHALL expose a per-grow-space problem-class binary indicator that is on
when the configured interval has elapsed since the last flush and off otherwise, and
that carries the underlying status (days since, days until, interval, last flush, next
due) as attributes.

#### Scenario: Interval elapsed
- **WHEN** the days since the last flush reach or exceed the interval
- **THEN** the flush-due indicator turns on

#### Scenario: Within interval
- **WHEN** the days since the last flush are fewer than the interval
- **THEN** the flush-due indicator is off

#### Scenario: Cleared by a new flush
- **WHEN** the indicator is on and the operator records a new flush
- **THEN** the indicator turns off

### Requirement: Overdue flush reminder
When a flush becomes overdue the integration SHALL notify the operator once per flush
cycle via a persistent Home Assistant notification, and additionally via the operator's
configured notify service when one is set. Recording a new flush MUST clear the reminder
so the next cycle can notify again, and the reminder MUST NOT repeat every check while
a single cycle remains overdue.

#### Scenario: Notify when overdue
- **WHEN** a grow space's flush first becomes overdue
- **THEN** the integration raises a persistent notification for that space

#### Scenario: Reminder is de-duplicated
- **WHEN** the flush remains overdue across multiple checks in the same cycle
- **THEN** the integration does not raise additional notifications for that cycle

#### Scenario: Reminder re-arms after a flush
- **WHEN** the operator records a new flush after an overdue reminder fired
- **THEN** the integration clears the reminder and can notify again when the next cycle becomes overdue

### Requirement: Flush status in AI advice
The integration SHALL include the current flush status in the cultivation context
provided to the AI health advisor, so its recommendations account for how recently the
reservoir was flushed.

#### Scenario: AI check includes flush status
- **WHEN** an AI health check runs for a grow space that has recorded a flush
- **THEN** the cultivation context passed to the advisor includes the flush status

### Requirement: No automatic actuation
This capability SHALL only record timestamps, compute status, and notify; it SHALL NOT
drain, fill, dose, or otherwise actuate any equipment. Performing a flush is always a
manual operator action recorded after the fact.

#### Scenario: Tracking performs no actuation
- **WHEN** a flush becomes due or overdue
- **THEN** the integration changes no equipment state and only reports status and notifies
