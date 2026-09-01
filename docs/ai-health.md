# AI health checks

TendrilGrow can send a camera snapshot plus cultivation context to a
vision-capable model and return an agronomy-style report.

## What a check produces

- **Health score** 0–100 (quality-first; not “did the model see a plant”).
- **Observations**, **issues**, **recommended actions**.
- **Feeding schedule** as readable mix-order markdown
  (`feeding_schedule_md` on the score entity).

Results fill the AI entities and are stored for the retention window
(default 30 days).

## Requirements

1. Map a **camera** on the grow space.
2. Provider is not `None`.
3. The selected model must accept **images**.

If any of those are missing, AI entities are not created.
[Troubleshooting](troubleshooting.md#ai-health-entities-are-missing).

## Providers

| Provider | Notes |
| --- | --- |
| `None` | AI off for this space. |
| `Gemini` | Google Gemini (API key). |
| `OpenAI` | OpenAI (API key). |
| `Ollama` | LAN/self-hosted; set the endpoint (e.g. `http://192.168.1.10:11434`). |

After credentials, TendrilGrow discovers models. If discovery fails, type a
model name manually.

Cloud providers bill per their own pricing. Lower the check interval to spend
less. Ollama stays on your network.

## When checks run

- **Scheduled:** default every **12 hours**.
- **On demand:** **Run AI Health Check** button or
  [`tendrilgrow.run_ai_health_check`](services.md#tendrilgrowrun_ai_health_check).

Example:

```yaml
action: tendrilgrow.run_ai_health_check
data:
  reason: After reservoir change
```

## Critical alerts

Score **at or below** the threshold (default **20**) → persistent notification
and optional `notify.*`. Alerts are de-duplicated.

## Stage-aware objectives

Uses **Growth Stage** ([Cultivation plan](cultivation.md)):

- **Mothers** — health and structure (never flowered).
- **Clones** — rooting.
- **Flower** — quality and finish.
- **Dry / cure** — drying, not reservoir EC.

Per-stage pH / EC / VPD bands calibrate the prompt.

## Live vs sterile reservoirs {#live-vs-sterile-reservoirs}

The prompt classifies the reservoir from **grow type**, **Additives**, and
**Base Nutrients**:

| Class | How | Chemistry |
| --- | --- | --- |
| **Live** | Hydroguard / Bacillus / biologicals, **or** grow type RDWC/DWC **without** a listed sterilant | ORP ~200–500 mV is not “critically low DO”. Water **65–68 °F** is in-range (concern from ~72 °F). Do not demand 650–850 mV disinfection ORP. |
| **Sterile** | Additives list H₂O₂, HOCl, UC Roots, or similar oxidizer | Sterile ORP band still applies. Do not combine with Hydroguard. |

EC inside the nutrient-line **week band** is not diagnosed as underfeeding
against a higher mix-to Target EC.

Vegetative VPD around **0.7–1.2 kPa** is treated as acceptable, not a
nitpick vs 0.8–1.1.

## Grounding context

Keep Cultivation Plan honest: strain, Stage Started, water type, volume,
targets, nutrient line, additives, flush status. Garbage in, garbage out.

## Feeding card

Markdown is numbered mix order when the line looks like GH FloraSeries:
Armor Si → CALiMAGic → Micro → Gro → Bloom → Hydroguard → pH last.
See [Cultivation plan](cultivation.md#mix-order-feeding-card).

Lovelace:

```yaml
type: markdown
title: AI Feeding Schedule
content: "{{ state_attr('sensor.4x4_flower_ai_health_score', 'feeding_schedule_md') }}"
```

## Secrets

API keys are redacted in diagnostics and logs. Never paste them into issues.
