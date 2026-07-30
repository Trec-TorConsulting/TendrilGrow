# Reservoir flush tracking

RDWC reservoirs are typically fully flushed and refilled on a 7–10 day cadence.
TendrilGrow tracks that cadence so you always know when the next flush is due.

## How it works

- Press **Flush Now** (or call
  [`tendrilgrow.mark_flush`](services.md#tendrilgrowmark_flush)) each time you
  complete a full flush and refill.
- The **Flush Interval** number sets your cadence (default **7 days**).
- Status sensors track the rest.

## Entities

| Entity | Description |
| --- | --- |
| Flush Now (button) | Records a flush at the current time. |
| Flush Interval (number) | Editable cadence in days (default 7). |
| Last Flush (sensor) | Timestamp of the most recent recorded flush. |
| Days Since Flush (sensor) | Days since the last flush. |
| Days Until Flush (sensor) | Days remaining until the next flush is due. |
| Next Flush Due (sensor) | Date the next flush is due. |
| Flush Due (binary sensor) | Problem-class indicator that turns on when overdue. |

## Overdue reminders

When a flush is overdue, TendrilGrow raises a de-duplicated persistent
notification and, if configured, calls your `notify.*` service. The flush status
is also folded into the AI advisor's cultivation context.

!!! note "Recording only — no actuation"
    Flush tracking records that you performed a flush. It does not drain or fill
    anything. There is no "fill" automation; "flush and fill" here means
    recording a completed reservoir change.
