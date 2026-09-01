"""Tests for the grow lifecycle stages and stage-projection sensor."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from custom_components.tendrilgrow.ai.health_checks import _build_prompt
from custom_components.tendrilgrow.const import (
    DEFAULT_STAGE,
    DEFAULT_WATER_TYPE,
    STAGE_DURATIONS_DAYS,
    STAGE_OPTIONS,
    STAGE_PIPELINE,
    STAGE_TARGETS,
    WATER_TYPE_OPTIONS,
)
from custom_components.tendrilgrow.models.grow import GrowSpace
from custom_components.tendrilgrow.select import GrowStageSelect, GrowWaterTypeSelect
from custom_components.tendrilgrow.sensor import compute_stage_projection

ROOT = Path(__file__).resolve().parents[1]
_STRINGS = json.loads(
    (ROOT / "custom_components/tendrilgrow/strings.json").read_text(encoding="utf-8")
)


def _grow_space() -> GrowSpace:
    return GrowSpace.new(name="Tent A", grow_type="rdwc", descriptor="3x3")


def test_stage_invariants() -> None:
    labels = _STRINGS["entity"]["select"]["growth_stage"]["state"]
    for stage in STAGE_OPTIONS:
        assert stage in labels, f"missing i18n label for {stage}"

    assert DEFAULT_STAGE in STAGE_OPTIONS
    for new_stage in ("mother", "clone", "harvest", "dry", "cure", "ready"):
        assert new_stage in STAGE_OPTIONS

    # mother and clone carry reservoir targets; post-harvest stages do not.
    assert "mother" in STAGE_TARGETS
    assert "clone" in STAGE_TARGETS
    for post in ("harvest", "dry", "cure", "ready"):
        assert post not in STAGE_TARGETS

    # Indefinite / terminal stages have no duration.
    assert STAGE_DURATIONS_DAYS["mother"] is None
    assert STAGE_DURATIONS_DAYS["ready"] is None
    # Every bounded stage sits on the projection pipeline.
    for stage, duration in STAGE_DURATIONS_DAYS.items():
        if duration is not None:
            assert stage in STAGE_PIPELINE


def test_water_type_invariants() -> None:
    labels = _STRINGS["entity"]["select"]["water_type"]["state"]
    for water_type in WATER_TYPE_OPTIONS:
        assert water_type in labels, f"missing i18n label for {water_type}"
    assert DEFAULT_WATER_TYPE in WATER_TYPE_OPTIONS
    assert DEFAULT_WATER_TYPE == "tap"


def test_select_default_is_vegetative_regardless_of_order() -> None:
    entry = SimpleNamespace(entry_id="abc123", title="Tent A")
    select = GrowStageSelect(entry)
    assert select.current_option == "vegetative"
    assert DEFAULT_STAGE == "vegetative"


def test_water_type_select_defaults_to_tap() -> None:
    entry = SimpleNamespace(entry_id="abc123", title="Tent A")
    select = GrowWaterTypeSelect(entry)
    assert select.current_option == "tap"
    assert set(select.options) == set(WATER_TYPE_OPTIONS)


def test_prompt_objective_is_stage_aware() -> None:
    def prompt_for(stage: str) -> str:
        return _build_prompt(
            _grow_space(), {}, {"growth_stage": stage}, retention_days=30
        )

    mother = prompt_for("mother")
    assert "Primary objective for the 'mother' stage" in mother
    assert "NEVER be flowered" in mother
    assert "Prioritize QUALITY" not in mother

    clone = prompt_for("clone")
    assert "unrooted cuttings" in clone
    assert "Prioritize QUALITY" not in clone

    dry = prompt_for("dry")
    assert "drying" in dry
    assert "Ignore pH/EC" in dry


def test_projection_pre_harvest_stage() -> None:
    now = datetime(2026, 7, 29, tzinfo=UTC)
    projection = compute_stage_projection("vegetative", "2", now)

    assert projection["days_in_stage"] == 14
    assert projection["days_remaining"] == 14  # 28-day veg, 2 weeks elapsed
    assert projection["pipeline_position"] == STAGE_PIPELINE.index("vegetative") + 1
    assert projection["projected_stage_end"] == "2026-08-12"
    assert projection["projected_harvest_date"] is not None
    assert projection["projected_ready_date"] is not None
    assert projection["projected_harvest_date"] < projection["projected_ready_date"]


def test_projection_from_stage_started_date() -> None:
    now = datetime(2026, 7, 29, tzinfo=UTC)
    projection = compute_stage_projection(
        "vegetative", None, now, stage_started="2026-07-15"
    )
    assert projection["days_in_stage"] == 14
    assert projection["weeks_in_stage"] == 2.0
    assert projection["days_remaining"] == 14
    assert projection["stage_started"] == "2026-07-15"


def test_projection_indefinite_and_terminal_stages() -> None:
    now = datetime(2026, 7, 29, tzinfo=UTC)

    mother = compute_stage_projection("mother", "6", now)
    assert mother["days_remaining"] is None
    assert mother["projected_harvest_date"] is None
    assert mother["projected_ready_date"] is None
    assert mother["pipeline_position"] is None

    ready = compute_stage_projection("ready", "1", now)
    assert ready["days_remaining"] is None
    assert ready["projected_ready_date"] is None
    assert ready["pipeline_position"] == STAGE_PIPELINE.index("ready") + 1
