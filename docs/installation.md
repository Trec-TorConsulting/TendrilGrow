# Installation

TendrilGrow is a **HACS custom integration**. Home Assistant does not ship it
in the default store until you add this GitHub repository once.

## Requirements

- Home Assistant **2026.2.0** or newer (OS, Container, or Core).
- [HACS](https://hacs.xyz/) already installed (skip HACS only if you install
  from a GitHub release zip).
- Companion integrations **only if you use that hardware**:
    - Lights/fans/controllers (any brand; the maintainer uses Vivosun via HACS).
    - **LocalTuya** or **Tuya Local** for a Wi-Fi water probe (recommended).
    - A **camera** entity if you want AI vision checks.

!!! info "No hardcoded entities"
    TendrilGrow never assumes entity IDs. You map your own sensors, switches,
    and cameras. Any brand that already exists in Home Assistant works.

## Install with HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Trec-TorConsulting&repository=TendrilGrow&category=integration)

### Add the custom repository (once)

1. Open **HACS**.
2. Open the **⋮** menu (top right) → **Custom repositories**.
3. Repository URL:
   `https://github.com/Trec-TorConsulting/TendrilGrow`
4. Category: **Integration**.
5. **Add**.

### Download the integration

1. In HACS, search **TendrilGrow**.
2. Open it → **Download** (use the latest release, not a random commit, unless
   you are testing a PR).
3. **Restart Home Assistant.** Custom components are not loaded until restart.
4. Confirm **Settings → Devices & Services → Add Integration** lists
   **TendrilGrow**.

After a HACS download you typically see a path like:

```text
/config/custom_components/tendrilgrow
```

## Add the integration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=tendrilgrow)

1. **Settings → Devices & Services → Add Integration**.
2. Search **TendrilGrow**.
3. Complete the config flow ([Configuration](configuration.md)).
4. Repeat for each tent / room / zone — **one entry per grow space**.

Then follow the [Quick start](quick-start.md) so Cultivation Plan and chemistry
are filled in.

## Manual install (no HACS)

1. Download `tendrilgrow.zip` from the
   [latest GitHub release](https://github.com/Trec-TorConsulting/TendrilGrow/releases/latest).
2. Unzip so this folder exists:

    ```text
    /config/custom_components/tendrilgrow/manifest.json
    ```

3. Restart Home Assistant.
4. Add **TendrilGrow** from **Devices & Services**.

Do not copy only some of the Python files. The whole `tendrilgrow` package must
be present.

## Update

1. HACS → **TendrilGrow** → **Update** (or **Redownload**).
2. **Restart Home Assistant** (or at least reload custom integrations if your
   HA version offers it — a full restart is the reliable path).
3. Read [Upgrading](upgrade.md) when a release changes entities (for example
   Stage Started in 0.3.2 / Cultivation Plan ids in 0.3.3).

## Allow-list for timelapse (optional) {#allow-list-for-timelapse-optional}

If you enable camera timelapse, add the capture directory to
`configuration.yaml` and restart:

```yaml
homeassistant:
  allowlist_external_dirs:
    - /config/www/tendrilgrow
```

Default frame path is
`/config/www/tendrilgrow/<grow_slug>/timelapse/`. If the path is not
allow-listed, TendrilGrow raises a **Repair** issue and pauses scheduled
captures.

## Verify the install

| Check | Where |
| --- | --- |
| Integration loaded | **Settings → Devices & Services** shows TendrilGrow |
| Version | Device diagnostics or `custom_components/tendrilgrow/manifest.json` (`version`) |
| Device | Each grow space appears as a **TendrilGrow** device named after the space |
| Helpers | Growth Stage, Stage Started, Week In Stage exist on that device |

If **TendrilGrow** is missing from Add Integration after restart, HACS did not
land the files under `/config/custom_components/tendrilgrow`. Re-download and
restart again.
