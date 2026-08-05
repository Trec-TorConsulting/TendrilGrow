## 1. Constants and select entity

- [x] 1.1 Add `CTX_WATER_TYPE`, `DEFAULT_WATER_TYPE`, `WATER_TYPE_OPTIONS`, and `GROW_CONTEXT_LABELS` entry in `const.py`
- [x] 1.2 Add `GrowWaterTypeSelect` in `select.py` (restore-state, device-grouped, default `tap`)
- [x] 1.3 Add `water_type` select strings in `strings.json` and `translations/en.json`

## 2. AI prompt grounding

- [x] 2.1 Include brief water-type dosing grounding in `_build_prompt` when `water_type` is present

## 3. Tests

- [x] 3.1 Cover water-type options, i18n labels, and default
- [x] 3.2 Assert `water_type` appears in the health prompt with source-water grounding for RO

## 4. Spec sync

- [x] 4.1 Keep change delta specs accurate; main specs sync at archive
- [x] 4.2 Document Water Type on entities + AI health docs
