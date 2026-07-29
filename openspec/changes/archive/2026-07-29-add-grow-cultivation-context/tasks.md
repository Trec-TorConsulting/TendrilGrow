# Tasks: add-grow-cultivation-context

> Retroactive change. All tasks are **complete** — they document code already
> shipped in `custom_components/tendrilgrow/`. Checkboxes reflect implemented
> behavior.

## 1. Context entities

- [x] 1.1 Add `GrowStageSelect` (RestoreEntity) with `STAGE_OPTIONS` (`select.py`)
- [x] 1.2 Add `GrowContextNumber` (RestoreNumber) for week, reservoir volume, site count, target pH/EC, feed interval, lights-on hours, runoff target (`number.py`)
- [x] 1.3 Add `GrowContextText` (TextEntity + RestoreEntity) for strain, nutrient line, base nutrients, additives (`text.py`)
- [x] 1.4 Group entities under the grow-space device via `grow_device_info` (`entity.py`)

## 2. Constants and consumption

- [x] 2.1 Add `CTX_*` keys, `STAGE_OPTIONS`, `STAGE_TARGETS`, and `GROW_CONTEXT_LABELS` (`const.py`)
- [x] 2.2 Register `select`, `number`, and `text` platforms and forward them per entry (`__init__.py`)
- [x] 2.3 Read context by unique-id suffix in the AI runtime; proceed when unset (`ai/health_checks.py`)
