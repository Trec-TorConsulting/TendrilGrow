# Dashboards

TendrilGrow does not inject a Lovelace dashboard by itself. You add cards, paste
the example YAML, or generate tabs from the live entity registry.

## What a complete tab includes

1. Camera snapshot  
2. Telemetry (pH, EC, ORP, temps, VPD)  
3. Reservoir Flush  
4. Grow Timeline (stage, Stage Started, weeks, projections)  
5. AI Health + report + **AI Feeding Schedule** markdown  
6. Cultivation Plan entities  

Ready-made YAML: [Examples](examples.md). Cultivation Plan IDs:
[Cultivation plan](cultivation.md).

## Example file in the repo

[`dashboards/tendrial_grow.yaml`](https://github.com/Trec-TorConsulting/TendrilGrow/blob/main/dashboards/tendrial_grow.yaml)
is an executive overview plus per-zone tabs from a real install.

!!! info "Entity IDs are examples"
    Prefixes such as `3x3_mothers_tent_` and `4x4_full_cycle_tent_` are
    **that** install. Copy a card, then replace prefixes from
    **Settings → Devices → your grow space → Entities**.

### Paste into Lovelace (no Python)

1. **Settings → Dashboards → Add dashboard** (or open an existing one).
2. **Edit dashboard → ⋮ → Raw configuration editor** (storage mode), or add
   **Manual** cards.
3. Paste a card from [Examples](examples.md) and fix entity IDs until no row
   says Entity not found.

## Generate from live grow spaces

On a machine with the repo, a venv, and a long-lived token in `.env`
(`HA_URL`, `HA_TOKEN` — never commit the token):

=== "Generate from live grow spaces"

    Builds an Executive overview plus one tab per TendrilGrow config entry.

    ```bash
    ./.venv/bin/python scripts/generate_dashboard.py          # dry run
    ./.venv/bin/python scripts/generate_dashboard.py --apply  # push to HA
    ```

    Default URL path: `tendrial-grow`. Override with
    `--url-path your-dashboard`.

=== "Export live → repo"

    ```bash
    ./.venv/bin/python scripts/export_dashboard.py
    ./.venv/bin/python scripts/export_dashboard.py tendrial-grow
    ```

=== "Import repo → live"

    Dry-run by default. `--apply` saves and writes a backup first. Warns if
    referenced entity IDs do not exist.

    ```bash
    ./.venv/bin/python scripts/import_dashboard.py
    ./.venv/bin/python scripts/import_dashboard.py tendrial-grow --apply
    ```

The token is never printed. `--apply` backups land under the system temp
directory.

## After an update

If Cultivation Plan shows **Entity not found**, see [Upgrading](upgrade.md)
(0.3.3 rewrites storage dashboards that still used `number.*_week_in_stage`).
YAML-mode dashboards are not rewritten — update them by hand or generate
again.
