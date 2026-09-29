## Context

`scripts/generate_dashboard.py` already discovers every TendrilGrow helper by unique-id suffix and every mapped sensor by diagnostics role. `build_overview` and `build_space_view` then emit a masonry stack of `entities` and `markdown` cards. Target bands (`ctx_target_ph_low` / `_high`, and the EC and VPD pairs), metric-band problem sensors (`metric_band_ph`, `metric_band_ec`, `metric_band_vpd`, `metric_band_summary`), and pump entities (`total_pump_power`, `rdwc_pump`, `chiller_pump`, `air_pump`, and each `{role}_power`) land in `reg` and never get a card.

The live dashboard is storage-mode Lovelace at `tendrial-grow`. Generation stays a maintainer script: dry-run by default, `--apply` backs up then saves. `fix-lovelace-migration` is removing unsolicited dashboard writes from the integration; this change must leave that boundary alone.

## Goals / Non-Goals

**Goals:**

- Emit a sections-view cockpit from the existing `classify()` data.
- Put pH, EC, and VPD next to the problem sensors that already compare them to the live band.
- Show AI score and summary above the fold, and the report plus feeding schedule below it.
- Show flush status, and pump switches plus power, when those entities exist.
- Give the Executive view one status section per grow space plus the existing 24h water-temperature and pH history graph.
- Prove the layout with unit tests on synthetic spaces.

**Non-Goals:**

- Custom Lit cards (`add-dashboard-cards`) and a Lovelace strategy.
- New entities, unique-id changes, or config-flow changes.
- The integration loading or saving Lovelace during setup.
- Timelapse, calendar, and to-do entities on this dashboard.
- Pixel-perfect column spans. Structure is specified; span numbers can move after the first live look.

## Decisions

### Sections views of built-in cards

Each view is `type: sections`. Cards are limited to `heading`, `tile`, `gauge`, `picture-entity`, `entities`, `markdown`, and `history-graph`, nested in `type: grid` sections.

Alternative: keep masonry and only swap `entities` for `tile`. That still scrolls as one column on the zone tab and cannot put the camera beside status. Sections are the current Lovelace layout and need no custom card.

Alternative: revive `add-dashboard-cards`. The cockpit composition is what this change is proving. A Lit bundle would freeze it before the three live tents have been looked at.

### Tiles plus problem sensors for chemistry, a gauge only for AI score

pH, EC, and VPD render as `tile` cards bound to the mapped sensor (VPD from the integration entity `vpd`). Each primary metric also gets a `tile` on `metric_band_{metric}` when that suffix exists. Those binary sensors are `device_class: problem`, so the tile is the in-range signal and it tracks operator edits to the band without regenerating.

The six target-band number entities render once, in an `entities` card titled "Target bands", so the numeric window is visible and editable. When a low/high pair exists, the legacy single `ctx_target_ph` or `ctx_target_ec` entity is left off the dashboard.

