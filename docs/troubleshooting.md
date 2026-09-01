# Troubleshooting

## Entity not found on Cultivation Plan

After 0.3.2, Week In Stage is a **sensor** and Stage Started is a **date**.
Dashboards that still list `number.*_week_in_stage`, or that guessed the wrong
prefix (`date.stage_started` vs `date.4x4_flower_stage_started`), show
**Entity not found** on every grow-space tab.

1. Update to **0.3.3 or newer** and **restart** Home Assistant.
2. Wait ~15 seconds (storage dashboards are rewritten on reload).
3. Confirm IDs on the grow-space **device** entity list.
4. YAML-mode dashboards are not auto-edited — paste IDs by hand or
   `scripts/generate_dashboard.py --apply`.

See [Upgrading](upgrade.md#upgrade-033).

## AI health entities are missing {#ai-health-entities-are-missing}

Created only when all three are true:

1. A `camera` is mapped.
2. Provider is `Gemini`, `OpenAI`, or `Ollama` — not `None`.
3. The model is **vision-capable**.

**Configure** the entry, then reload TendrilGrow.

## Model discovery failed

Network, key, or endpoint issue. Enter the model name manually. Confirm the
account can use a vision model.

## VPD looks wrong

VPD uses **canopy air** temp + humidity, not the water probe.

- Map tent air to `temperature` / `humidity`.
- Map the reservoir probe to `water_temperature`.

## Tuya / LocalTuya sensors missing

1. Probe exists in HA and is selected as **Local water monitor**.
2. Do not run LocalTuya and Tuya Local on the **same** physical device.
3. Cloud fallback: access ID/secret/region/device IDs; poll ≥ 600 s on Trial.
4. Call [`tendrilgrow.rebuild_automap`](services.md#tendrilgrowrebuild_automap).
5. Logger: `custom_components.tendrilgrow`.
6. After leaving cloud sensors, regenerate the dashboard so cards are not still
   on `sensor.*_tuya_*`.

## Entities unavailable after an update

Restart Home Assistant after HACS updates. New platforms (date, etc.) load
only then.

## Timelapse capture paused / Repair issue

Add the capture dir to `allowlist_external_dirs` and restart.
[Installation](installation.md#allow-list-for-timelapse-optional). Then capture
one frame so the scheduler resumes.

## Flush Due never clears

**Flush Now** (or `tendrilgrow.mark_flush`) records a completed dump/refill.
TendrilGrow does not drain the reservoir for you.

## AI says sterile but you run Hydroguard

Put Hydroguard in **Additives**. Do not list H₂O₂ / HOCl / UC Roots on the
same space. Grow type should be `rdwc` or `dwc` if that is the system.

## Collecting diagnostics

**Settings → Devices & Services → TendrilGrow → entry → ⋮ → Download
diagnostics**. Keys and Tuya secrets are redacted.

## Still stuck?

- [Discussions](https://github.com/Trec-TorConsulting/TendrilGrow/discussions)
- [Bug report](https://github.com/Trec-TorConsulting/TendrilGrow/issues/new/choose)
  with HA version, TendrilGrow version, install type, and sanitized logs.
