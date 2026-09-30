"""Tests for pure derived-metric helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from custom_components.tendrilgrow.const import (
    DRIFT_DILUTE,
    DRIFT_EQUILIBRIUM,
    DRIFT_FEED,
    DRIFT_ROOT_CHECK,
)
from custom_components.tendrilgrow.insights import (
    build_grow_events,
    build_grow_tasks,
    compose_weekly_journal,
    compute_daily_energy_kwh,
    compute_days_since_flip,
    compute_dew_point_c,
    compute_dew_point_margin,
    compute_dli,
    compute_leaf_vpd_kpa,
    compute_mold_risk,
    compute_photoperiod_hours,
    compute_transpiration_rate,
    days_in_stage,
    diagnose_reservoir_drift,
    estimate_daily_cost,
    weeks_in_stage,
)


def test_dew_point_at_saturation_equals_temperature() -> None:
    assert round(compute_dew_point_c(20.0, 100.0), 2) == 20.0


def test_dew_point_typical() -> None:
    # 20 C / 50% RH -> ~9.25 C
    assert round(compute_dew_point_c(20.0, 50.0), 1) == 9.3


def test_dew_point_invalid_inputs() -> None:
    assert compute_dew_point_c(None, 50.0) is None
    assert compute_dew_point_c(20.0, 0.0) is None
    assert compute_dew_point_c(20.0, 150.0) is None


def test_dli_typical_veg() -> None:
    # 400 umol/m2/s for 18 h -> 25.92 mol/m2/day
    assert round(compute_dli(400.0, 18.0), 2) == 25.92


def test_dli_invalid_inputs() -> None:
    assert compute_dli(None, 18.0) is None
    assert compute_dli(400.0, None) is None
    assert compute_dli(-1.0, 18.0) is None


def test_daily_energy_and_cost() -> None:
    assert compute_daily_energy_kwh(100.0) == 2.4
    assert compute_daily_energy_kwh(100.0, hours=12.0) == 1.2
    assert compute_daily_energy_kwh(None) is None
    assert estimate_daily_cost(2.4, 0.15) == 0.36
    assert estimate_daily_cost(None, 0.15) is None
    assert estimate_daily_cost(2.4, None) is None


def test_build_grow_events_orders_and_skips_past() -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    projection = {
        "stage": "mid_flower",
        "projected_stage_end": "2026-08-10",
        "projected_harvest_date": "2026-09-01",
        "projected_ready_date": "2026-07-01",  # past -> skipped
    }
    flush_due = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)
    events = build_grow_events(projection, flush_due, now)

    summaries = [e["summary"] for e in events]
    assert "Ready (cured)" not in summaries  # past date skipped
    # sorted by date: flush 08-05, stage end 08-10, harvest 09-01
    assert summaries == [
        "Reservoir flush due",
        "Stage ends (mid_flower)",
        "Projected harvest",
    ]
    # all-day event spans one day
    first = events[0]
    assert first["end"] - first["start"] == timedelta(days=1)


def test_build_grow_events_empty_when_no_dates() -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    assert build_grow_events({"stage": "mother"}, None, now) == []


def test_build_grow_tasks_collects_due_items() -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    flush = {"due": True, "next_due": datetime(2026, 7, 29, tzinfo=UTC)}
    projection = {
        "stage": "late_flower",
        "days_remaining": 2,
        "projected_stage_end": "2026-08-01",
    }
    tasks = build_grow_tasks(flush, projection, True, now)
    assert [t["uid"] for t in tasks] == ["flush", "stage", "ai"]


def test_build_grow_tasks_empty_when_nothing_due() -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    tasks = build_grow_tasks(
        {"due": False},
        {"stage": "vegetative", "days_remaining": 20},
        False,
        now,
    )
    assert tasks == []


def test_compose_weekly_journal_summarizes_recent() -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    checks = [
        SimpleNamespace(
            checked_at=datetime(2026, 7, 25, tzinfo=UTC),
            score=60,
            summary="ok",
            issues=["tip burn"],
        ),
        SimpleNamespace(
            checked_at=datetime(2026, 7, 29, tzinfo=UTC),
            score=80,
            summary="better",
            issues=["tip burn", "light stress"],
        ),
    ]
    journal = compose_weekly_journal(checks, now)
    assert "2 checks" in journal["headline"]
    assert "avg 70/100" in journal["headline"]
    assert "improving" in journal["headline"]
    assert "tip burn" in journal["markdown"]


def test_compose_weekly_journal_empty_when_no_recent() -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    old = [
        SimpleNamespace(
            checked_at=datetime(2026, 7, 1, tzinfo=UTC),
            score=50,
            summary="",
            issues=[],
        )
    ]
    assert compose_weekly_journal(old, now)["headline"].startswith("No AI checks")
    assert compose_weekly_journal([], now)["headline"].startswith("No AI checks")


def test_days_in_stage_prefers_start_date() -> None:
    now = datetime(2026, 7, 29, tzinfo=UTC)
    assert days_in_stage(now, stage_started=date(2026, 7, 15)) == 14
    assert days_in_stage(now, stage_started="2026-07-15") == 14
    assert days_in_stage(now, week_in_stage="2") == 14
    assert weeks_in_stage(14) == 2.0
    assert days_in_stage(now, stage_started="2026-07-15", week_in_stage="9") == 14


def test_leaf_vpd_with_measured_and_offset() -> None:
    # Air 25 C, 60% RH:
    # Saturated air VP = ~3.17 kPa, ea = 3.17 * 0.6 = ~1.90 kPa
    # Leaf 23 C: es_leaf = ~2.81 kPa -> VPD = 2.81 - 1.90 = ~0.91 kPa
    vpd_measured = compute_leaf_vpd_kpa(25.0, 60.0, leaf_temp_c=23.0)
    assert vpd_measured is not None
    assert 0.85 <= vpd_measured <= 0.95

    # With -3.0 F offset (-1.67 C) on 25 C -> ~23.33 C leaf
    vpd_offset = compute_leaf_vpd_kpa(25.0, 60.0, offset_f=-3.0)
    assert vpd_offset is not None
    assert 0.90 <= vpd_offset <= 1.05

    # Missing inputs
    assert compute_leaf_vpd_kpa(None, 60.0) is None
    assert compute_leaf_vpd_kpa(25.0, 0.0) is None
    assert compute_leaf_vpd_kpa(25.0, 110.0) is None


def test_dew_point_margin_and_mold_risk() -> None:
    # Air 20 C, 50% RH -> Dew point ~9.3 C -> Margin ~10.7 C
    margin = compute_dew_point_margin(20.0, 50.0)
    assert margin == 10.7

    # With leaf temp 18 C -> Margin = 18 - 9.3 = 8.7 C
    margin_leaf = compute_dew_point_margin(20.0, 50.0, leaf_temp_c=18.0)
    assert margin_leaf == 8.7

    # Critical margin (margin <= 2.0 C)
    is_risk, factors, rec = compute_mold_risk(1.5, 60.0, "vegetative")
    assert is_risk is True
    assert "dew_point_margin_critical" in factors

    # High humidity in late flower (RH >= 65%)
    is_risk, factors, rec = compute_mold_risk(4.0, 68.0, "late_flower")
    assert is_risk is True
    assert "high_humidity_in_vulnerable_stage" in factors

    # Safe vegetative conditions (RH 64%, margin 4.0 C)
    is_risk, factors, rec = compute_mold_risk(4.0, 64.0, "vegetative")
    assert is_risk is False
    assert factors == []


def test_diagnose_reservoir_drift() -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    t_start = now - timedelta(hours=18)

    # 1. Critical pH plunge (< 5.2)
    diag = diagnose_reservoir_drift([], 1.2, 5.0)
    assert diag["status"] == DRIFT_ROOT_CHECK

    # 2. Anaerobic root rot pattern: pH drops 0.5 with steady EC
    samples = [(t_start, 1.2, 6.0, 10.0), (now, 1.2, 5.5, 9.0)]
    diag = diagnose_reservoir_drift(samples, 1.2, 5.5, 9.0)
    assert diag["status"] == DRIFT_ROOT_CHECK

    # 3. Transpiration outstrips feeding: EC rises, pH drops
    samples = [(t_start, 1.2, 6.0, 10.0), (now, 1.35, 5.8, 8.5)]
    diag = diagnose_reservoir_drift(samples, 1.35, 5.8, 8.5)
    assert diag["status"] == DRIFT_DILUTE

    # 4. Hungry plants: EC drops, pH rises
    samples = [(t_start, 1.4, 5.8, 10.0), (now, 1.2, 6.1, 8.5)]
    diag = diagnose_reservoir_drift(samples, 1.2, 6.1, 8.5)
    assert diag["status"] == DRIFT_FEED

    # 5. Equilibrium
    samples = [(t_start, 1.2, 5.9, 10.0), (now, 1.22, 5.95, 8.5)]
    diag = diagnose_reservoir_drift(samples, 1.22, 5.95, 8.5)
    assert diag["status"] == DRIFT_EQUILIBRIUM


def test_transpiration_rate_and_stalled() -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    t_start = now - timedelta(hours=24)

    # Normal: 1.0 gallon consumed over 24h
    samples = [(t_start, 10.0), (now, 9.0)]
    res = compute_transpiration_rate(samples)
    assert res["status"] == "normal"
    assert res["rate_daily"] == 1.0

    # Stalled: < 0.05 gallons consumed over 24h
    samples_stalled = [(t_start, 10.0), (now, 9.98)]
    res_stalled = compute_transpiration_rate(samples_stalled)
    assert res_stalled["status"] == "stalled"


def test_compute_days_since_flip() -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    # Non-flowering stages return None
    assert compute_days_since_flip("vegetative", "2026-07-10", now) is None
    assert compute_days_since_flip("mother", "2026-07-10", now) is None

    # Flowering stages return days
    assert compute_days_since_flip("early_flower", "2026-07-16", now) == 14
    assert compute_days_since_flip("mid_flower", "2026-07-10", now) == 20


def test_compute_photoperiod_hours() -> None:
    # 06:00 to 24:00 (00:00) -> 18h
    assert compute_photoperiod_hours("06:00", "00:00") == 18.0
    # 18:00 to 12:00 next day (overnight) -> 18h
    assert compute_photoperiod_hours("18:00", "12:00") == 18.0
    # 08:00 to 20:00 -> 12h
    assert compute_photoperiod_hours("08:00", "20:00") == 12.0
    # Invalid inputs
    assert compute_photoperiod_hours(None, "12:00") is None
