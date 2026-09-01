<p align="center">
  <img src="https://raw.githubusercontent.com/Trec-TorConsulting/TendrilGrow/main/docs/assets/logo.svg" alt="TendrilGrow" width="520">
</p>

# TendrilGrow

Home Assistant custom integration for indoor cultivation. One grow space per
config entry — sensors, pumps, reservoir chemistry, cultivation stage, and
camera-based AI health checks in a single [HACS](https://hacs.xyz) package.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Trec-TorConsulting&repository=TendrilGrow&category=integration)
[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=tendrilgrow)

[![lint & test](https://github.com/Trec-TorConsulting/TendrilGrow/actions/workflows/lint-test.yml/badge.svg)](https://github.com/Trec-TorConsulting/TendrilGrow/actions/workflows/lint-test.yml)
[![hassfest](https://github.com/Trec-TorConsulting/TendrilGrow/actions/workflows/hassfest.yml/badge.svg)](https://github.com/Trec-TorConsulting/TendrilGrow/actions/workflows/hassfest.yml)
[![HACS validation](https://github.com/Trec-TorConsulting/TendrilGrow/actions/workflows/hacs.yml/badge.svg)](https://github.com/Trec-TorConsulting/TendrilGrow/actions/workflows/hacs.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.2.0%2B-41BDF5?logo=home-assistant&logoColor=white)](https://www.home-assistant.io/)
[![Release](https://img.shields.io/github/v/release/Trec-TorConsulting/TendrilGrow?sort=semver)](https://github.com/Trec-TorConsulting/TendrilGrow/releases)
[![License: MIT](https://img.shields.io/github/license/Trec-TorConsulting/TendrilGrow)](LICENSE)

**[Documentation](https://trec-torconsulting.github.io/TendrilGrow/) ·
[Quick start](https://trec-torconsulting.github.io/TendrilGrow/quick-start/) ·
[Changelog](CHANGELOG.md) ·
[Discussions](https://github.com/Trec-TorConsulting/TendrilGrow/discussions) ·
[Report a bug](https://github.com/Trec-TorConsulting/TendrilGrow/issues/new/choose)**

## What it does

TendrilGrow does **not** replace your lights, sensors, or cameras. It groups
them into a grow space, tracks cultivation context, and (optionally) asks a
vision model to score plant health.

| You map | TendrilGrow adds |
| --- | --- |
| Canopy temp + humidity | VPD and dew point |
| Reservoir pH / EC / ORP / temp | Role-mapped chemistry + AI context |
| Circulation / chiller / air pumps | Switches, power, estimated daily cost |
| A camera + vision model | Health score, issues, mix-order feeding card |
| Nothing extra | Growth stage, Stage Started date, Week In Stage, flush cadence, timeline calendar, tasks |

Control stays **manual and opt-in**. You build automations; TendrilGrow does not
actuate pumps or valves on its own.

## Install with HACS

**Requirements:** Home Assistant **2026.2.0** or newer, and [HACS](https://hacs.xyz/).

1. Click **HACS** → **Custom repositories** (or use the badge above).
2. Repository:
   `https://github.com/Trec-TorConsulting/TendrilGrow`
3. Category: **Integration**.
4. Download **TendrilGrow**, then **restart Home Assistant**.
5. **Settings → Devices & Services → Add Integration → TendrilGrow**
   (or the “start setup” badge above).

Add **one integration entry per tent, room, or zone**.

Manual install (no HACS): unzip `tendrilgrow.zip` from the
[latest release](https://github.com/Trec-TorConsulting/TendrilGrow/releases)
into `/config/custom_components/tendrilgrow` and restart.

Full walkthrough with example values:
[Quick start](https://trec-torconsulting.github.io/TendrilGrow/quick-start/).

## First grow space (5 minutes)

During setup you will:

1. Name the space (`4x4 Flower`) and pick a grow type (`rdwc`, `dwc`, `soil`, …).
2. Map what you have. Skip anything you do not own. Prefer a **LocalTuya** /
   **Tuya Local** water probe; cloud Tuya polling is fallback-only.
3. Optionally enable AI (Gemini, OpenAI, or Ollama) and map a **camera**.
4. After setup, fill **Cultivation Plan** on the device: strain, Growth Stage,
   **Stage Started** (calendar date), makeup water, targets, nutrients,
   additives (include **Hydroguard** if the reservoir is live).

Week In Stage is computed from Stage Started. Changing Growth Stage resets
Stage Started to today; you can backdate it.

## Dashboards

Tracked example: [`dashboards/tendrial_grow.yaml`](dashboards/tendrial_grow.yaml)
(executive overview + one tab per zone). Entity IDs in that file are examples —
replace prefixes, or generate from your live registry:

```bash
./.venv/bin/python scripts/generate_dashboard.py          # dry run
./.venv/bin/python scripts/generate_dashboard.py --apply  # push to HA
```

Copy-paste cards (no Python required):
[Dashboards](https://trec-torconsulting.github.io/TendrilGrow/dashboards/) and
[Examples](https://trec-torconsulting.github.io/TendrilGrow/examples/).

## Documentation

| Topic | Link |
| --- | --- |
| Install + update | [Installation](https://trec-torconsulting.github.io/TendrilGrow/installation/) |
| Worked 4×4 RDWC example | [Quick start](https://trec-torconsulting.github.io/TendrilGrow/quick-start/) |
| Config flow fields | [Configuration](https://trec-torconsulting.github.io/TendrilGrow/configuration/) |
| Stage, date, feeding | [Cultivation plan](https://trec-torconsulting.github.io/TendrilGrow/cultivation/) |
| AI scoring | [AI health](https://trec-torconsulting.github.io/TendrilGrow/ai-health/) |
| Water probes | [LocalTuya / Tuya](https://trec-torconsulting.github.io/TendrilGrow/tuya-water/) |
| Entities & services | [Entities](https://trec-torconsulting.github.io/TendrilGrow/entities/), [Services](https://trec-torconsulting.github.io/TendrilGrow/services/) |
| Automations | [Examples](https://trec-torconsulting.github.io/TendrilGrow/examples/) |
| Something broke | [Troubleshooting](https://trec-torconsulting.github.io/TendrilGrow/troubleshooting/) |

## Security

API keys and Tuya secrets are redacted in diagnostics. Do not paste them into
issues. See [SECURITY.md](SECURITY.md).

## Development

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-test.txt
./.venv/bin/ruff check .
./.venv/bin/pytest -q
```

See [CONTRIBUTING.md](CONTRIBUTING.md). CI runs hassfest, HACS validation, Ruff,
and pytest.

## Disclaimer

TendrilGrow assists monitoring and decision support. It does not replace safe
electrical, environmental, or horticultural practice. Validate every automation
before you rely on it.
