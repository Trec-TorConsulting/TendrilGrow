## 1. Section builders

- [x] 1.1 Add helpers in `scripts/generate_dashboard.py` that emit a `type: sections` view, a `type: grid` section, `heading` and `tile` cards, and an entity badge with a `state: "on"` visibility condition
- [x] 1.2 Keep the card vocabulary to `heading`, `tile`, `gauge`, `picture-entity`, `entities`, `markdown`, and `history-graph`

## 2. Zone cockpit

- [x] 2.1 Rewrite `build_space_view` to emit Watch, Lifecycle, AI, Reservoir, Operations, Advisor, and Plan sections in that order, dropping a section with no entity card
- [x] 2.2 Lifecycle tiles `ctx_stage`, `ctx_stage_started`, `ctx_week_in_stage`, and `stage_projection`, plus markdown for `projected_stage_end`, `projected_harvest_date`, and `projected_ready_date`
- [x] 2.3 AI section gauges `ai_health_score` at min 0, max 100, severity red 0 / yellow 50 / green 75, and tiles summary, last check, critical alert, and the run button
- [x] 2.4 Reservoir tiles mapped `ph`, `ec`, and integration `vpd` before other mapped roles, tiles `metric_band_ph` / `metric_band_ec` / `metric_band_vpd` when present, and lists low/high bounds in one "Target bands" entities card
- [x] 2.5 Leave `ctx_target_ph` and `ctx_target_ec` off the view when the matching low/high pair exists
- [x] 2.6 Operations tiles flush suffixes and pump suffixes (`total_pump_power`, `rdwc_pump`, `chiller_pump`, `air_pump`, `{role}_power`), and the section is absent when none of those suffixes exist
- [x] 2.7 Advisor markdown templates `report` and `feeding_schedule_md` on the score entity, after Operations
- [x] 2.8 Plan lists the remaining cultivation helpers and does not repeat an entity already placed above

## 3. Executive view

- [x] 3.1 Rewrite `build_overview` as a sections view with one section per space: camera, AI gauge, summary, `metric_band_summary`, `flush_due`, and `days_until_flush`
- [x] 3.2 Add a view badge for each existing `metric_band_summary` and `flush_due`, visible only when that entity is `on`
- [x] 3.3 End with a 24-hour history graph of mapped `water_temperature` and `ph`, omitted when no space has either role

## 4. Tests

- [x] 4.1 Add `tests/test_generate_dashboard.py` that loads `scripts/generate_dashboard.py` (the `scripts` directory is not a package) and builds views from synthetic `classify()` dicts
- [x] 4.2 Cover a populated space (section order, gauge thresholds, primary-metric order, band card, Advisor templates, flush and pump tiles, plan dedupe)
- [x] 4.3 Cover omission: no camera, no VPD, no pumps, no Operations section; an `unavailable` mapped pH entity is still tiled; legacy `ctx_target_ph` is absent when the band pair exists
- [x] 4.4 Cover Executive: one section per space, badges with `state: "on"` visibility, and the history graph
- [x] 4.5 Run `pytest tests/test_generate_dashboard.py` and confirm the dry-run branch in `main()` still returns before `lovelace/config/save`

## 5. Docs

- [x] 5.1 Update `docs/dashboards.md` so a complete tab is the cockpit section order, and note that `dashboards/tendrial_grow.yaml` refreshes from `scripts/export_dashboard.py` after `--apply`
