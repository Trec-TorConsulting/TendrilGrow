# Cultivation plan

Cultivation Plan is the set of helpers on each grow-space device that tell
TendrilGrow (and the AI advisor) **what you are growing and how**. Fill them
the same week you add the integration — they matter more than a perfect sensor
map.

## Growth Stage

Persisted snake_case values with human-readable labels in the UI:

`seedling` → `mother` → `clone` → `vegetative` → `early_flower` →
`mid_flower` → `late_flower` → `flush` → `harvest` → `dry` → `cure` → `ready`

Default is **vegetative**. Mothers stay on `mother` indefinitely. `ready` is
terminal (packaged / stored).

AI objectives change with stage: mothers (structure), clones (rooting), flower
(quality), dry/cure (moisture), not “make it look like mid-flower.”

## Stage Started and Week In Stage {#stage-started-and-week-in-stage}

| Entity | Domain | You edit? |
| --- | --- | --- |
| Stage Started | `date` | Yes |
| Week In Stage | `sensor` (weeks, one decimal) | No — computed |

**Week In Stage** = days since Stage Started ÷ 7.

Example: Stage Started `2026-08-18`, today `2026-09-01` → 14 days → **2.0 wk**.

Changing **Growth Stage** sets Stage Started to **today**. If you flipped the
tent three days ago and then remembered to change the select, open Stage
Started and pick that date.

On upgrade from the old Week In Stage **number**, week 2 becomes a start date
about 14 days ago.

These values drive:

- AI feeding week (GH FloraSeries bands, etc.)
- Stage projection (days left, projected harvest / ready)
- Grow Timeline calendar events

## Makeup water

**Water Type:** `tap`, `ro`, `filtered`, `bottled`, `rain`, `well`,
`distilled`, `spring`, `mixed`. Default `tap`.

Used when the advisor talks about fills and flushes — not a live TDS probe.

## Targets and inventory

| Helper | Typical RDWC veg |
| --- | --- |
| Sites / Plants | `4` |
| Total System Volume | gallons of the **whole** loop |
| Target pH | `5.8`–`6.0` |
| Target EC | mix-to, e.g. `1.6` |
| Feed Interval | days between reservoir adjustments |
| Lights On | photoperiod hours (DLI uses this) |
| Runoff Target | coco/soil; ignore in RDWC if unused |
| Strain / Genetics | text |
| Nutrient Line | e.g. `General Hydroponics FloraSeries` |
| Base Nutrients | products in the three-part / cal-mag / silica set |
| Additives | biologicals, enzymes — **list Hydroguard here for live RDWC** |

## Mix order (feeding card) {#mix-order-feeding-card}

When Nutrient Line / Base Nutrients look like GH FloraSeries, the **AI Feeding
Schedule** markdown is expanded into a numbered mix order:

1. Armor Si (in water first)
2. CALiMAGic
3. FloraMicro
4. FloraGro
5. FloraBloom
6. Hydroguard last among additives (not with oxidizers)
7. pH last

Keep Hydroguard **out** of the same reservoir as H₂O₂, HOCl, or UC Roots.

## Dashboard

See [Quick start](quick-start.md#7-put-it-on-a-dashboard) for an entities card
and [Dashboards](dashboards.md) for the full tab. Entity IDs follow the grow
space name, matching **Growth Stage** (for example `date.clone_stage_started`
when the select is `select.clone_growth_stage`).
