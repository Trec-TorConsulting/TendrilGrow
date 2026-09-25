"""Unit tests for pump duty-cycle energy helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from custom_components.tendrilgrow.const import CONTROL_ROLE_RDWC_PUMP
from custom_components.tendrilgrow.insights import compute_daily_energy_kwh
from custom_components.tendrilgrow.pump_energy import (
    PumpEnergyState,
    record_pump_switch_state,
    seconds_on_today,
)


def test_one_hour_at_100w_yields_0_1_kwh() -> None:
    assert compute_daily_energy_kwh(100.0, 1.0) == 0.1


def test_switch_on_for_one_hour_records_3600_seconds() -> None:
    state = PumpEnergyState()
    start = datetime(2026, 9, 25, 10, 0, tzinfo=UTC)
    end = datetime(2026, 9, 25, 11, 0, tzinfo=UTC)
    record_pump_switch_state(state, CONTROL_ROLE_RDWC_PUMP, True, start)
    record_pump_switch_state(state, CONTROL_ROLE_RDWC_PUMP, False, end)
    assert seconds_on_today(state, CONTROL_ROLE_RDWC_PUMP, end) == 3600.0


def test_switch_stays_off_contributes_zero_seconds() -> None:
    state = PumpEnergyState()
    now = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
    record_pump_switch_state(state, CONTROL_ROLE_RDWC_PUMP, False, now)
    assert seconds_on_today(state, CONTROL_ROLE_RDWC_PUMP, now) == 0.0
