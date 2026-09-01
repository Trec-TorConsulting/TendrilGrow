# Upgrading

Always **restart Home Assistant** after a HACS update. New platforms (for
example the Stage Started `date` entity) are not created until the integration
reloads with the new code.

## HACS update

1. HACS → **TendrilGrow** → **Update**.
2. Restart Home Assistant.
3. Confirm **Settings → Devices & Services → TendrilGrow** still shows each
   grow space.
4. Skim [Changelog](changelog.md) for the version you installed.

## 0.3.2 — Stage Started

Week In Stage is no longer an editable number. **Stage Started** is a date;
weeks are computed from it.

- Changing **Growth Stage** resets Stage Started to **today**. Backdate the
  date if the stage actually started earlier.
- On upgrade, an old week number is converted (week 2 → about 14 days ago).

## Cultivation Plan entity IDs (0.3.3) {#upgrade-033}

0.3.2 could create generic ids (`date.stage_started`) while dashboards expected
`date.<grow_space>_stage_started`, which showed **Entity not found** on every
Cultivation Plan card.

0.3.3:

- Pins Stage Started and Week In Stage to the same prefix as **Growth Stage**.
- Rewrites **storage-mode** Lovelace dashboards that still list
  `number.*_week_in_stage`.

After update, reload TendrilGrow (or restart) and wait ~15 seconds. If a YAML
dashboard still 404s, copy IDs from the device entity list or run
`scripts/generate_dashboard.py --apply` ([Dashboards](dashboards.md)).

## After any major update

| Check | Expected |
| --- | --- |
| Cultivation Plan | Stage Started (date picker) + Week In Stage (sensor) |
| Flush Due | Still present on the device |
| AI Health | Score/summary return after one manual run if AI is configured |
| Local water | pH/EC still updating; call `tendrilgrow.rebuild_automap` if not |

Download **diagnostics** from the config entry if you need to file an issue.
Keys are redacted.