AI health score stays a `gauge` with `min: 0`, `max: 100`, and severity thresholds `red: 0`, `yellow: 50`, `green: 75` (higher value takes the higher threshold's color).

Alternative: bake gauge `severity` from the current band values at generate time. Those numbers go stale the moment the operator edits a target, and a gauge severity map cannot express "inside this window."

### Zone tab order

One view per space, `path: zone-{slug}`, icon `mdi:sprout`, `max_columns: 2`.

1. **Watch** — `picture-entity` when `camera` is mapped. `column_span: 2`.
2. **Lifecycle** — heading with the space title, then tiles for `ctx_stage`, `ctx_stage_started`, `ctx_week_in_stage`, and `stage_projection`. A markdown card renders `projected_stage_end`, `projected_harvest_date`, and `projected_ready_date` from the projection sensor.
3. **AI** — gauge for `ai_health_score`, tiles for `ai_health_summary`, `ai_health_last_check`, `ai_health_critical_alert`, and `run_ai_health_check`.
4. **Reservoir** — tiles for mapped `ph`, `ec`, then `vpd`, then any other mapped role in `SENSOR_ROLE_ORDER` (`cf`, `tds`, `orp`, `water_temperature`, `temperature`, `humidity`, `light_ppfd`). Band tiles and the target-band `entities` card follow.
5. **Operations** — flush tiles (`flush_due`, `days_until_flush`, `days_since_flush`, `next_flush_due`, `last_flush`, `flush_now`, `flush_interval_days`) and pump tiles (`total_pump_power`, `rdwc_pump`, `chiller_pump`, `air_pump`, and each `{role}_power`). The section is omitted when none of those suffixes exist.
6. **Advisor** — markdown for `state_attr(score, 'report')` and `state_attr(score, 'feeding_schedule_md')`. `column_span: 2`. This section sits after the cockpit so the report is below the first screen.
7. **Plan** — one `entities` card for remaining cultivation helpers: strain, water type, site count, reservoir volume, feed interval, lights-on hours, lights-on time, lights-off time, runoff target, nutrient line, base nutrients, additives. Helpers already placed above are not repeated.

A section is omitted when it would contain no entity card. Headings alone are not emitted.

### Executive view

`path: overview`, title Executive, icon `mdi:view-dashboard`, `max_columns` equal to the number of spaces (at least 1).

- One section per space: heading, camera tile-sized `picture-entity` when mapped, AI gauge, summary tile, `metric_band_summary` tile, `flush_due` tile, `days_until_flush` tile.
- View `badges`: an entity badge for each space's `metric_band_summary` and `flush_due`, each with a visibility condition `state: "on"` on that same entity. A quiet tent adds nothing to the badge row.
- One trailing section, spanning all columns, with the 24h `history-graph` of each space's mapped `water_temperature` and `ph`. The section is omitted when neither role is mapped on any space.

### Missing entities

`classify()` is unchanged. Builders skip a card when the suffix or sensor role is absent. They do not emit placeholder entities. Runtime `unavailable` is left to Lovelace; generation does not drop an entity because its current state is unknown.

### Tests call the builders

`build_space_view` and `build_overview` stay pure functions in `scripts/generate_dashboard.py`. Tests construct the dict `classify()` returns and assert section order, entity placement, the card-type allowlist, badge visibility, and omission. No WebSocket and no `--apply` in unit tests.

### Docs follow the cockpit

`docs/dashboards.md` replaces the "entity list plus markdown dump" description with the section order above. `dashboards/tendrial_grow.yaml` remains an export of the live dashboard and is refreshed by `scripts/export_dashboard.py` after a maintainer `--apply`.

## Risks / Trade-offs

- [Sections YAML is rejected by an older Home Assistant] → The project targets the current HA release. The first `--apply` is a dry-run review away from the backup the script already writes.
- [`--apply` replaces hand edits on `tendrial-grow`] → Same rule as today. The pre-save backup in the temp directory is the rollback.
- [Tiles for a long secondary sensor list recreate the old wall] → Primary metrics and their band sensors come first; CF, TDS, ORP, and the rest follow in the same Reservoir section and only when mapped.
- [Gauge color for AI score depends on HA applying the highest matching severity threshold] → Keep the existing 0 / 50 / 75 thresholds and cover them in the builder test so a restyle does not invert them.
- [Column spans look wrong on the phone] → Spans are not part of the spec. Adjust after viewing Executive and one zone tab on the live dashboard.

## Migration Plan

1. Land the builder and unit tests.
2. Dry-run `scripts/generate_dashboard.py` and read the temp YAML.
3. `--apply` to `tendrial-grow` (the script writes a backup first).
4. Look at Executive and each zone tab. Adjust span only if a section wraps badly.
5. `scripts/export_dashboard.py` to refresh `dashboards/tendrial_grow.yaml`.

Rollback is restoring that backup through `scripts/import_dashboard.py --apply`, or saving the backup YAML in the raw configuration editor. Entity ids are untouched, so rollback is dashboard config only.

## Open Questions

None that block implementation. Span numbers are tuned on the live dashboard after the first apply; tests lock entity placement.
