"""Tests for pure derived-metric helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from custom_components.tendrilgrow.insights import (
    build_grow_events,
    build_grow_tasks,
    compose_weekly_journal,
    compute_daily_energy_kwh,
    compute_dew_point_c,
    compute_dli,
    days_in_stage,
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
