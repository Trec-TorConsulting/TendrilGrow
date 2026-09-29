## Why

The generated Tendrial Grow dashboard is a vertical stack of entity lists and raw markdown. Reservoir chemistry, target bands, flush timing, and AI health are all present as entities, but the layout reads like a settings page, so an operator cannot see whether a tent is in range without scanning rows.

## What Changes

- Restyle the dashboard produced by `scripts/generate_dashboard.py` into a cockpit: a camera, stage and harvest timing, an AI health score with the report folded away, pH / EC / VPD shown against their target bands, band-alert and flush status, and pump power when those entities exist.
- Restyle the Executive view so each grow space shows up as a status summary (camera, AI score, out-of-range, flush due) instead of a repeated chemistry list.
- Omit any card whose entities are missing, so a space without pumps, a camera, or a VPD reading still generates a valid view.
- Keep generation opt-in: dry-run by default, `--apply` still backs up and writes only the named storage dashboard. The integration does not rewrite Lovelace on setup.
- Stay on built-in Lovelace cards. Custom cards and a Lovelace strategy stay out of this change.

## Capabilities

### New Capabilities

- `generated-dashboard`: The layout, card vocabulary, and omission rules for the dashboard that `scripts/generate_dashboard.py` builds from live grow spaces.

### Modified Capabilities

## Impact

- `scripts/generate_dashboard.py` view builders (`build_overview`, `build_space_view`, and the card helpers they call).
- New unit tests for those builders using synthetic grow-space data, with no live Home Assistant connection.
- `docs/dashboards.md`, so the documented tab contents match the cockpit.
- `dashboards/tendrial_grow.yaml` stays a live export. It updates when the maintainer exports after `--apply`, not by hand-editing entity ids in the repo.
- No Python runtime dependencies, no frontend bundle, and no change to entity unique ids or the config flow.
