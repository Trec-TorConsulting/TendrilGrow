"""Tests for AI health-check prompt building and result parsing."""

from __future__ import annotations

from custom_components.tendrilgrow.ai.health_checks import (
    AIHealthResult,
    _build_prompt,
    _coerce_result,
)
from custom_components.tendrilgrow.models.grow import GrowSpace


def _grow_space() -> GrowSpace:
    return GrowSpace.new(name="Tent A", grow_type="rdwc", descriptor="3x3")


def test_build_prompt_includes_context_and_metrics() -> None:
    prompt = _build_prompt(
        _grow_space(),
        {
            "ph": ("5.9", ""),
            "ec": ("1.6", "mS/cm"),
            "temperature": ("72", "\u00b0F"),
            "humidity": ("65", "%"),
            "water_temperature": ("65", "\u00b0F"),
        },
        {
            "growth_stage": "mid_flower",
            "nutrient_line": "Brand X",
            "strain_genetics": "OG Kush",
            "week_in_stage": "3",
            "reservoir_volume_gal": "13",
        },
        retention_days=30,
    )

    assert "master cannabis cultivation agronomist" in prompt
    assert "Primary objective for the 'mid_flower' stage" in prompt
    assert "Prioritize QUALITY" in prompt
    assert "growth_stage: mid_flower" in prompt
    assert "nutrient_line: Brand X" in prompt
    assert "strain_genetics: OG Kush" in prompt
    assert "pH: 5.9" in prompt
    assert "Air Temperature: 72 \u00b0F" in prompt
    assert "Air Humidity: 65 %" in prompt
    assert "Water/Reservoir Temperature: 65 \u00b0F" in prompt
    assert "Derived VPD" in prompt
    assert "observations" in prompt
    # New calibration, rubric, dosing, and feeding-schedule sections.
    assert "Calibration targets for current stage 'mid_flower'" in prompt
    assert "Mobile nutrients" in prompt
    assert "Immobile nutrients" in prompt
    assert "confidence_rationale" in prompt
    assert "feeding_schedule" in prompt
    assert "13 gallons" in prompt


def test_build_prompt_handles_empty_context_and_metrics() -> None:
    prompt = _build_prompt(_grow_space(), {}, {}, retention_days=7)

    assert "- none provided" in prompt
    assert "- no telemetry available" in prompt


def test_coerce_result_parses_rich_json() -> None:
    raw = (
        '{"score": 82, "confidence": 74, '
        '"confidence_rationale": "clear image, on-target pH", '
        '"severity": "Low", "summary": "Healthy canopy", '
        '"observations": ["even canopy"], "issues": ["minor tip burn"], '
        '"recommended_actions": ["reduce EC to 1.4"], '
        '"feeding_schedule": ["Days 1-3: EC 1.4, pH 5.9, total 49ml Cal-Mag"]}'
    )

    result = _coerce_result(raw, "gemini", "model-x", "manual")

    assert result.score == 82
    assert result.confidence == 74
    assert result.confidence_rationale == "clear image, on-target pH"
    assert result.severity == "low"
    assert result.observations == ["even canopy"]
    assert result.issues == ["minor tip burn"]
    assert result.recommended_actions == ["reduce EC to 1.4"]
    assert result.feeding_schedule == ["Days 1-3: EC 1.4, pH 5.9, total 49ml Cal-Mag"]


def test_coerce_result_falls_back_on_non_json() -> None:
    result = _coerce_result("not json here", "openai", "gpt", "scheduled")

    assert result.score is None
    assert result.confidence is None
    assert result.severity == "unknown"
    assert result.summary == "not json here"


def test_result_roundtrip_preserves_new_fields() -> None:
    raw = (
        '{"score": 50, "confidence": 60, "confidence_rationale": "ok", '
        '"severity": "medium", "summary": "ok", "observations": ["a"], '
        '"feeding_schedule": ["step1"]}'
    )
    result = _coerce_result(raw, "gemini", "model-x", "manual")

    restored = AIHealthResult.from_dict(result.to_dict())

    assert restored.score == 50
    assert restored.confidence == 60
    assert restored.confidence_rationale == "ok"
    assert restored.observations == ["a"]
    assert restored.feeding_schedule == ["step1"]
