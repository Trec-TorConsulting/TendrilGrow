"""Pure derived-metric helpers for TendrilGrow.

These functions are intentionally free of Home Assistant dependencies so they can
be unit-tested directly and reused by sensors, the calendar, and repairs.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from math import exp, log
from typing import Any

# Magnus-Tetens coefficients (over water), matching the VPD formula's basis.
_MAGNUS_A = 17.27
_MAGNUS_B = 237.7


def compute_dew_point_c(
    temperature_c: float | None, humidity_pct: float | None
) -> float | None:
    """Dew point in Celsius from air temperature (C) and relative humidity (%).

    Returns None when inputs are missing or out of range.
    """
    if temperature_c is None or humidity_pct is None:
        return None
    if humidity_pct <= 0 or humidity_pct > 100:
        return None
    gamma = (_MAGNUS_A * temperature_c) / (_MAGNUS_B + temperature_c) + log(
        humidity_pct / 100.0
    )
    return (_MAGNUS_B * gamma) / (_MAGNUS_A - gamma)


def compute_vapor_pressure_kpa(temperature_c: float | None) -> float | None:
    """Saturation vapor pressure (kPa) at a temperature, for reference."""
    if temperature_c is None:
        return None
    return 0.6108 * exp((_MAGNUS_A * temperature_c) / (temperature_c + _MAGNUS_B))


def compute_leaf_vpd_kpa(
    air_temp_c: float | None,
    humidity_pct: float | None,
    leaf_temp_c: float | None = None,
    offset_f: float | None = None,
) -> float | None:
    """Compute true leaf VPD (kPa) using measured or offset leaf temperature.

    Leaf VPD = e_s(T_leaf) - e_a(T_air, RH).
    If leaf_temp_c is not provided and offset_f is provided,
    T_leaf_c = air_temp_c + (offset_f * 5.0 / 9.0).
    """
    if air_temp_c is None or humidity_pct is None:
        return None
    if humidity_pct <= 0 or humidity_pct > 100:
        return None

    if leaf_temp_c is None and offset_f is not None:
        effective_leaf_c = air_temp_c + (offset_f * 5.0 / 9.0)
    elif leaf_temp_c is not None:
        effective_leaf_c = leaf_temp_c
    else:
        effective_leaf_c = air_temp_c

    e_s_leaf = compute_vapor_pressure_kpa(effective_leaf_c)
    e_s_air = compute_vapor_pressure_kpa(air_temp_c)
    if e_s_leaf is None or e_s_air is None:
        return None

    e_a = e_s_air * (humidity_pct / 100.0)
    vpd = e_s_leaf - e_a
    return round(max(0.0, vpd), 2)


def compute_dew_point_margin(
    air_temp_c: float | None,
    humidity_pct: float | None,
    leaf_temp_c: float | None = None,
) -> float | None:
    """Calculate dew point margin in Celsius (T_surface - T_dew).

    Uses leaf temperature when available, otherwise air temperature.
    """
    dew_point_c = compute_dew_point_c(air_temp_c, humidity_pct)
    if dew_point_c is None:
        return None
    target_temp = leaf_temp_c if leaf_temp_c is not None else air_temp_c
    if target_temp is None:
        return None
    return round(target_temp - dew_point_c, 1)


def compute_mold_risk(
    margin_c: float | None,
    humidity_pct: float | None,
    stage: str | None = None,
) -> tuple[bool, list[str], str]:
    """Evaluate Botrytis / powdery mildew risk based on margin, RH, and stage.

    Returns (is_risk, risk_factors, recommendation).
    """
    if margin_c is None and humidity_pct is None:
        return False, [], "No climate data available."

    factors: list[str] = []
    # Condensation boundary threshold (< 2.0 C / 3.6 F)
    if margin_c is not None and margin_c <= 2.0:
        factors.append("dew_point_margin_critical")

    # High humidity in flowering / drying / curing
    flower_or_cure = (stage or "").lower() in (
        "mid_flower",
        "late_flower",
        "flush",
        "dry",
        "cure",
    )
    if humidity_pct is not None:
        if flower_or_cure and humidity_pct >= 65.0:
            factors.append("high_humidity_in_vulnerable_stage")
        elif humidity_pct >= 75.0:
            factors.append("excessive_relative_humidity")

    if factors:
        rec = (
            "High mold / Botrytis risk! Increase airflow and dehumidification to "
            "widen dew point margin."
        )
        return True, factors, rec
    return False, [], "Climate within safe mold-prevention margins."


def diagnose_reservoir_drift(
    samples: list[tuple[datetime, float, float, float | None]],
    current_ec: float | None,
    current_ph: float | None,
    current_water: float | None = None,
) -> dict[str, Any]:
    """Diagnose RDWC reservoir dynamics from rolling EC, pH, and water trend.

    Samples are (timestamp, ec, ph, water_level).
    """
    from .const import DRIFT_DILUTE, DRIFT_EQUILIBRIUM, DRIFT_FEED, DRIFT_ROOT_CHECK

    result: dict[str, Any] = {
        "status": DRIFT_EQUILIBRIUM,
        "ec_delta_24h": None,
        "ph_delta_24h": None,
        "water_delta_24h": None,
        "recommendation": "Nutrient solution is in equilibrium.",
    }

    if current_ph is not None and current_ph < 5.2:
        result["status"] = DRIFT_ROOT_CHECK
        result["recommendation"] = (
            f"Critical acid plunge detected (pH {current_ph:.2f} < 5.2). "
            "Inspect root zone immediately for Pythium/root rot, slime, and "
            "verify oxygenation."
        )
        return result

    if current_ec is None or current_ph is None or not samples:
        return result

    # Find oldest sample within the last 12-24 hours
    now = samples[-1][0] if samples else datetime.now()
    baseline_sample = None
    for ts, ec, ph, wl in samples:
        age_hours = (now - ts).total_seconds() / 3600.0
        if age_hours >= 6.0:  # At least 6h of trend
            baseline_sample = (ts, ec, ph, wl)
            break

    if baseline_sample is None:
        result["recommendation"] = "Collecting baseline data for drift analysis."
        return result

    _bts, base_ec, base_ph, base_wl = baseline_sample
    ec_delta = round(current_ec - base_ec, 2)
    ph_delta = round(current_ph - base_ph, 2)
    water_delta = (
        round(current_water - base_wl, 2)
        if current_water is not None and base_wl is not None
        else None
    )

    result["ec_delta_24h"] = ec_delta
    result["ph_delta_24h"] = ph_delta
    result["water_delta_24h"] = water_delta

    # Pathogen root plunge check: pH drop >= 0.4 while EC is steady or rising
    if ph_delta <= -0.40 and ec_delta >= -0.05:
        result["status"] = DRIFT_ROOT_CHECK
        result["recommendation"] = (
            f"Abnormal pH drop ({ph_delta:+.2f}) with steady/rising EC "
            f"({ec_delta:+.2f}). Possible root pathogen activity or hypoxia."
        )
    # Transpiration > feeding: salts concentrating (EC rising, pH falling)
    elif (ec_delta >= 0.10 and ph_delta <= -0.15) or ec_delta >= 0.15:
        result["status"] = DRIFT_DILUTE
        result["recommendation"] = (
            f"Transpiration is outstripping nutrient uptake (EC {ec_delta:+.2f}, "
            f"pH {ph_delta:+.2f}). Dilute with fresh pH-balanced top-off water."
        )
    # Feeding > transpiration: plants hungry (EC falling, pH rising)
    elif (ec_delta <= -0.10 and ph_delta >= 0.15) or ec_delta <= -0.15:
        result["status"] = DRIFT_FEED
        result["recommendation"] = (
            f"Heavy nutrient uptake observed (EC {ec_delta:+.2f}, "
            f"pH {ph_delta:+.2f}). Top off reservoir with nutrient solution."
        )
    else:
        result["status"] = DRIFT_EQUILIBRIUM
        result["recommendation"] = "Nutrient and water consumption are balanced."

    return result


def compute_transpiration_rate(
    samples: list[tuple[datetime, float]],
) -> dict[str, Any]:
    """Compute daily transpiration rate from water level time-series.

    Returns dict with 'rate_daily', 'status' ('normal', 'stalled', or 'unknown').
    """
    if len(samples) < 2:
        return {"rate_daily": None, "status": "unknown"}

    t_start, w_start = samples[0]
    t_end, w_end = samples[-1]
    duration_days = (t_end - t_start).total_seconds() / 86400.0

    if duration_days < 0.25:  # Need at least 6 hours
        return {"rate_daily": None, "status": "unknown"}

    delta_water = w_start - w_end  # Water consumed
    rate_daily = round(delta_water / duration_days, 2)

    status = "normal"
    if duration_days >= 0.75 and delta_water <= 0.05:
        status = "stalled"

    return {"rate_daily": rate_daily, "status": status}


def compute_days_since_flip(
    stage: str | None,
    stage_started: object | None,
    now: datetime,
    flip_date: object | None = None,
) -> int | None:
    """Calculate elapsed days since the 12/12 photoperiod flip.

    Returns None for non-flowering stages (seedling, mother, clone, vegetative).
    """
    stage_str = (stage or "").strip().lower()
    if stage_str not in ("early_flower", "mid_flower", "late_flower", "flush"):
        return None

    started = _parse_iso_date(flip_date) or _parse_iso_date(stage_started)
    if started is None:
        return None
    return max(0, (now.date() - started).days)


def compute_photoperiod_hours(
    lights_on: str | time | None,
    lights_off: str | time | None,
) -> float | None:
    """Calculate photoperiod hours from lights on and lights off times.

    Supports crossover past midnight (e.g. 18:00 on, 12:00 off -> 18.0 hours).
    """
    from datetime import time as dt_time

    def _to_minutes(val: str | time | None) -> int | None:
        if val is None:
            return None
        if isinstance(val, dt_time):
            return val.hour * 60 + val.minute
        if isinstance(val, str) and ":" in val:
            parts = val.split(":")
            try:
                return int(parts[0]) * 60 + int(parts[1])
            except (ValueError, IndexError):
                return None
        return None

    on_min = _to_minutes(lights_on)
    off_min = _to_minutes(lights_off)
    if on_min is None or off_min is None:
        return None

    if off_min >= on_min:
        diff_min = off_min - on_min
    else:
        diff_min = (1440 - on_min) + off_min

    return round(diff_min / 60.0, 1)


def compute_dli(
    ppfd_umol_m2_s: float | None, photoperiod_hours: float | None
) -> float | None:
    """Estimated Daily Light Integral (mol/m^2/day).

    DLI = PPFD (umol/m^2/s) x photoperiod (s) / 1e6. This assumes a roughly
    constant PPFD across the photoperiod, which holds for fixed-output LED grows;
    it is an estimate, not an integrated measurement.
    """
    if ppfd_umol_m2_s is None or photoperiod_hours is None:
        return None
    if ppfd_umol_m2_s < 0 or photoperiod_hours < 0:
        return None
    return ppfd_umol_m2_s * photoperiod_hours * 3600.0 / 1_000_000.0


def compute_daily_energy_kwh(
    power_w: float | None, hours: float = 24.0
) -> float | None:
    """Estimated energy (kWh) for a constant power draw over ``hours``."""
    if power_w is None or power_w < 0 or hours < 0:
        return None
    return power_w * hours / 1000.0


def estimate_daily_cost(
    energy_kwh: float | None, price_per_kwh: float | None
) -> float | None:
    """Estimated cost for a given daily energy and unit price."""
    if energy_kwh is None or price_per_kwh is None or price_per_kwh < 0:
        return None
    return energy_kwh * price_per_kwh


def _parse_iso_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def days_in_stage(
    now: datetime,
    *,
    stage_started: object | None = None,
    week_in_stage: object | None = None,
) -> int:
    """Elapsed whole days in the current stage.

    Prefer an operator-entered stage-start date. Fall back to week-in-stage × 7
    for older data that has not been migrated yet.
    """
    started = _parse_iso_date(stage_started)
    if started is not None:
        return max(0, (now.date() - started).days)
    try:
        weeks = float(week_in_stage)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        weeks = 0.0
    return max(0, int(round(weeks * 7)))


def weeks_in_stage(days: int) -> float:
    """Elapsed weeks, one decimal, from whole days in stage."""
    return round(max(0, days) / 7.0, 1)


def build_grow_events(
    projection: dict[str, object | None],
    flush_next_due: datetime | None,
    now: datetime,
) -> list[dict[str, object]]:
    """Build calendar events from a stage projection and the next flush due.

    Each event is a dict with ``summary`` and an all-day ``start``/``end`` date.
    Past-dated projections are skipped. Milestones are de-duplicated by date and
    summary so overlapping stage/harvest/ready dates do not repeat.
    """
    today = now.date()
    events: list[dict[str, object]] = []
    seen: set[tuple[str, date]] = set()

    def _add(summary: str, day: date | None) -> None:
        if day is None or day < today:
            return
        key = (summary, day)
        if key in seen:
            return
        seen.add(key)
        events.append(
            {"summary": summary, "start": day, "end": day + timedelta(days=1)}
        )

    stage = projection.get("stage")
    stage_label = f" ({stage})" if isinstance(stage, str) and stage else ""
    _add(
        f"Stage ends{stage_label}",
        _parse_iso_date(projection.get("projected_stage_end")),
    )
    _add("Projected harvest", _parse_iso_date(projection.get("projected_harvest_date")))
    _add("Ready (cured)", _parse_iso_date(projection.get("projected_ready_date")))
    if flush_next_due is not None:
        _add("Reservoir flush due", flush_next_due.date())

    events.sort(key=lambda e: e["start"])
    return events


def build_grow_tasks(
    flush_status: dict | None,
    projection: dict[str, object | None] | None,
    ai_critical: bool,
    now: datetime,
) -> list[dict[str, object]]:
    """Build actionable grow tasks from current flush, stage, and AI state."""
    tasks: list[dict[str, object]] = []
    if flush_status and flush_status.get("due"):
        due = flush_status.get("next_due")
        tasks.append(
            {
                "uid": "flush",
                "summary": "Flush and refill the reservoir",
                "due": due.date() if isinstance(due, datetime) else None,
            }
        )
    projection = projection or {}
    days_remaining = projection.get("days_remaining")
    stage = projection.get("stage")
    if isinstance(days_remaining, int) and days_remaining <= 3 and stage:
        tasks.append(
            {
                "uid": "stage",
                "summary": f"Stage '{stage}' ends soon \u2014 prepare the transition",
                "due": _parse_iso_date(projection.get("projected_stage_end")),
            }
        )
    if ai_critical:
        tasks.append(
            {
                "uid": "ai",
                "summary": "Review the critical AI health alert",
                "due": None,
            }
        )
    return tasks


def compose_weekly_journal(checks: object, now: datetime) -> dict[str, str]:
    """Summarize the last 7 days of recorded AI health checks as markdown.

    ``checks`` is any iterable of objects exposing ``checked_at`` (datetime),
    ``score`` (int | None), ``summary`` (str), and ``issues`` (list[str]).
    """
    week_ago = now - timedelta(days=7)
    recent = [
        c
        for c in (checks or [])
        if getattr(c, "checked_at", None) is not None and c.checked_at >= week_ago
    ]
    if not recent:
        return {
            "headline": "No AI checks in the last 7 days",
            "markdown": "_No AI health checks were recorded this week._",
        }
    scores = [c.score for c in recent if getattr(c, "score", None) is not None]
    avg = round(sum(scores) / len(scores)) if scores else None
    trend = None
    if len(scores) >= 2:
        delta = scores[-1] - scores[0]
        trend = "improving" if delta > 3 else "declining" if delta < -3 else "steady"
    issues: list[str] = []
    for check in recent:
        for issue in getattr(check, "issues", None) or []:
            text = str(issue).strip()
            if text and text not in issues:
                issues.append(text)
    latest_summary = str(getattr(recent[-1], "summary", "") or "").strip()

    lines = ["### Weekly grow journal", "", f"- Checks recorded: {len(recent)}"]
    if avg is not None:
        lines.append(f"- Average score: {avg}/100")
    if trend:
        lines.append(f"- Trend: {trend}")
    if latest_summary:
        lines.append(f"- Latest: {latest_summary}")
    if issues:
        lines.append("- Issues noted: " + ", ".join(issues[:5]))

    headline = f"{len(recent)} checks"
    if avg is not None:
        headline += f", avg {avg}/100"
    if trend:
        headline += f" ({trend})"
    return {"headline": headline, "markdown": "\n".join(lines)}
