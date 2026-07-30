# Dashboards

An example multi-tab Lovelace dashboard is tracked in the repository at
[`dashboards/tendrial_grow.yaml`](https://github.com/Trec-TorConsulting/TendrilGrow/blob/main/dashboards/tendrial_grow.yaml).
It includes an executive overview plus a per-zone tab with camera snapshots,
reservoir chemistry, trends, AI health, the cultivation plan, a grow timeline,
and a **Reservoir Flush** card.

!!! info "Entity IDs are examples"
    The entity IDs in the file are specific to the maintainer's grow spaces
    (`3x3_mothers_tent_*`, `4x4_full_cycle_tent_*`). Adjust the prefixes for your
    own spaces, or generate a fresh dashboard from your live entities (below).

## Reuse the example

- Open the dashboard's **Raw configuration editor** in Home Assistant and paste
  the file contents, or
- Add individual cards with **Add card → Manual**.

## Helper scripts

The repository includes scripts that read `HA_URL`/`HA_TOKEN` from a local
`.env`. They are read-safe by default and never print your token.

=== "Generate from live grow spaces"

    Build an Executive overview plus one tab per configured grow space from the
    live entity registry and role mappings. Adding a hub and re-running adds its
    tab and refreshes the overview.

    ```bash
    ./.venv/bin/python scripts/generate_dashboard.py          # dry run
    ./.venv/bin/python scripts/generate_dashboard.py --apply  # push to HA
    ```

=== "Export live → repo"

    ```bash
    ./.venv/bin/python scripts/export_dashboard.py <url_path>
    ```

=== "Import repo → live"

    Dry-run by default; add `--apply` to save. It backs up the live config first
    and warns about any referenced entity IDs that do not exist.

    ```bash
    ./.venv/bin/python scripts/import_dashboard.py <url_path>
    ./.venv/bin/python scripts/import_dashboard.py <url_path> --apply
    ```

!!! tip
    `--apply` writes a backup of the live dashboard first, and the token is never
    printed or logged.
