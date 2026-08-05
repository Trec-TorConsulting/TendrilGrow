## Why

Source water chemistry drives nutrient advice (Cal-Mag demand, chlorine/chloramine
handling, baseline EC). Cultivation context today captures reservoir volume,
targets, and nutrient products — but not what water fills the reservoir — so AI
health checks guess or ignore water-source constraints.

## What Changes

- Add an editable per-grow-space **water type** select to the Cultivation Plan
  (cultivation-context helpers): Tap, RO, Filtered, Bottled, Rain, Well,
  Distilled, Spring, Mixed
- Wire the value into `GROW_CONTEXT_LABELS` so AI health checks include it
- Lightly ground feeding/dosing guidance when water type is set (e.g. RO /
  distilled → Cal-Mag priority)

## Capabilities

### New Capabilities

### Modified Capabilities
- `grow-cultivation-context`: Add water-type select to editable cultivation
  context and AI label map
- `ai-health-monitoring`: Include water type in the health-check cultivation
  context used for dosing/feeding guidance

## Impact

- `custom_components/tendrilgrow/const.py` — new `CTX_*`, options, label map
- `custom_components/tendrilgrow/select.py` — new restore-state select entity
- `strings.json` / `translations/en.json` — entity name + option labels
- `custom_components/tendrilgrow/ai/health_checks.py` — optional water-type
  grounding in the prompt
- Tests for options/i18n/default and prompt inclusion
