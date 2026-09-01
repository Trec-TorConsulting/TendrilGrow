# Quick start

This page is a complete first tent. Copy the names if you want the example
entity IDs to match the YAML snippets in [Examples](examples.md).

**Example space:** 4×4 flower tent, recirculating DWC (RDWC), General Hydroponics
FloraSeries + Hydroguard, one canopy camera.

## 1. Install and restart

Follow [Installation](installation.md). Confirm TendrilGrow appears under
**Add Integration**.

## 2. Create the grow space

| Field | Example |
| --- | --- |
| Grow space name | `4x4 Flower` |
| Grow type | `rdwc` |
| Size / descriptor | `4x4` |

Home Assistant will slug entity IDs from the name, for example
`select.4x4_flower_growth_stage`. If you already created a space with a
different title, use **that** prefix everywhere below.

## 3. Map only what you have

All mappings are optional. A useful minimum for RDWC:

| Role (UI label) | Map to |
| --- | --- |
| Local water monitor | Your LocalTuya / Tuya Local probe device |
| Air temperature (canopy) | Tent air temp — **not** the reservoir probe |
| Air humidity (canopy) | Tent RH |
| Camera | The tent camera (needed for AI) |
| RDWC circulation pump | The recirc pump switch |
| Lights | Optional, for your own automations |

Leave cloud Tuya polling **off** if the local probe is bound.

If you have no water probe yet, skip it. You can still use Cultivation Plan,
flush tracking, and AI (camera only).

## 4. AI (optional)

| Setting | Example |
| --- | --- |
| Provider | `Gemini` or `OpenAI` (cloud) or `Ollama` (LAN) |
| Check interval | `12` hours |
| Critical score | `20` |
| Notify service | `notify.mobile_app_your_phone` |
| Model | A **vision** model from the discovered list |

Without a camera + vision model, AI health entities are not created. You can
add them later in **Configure**.

## 5. Fill Cultivation Plan

Open the grow-space **device** (or the Cultivation Plan card on your dashboard).

| Helper | Example | Why |
| --- | --- | --- |
| Strain / Genetics | `Example Cross F2` | Grounds AI |
| Growth Stage | `vegetative` | Stage-aware scoring and timeline |
| Stage Started | yesterday’s date if you flipped two days ago | Week In Stage = days ÷ 7 |
| Water Type | `ro` | Makeup water for fills |
| Sites / Plants | `4` | |
| Total System Volume | `13` gal | Dose math |
| Target pH | `5.8` | |
| Target EC | `1.6` | Mix-to; in-week chart still applies |
| Feed Interval | `1` | |
| Lights On | `18` | DLI estimate |
| Nutrient Line | `General Hydroponics FloraSeries` | Feeding card layout |
| Base Nutrients | `Micro, Gro, Bloom, CALiMAGic, Armor Si` | Mix order |
| Additives | `Hydroguard 2 ml/gal` | Marks the reservoir **live** |

**Week In Stage** is read-only. Change Stage Started (or Growth Stage) instead.

!!! tip "Live vs sterile"
    Listing Hydroguard (or another biological) tells the AI this is a **live**
    RDWC. Do not also list H₂O₂ / HOCl / UC Roots. See
    [AI health](ai-health.md#live-vs-sterile-reservoirs).

## 6. Record the last flush

Press **Flush Now** the next time you fully dump and refill — or press it once
now if you just did. Set **Flush Interval** to `7` (or `10`) days.

## 7. Put it on a dashboard {#7-put-it-on-a-dashboard}

Minimal Cultivation Plan card (replace the prefix if your space name differs):

```yaml
type: entities
title: Cultivation Plan
entities:
  - text.4x4_flower_strain_genetics
  - select.4x4_flower_growth_stage
  - date.4x4_flower_stage_started
  - sensor.4x4_flower_week_in_stage
  - select.4x4_flower_water_type
  - number.4x4_flower_sites_plants
  - number.4x4_flower_total_system_volume
  - number.4x4_flower_target_ph
  - number.4x4_flower_target_ec
  - text.4x4_flower_nutrient_line
  - text.4x4_flower_base_nutrients
  - text.4x4_flower_additives
```

If a row says **Entity not found**, the object id does not match your device
name. **Settings → Devices & Services → TendrilGrow → the device → entities**
shows the real IDs. After 0.3.3, storage dashboards that still pointed at the
old `number.*_week_in_stage` are rewritten on reload — [Upgrading](upgrade.md).

Full tab layout: [Dashboards](dashboards.md). More YAML: [Examples](examples.md).

## 8. Run one AI check

Press **Run AI Health Check**. Wait for **AI Last Health Check** to update.
Open **AI Health Report** and **AI Feeding Schedule** markdown cards.

Feeding should list products in mix order, for example Armor Si → CALiMAGic →
Micro → Gro → Bloom → Hydroguard → pH last.

## Done

You now have a named grow space, a cultivation clock, flush cadence, and
(optional) vision scoring. Add a second entry the same way for a mother tent or
clone dome.
