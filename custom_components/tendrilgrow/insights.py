"""Pure derived-metric helpers for TendrilGrow.

These functions are intentionally free of Home Assistant dependencies so they can
be unit-tested directly and reused by sensors, the calendar, and repairs.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from math import exp, log

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
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


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
