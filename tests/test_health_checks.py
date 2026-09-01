"""Tests for AI health-check prompt building and result parsing."""

from __future__ import annotations

from custom_components.tendrilgrow.ai.health_checks import (
    AIHealthResult,
    _build_prompt,
    _coerce_result,
    classify_reservoir_biology,
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
            "water_type": "ro",
        },
        retention_days=30,
    )

    assert "master cannabis cultivation agronomist" in prompt
    assert "Primary objective for the 'mid_flower' stage" in prompt
    assert "Prioritize QUALITY" in prompt
    assert "growth_stage: mid_flower" in prompt
    assert "nutrient_line: Brand X" in prompt
    assert "strain_genetics: OG Kush" in prompt
    assert "water_type: ro" in prompt
    assert "near-zero mineral baseline" in prompt
    assert "Cal-Mag" in prompt
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


def test_hydroguard_and_rdwc_classify_as_live() -> None:
    assert classify_reservoir_biology("rdwc", "Hydroguard") == "live"
    assert classify_reservoir_biology("rdwc", "") == "live"
    assert classify_reservoir_biology("dwc", "beneficial bacteria") == "live"
    assert classify_reservoir_biology("soil", "Hydroguard") == "live"
    assert classify_reservoir_biology("soil", "") == "unknown"
    assert classify_reservoir_biology("rdwc", "H2O2") == "sterile"
    assert classify_reservoir_biology("rdwc", "Hydroguard and H2O2") == "mixed"


def test_live_rdwc_prompt_rejects_sterile_orp_and_65f_water() -> None:
    prompt = _build_prompt(
        _grow_space(),
        {
            "orp": ("239", "mV"),
            "ec": ("1.021", "mS/cm"),
            "water_temperature": ("65.3", "°F"),
            "temperature": ("75", "°F"),
            "humidity": ("65", "%"),
        },
        {
            "growth_stage": "vegetative",
            "additives": "Hydroguard",
            "nutrient_line": "GH Flora",
            "target_ec_ms_cm": "1.6",
            "stage_started_on": "2026-08-18",
        },
        retention_days=30,
    )

    assert "LIVE" in prompt
    assert "Hydroguard" in prompt
    assert "650-850 mV" in prompt
    assert "do NOT apply that target to a live system" in prompt
    assert "NOT critically low" in prompt
    assert "ORP is NOT dissolved oxygen" in prompt
    assert "65-68 F" in prompt
    assert "not an upper limit" in prompt
    assert "Do not write an Issue for 65-68 F water" in prompt
    assert "0.70-1.20 kPa" in prompt
    assert "early veg 0.9-1.1 is on-target" in prompt
    assert "week_in_stage:" in prompt
    assert "Armor Si" in prompt
    assert "SEMICOLONS" in prompt
    # Vegetative VPD band widened from peer-reviewed sources.
    assert "VPD 0.7-1.2 kPa" in prompt


def test_sterile_oxidizer_prompt_uses_disinfection_orp() -> None:
    prompt = _build_prompt(
        GrowSpace.new(name="Sterile", grow_type="rdwc"),
        {},
        {"additives": "hydrogen peroxide UC Roots"},
        retention_days=7,
    )
    assert "STERILE" in prompt
    assert "disinfection ORP 650-850 mV" in prompt
    assert "do not recommend hydroguard" in prompt.lower()

