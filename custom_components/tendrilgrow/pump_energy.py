"""Pump duty-cycle energy estimation for TendrilGrow."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import async_get as get_entity_registry
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PUMP_CONTROL_ROLES
from .entry_config import entry_merged_config
from .insights import compute_daily_energy_kwh

LOGGER = logging.getLogger(__name__)


def pump_energy_dispatcher_signal(entry_id: str) -> str:
    return f"{DOMAIN}_pump_energy_update_{entry_id}"


def pump_power_entity_id(hass: HomeAssistant, entry: ConfigEntry, pump_role: str) -> str | None:
    registry = get_entity_registry(hass)
    return registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_{pump_role}_power"
    )


def pump_switch_entity_id(hass: HomeAssistant, entry: ConfigEntry, pump_role: str) -> str | None:
    registry = get_entity_registry(hass)
    return registry.async_get_entity_id(
        "switch", DOMAIN, f"{entry.entry_id}_{pump_role}"
    )


@dataclass(slots=True)
class PumpEnergyState:
    """Persisted on-time counters per pump for the current local day."""

    local_day: str = ""
    pumps: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"local_day": self.local_day, "pumps": self.pumps}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PumpEnergyState:
        pumps = value.get("pumps")
        if not isinstance(pumps, dict):
            pumps = {}
        local_day = str(value.get("local_day") or "")
        return cls(local_day=local_day, pumps=dict(pumps))


async def load_pump_energy_state(store: Store[dict[str, Any]]) -> PumpEnergyState:
    payload = await store.async_load() or {}
    if not isinstance(payload, dict):
        return PumpEnergyState()
    return PumpEnergyState.from_dict(payload)


async def async_save_pump_energy_state(
    store: Store[dict[str, Any]], state: PumpEnergyState
) -> None:
    await store.async_save(state.to_dict())


def _local_day_iso(now: datetime) -> str:
    return dt_util.as_local(now).date().isoformat()


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def rollover_local_day(state: PumpEnergyState, now: datetime) -> None:
    day = _local_day_iso(now)
    if state.local_day == day:
        return
    state.local_day = day
    for pump in state.pumps.values():
        pump["seconds_on"] = 0.0


def _pump_bucket(state: PumpEnergyState, pump_role: str) -> dict[str, Any]:
    return state.pumps.setdefault(
        pump_role, {"seconds_on": 0.0, "on_since": None, "observed_since": None}
    )


def record_pump_switch_state(
    state: PumpEnergyState, pump_role: str, is_on: bool, now: datetime
) -> None:
    rollover_local_day(state, now)
    if not state.local_day:
        state.local_day = _local_day_iso(now)
    bucket = _pump_bucket(state, pump_role)
    if not bucket.get("observed_since"):
        bucket["observed_since"] = now.isoformat()

    on_since = _parse_dt(bucket.get("on_since"))
    if is_on:
        if on_since is None:
            bucket["on_since"] = now.isoformat()
        return

    if on_since is not None:
        elapsed = (now - on_since).total_seconds()
        bucket["seconds_on"] = float(bucket.get("seconds_on", 0.0)) + max(0.0, elapsed)
        bucket["on_since"] = None


def seconds_on_today(state: PumpEnergyState, pump_role: str, now: datetime) -> float:
    rollover_local_day(state, now)
    bucket = state.pumps.get(pump_role)
    if not bucket:
        return 0.0
    total = float(bucket.get("seconds_on", 0.0))
    on_since = _parse_dt(bucket.get("on_since"))
    if on_since is not None:
        total += max(0.0, (now - on_since).total_seconds())
    return total


def compute_daily_pump_energy_kwh(
    hass: HomeAssistant,
    entry: ConfigEntry,
    state: PumpEnergyState,
    now: datetime,
) -> tuple[float | None, dict[str, Any]]:
    """Estimate today's pump energy from switch on-time and power readings."""
    merged = entry_merged_config(entry)
    control_mappings = merged.get("control_mappings", {})
    rollover_local_day(state, now)
    if not state.local_day:
        state.local_day = _local_day_iso(now)

    total_kwh = 0.0
    has_value = False
    duty_cycle_known = True
    per_pump: dict[str, float] = {}

    for pump_role in PUMP_CONTROL_ROLES:
        if pump_role not in control_mappings:
            continue
        power_id = pump_power_entity_id(hass, entry, pump_role)
        watts: float | None = None
        if power_id:
            power_state = hass.states.get(power_id)
            if power_state is not None and power_state.state not in (
                "unavailable",
                "unknown",
            ):
                try:
                    watts = float(power_state.state)
                except (ValueError, TypeError):
                    watts = None

        switch_id = pump_switch_entity_id(hass, entry, pump_role)
        switch_state = hass.states.get(switch_id) if switch_id else None
        switch_known = switch_state is not None and switch_state.state not in (
            "unavailable",
            "unknown",
        )

        if watts is None:
            continue

        if switch_known:
            hours_on = seconds_on_today(state, pump_role, now) / 3600.0
            if switch_state.state == STATE_ON and hours_on == 0.0:
                # Startup mid-interval before the first transition is recorded.
                hours_on = 0.0
            pump_kwh = compute_daily_energy_kwh(watts, hours_on)
        else:
            duty_cycle_known = False
            pump_kwh = compute_daily_energy_kwh(watts, 24.0)

        if pump_kwh is None:
            continue
        total_kwh += pump_kwh
        per_pump[pump_role] = round(pump_kwh, 4)
        has_value = True

    attrs: dict[str, Any] = {
        "estimated": True,
        "duty_cycle_known": duty_cycle_known,
        "per_pump_kwh": per_pump,
    }
    if not duty_cycle_known:
        attrs["assumes_hours_per_day"] = 24
    return (round(total_kwh, 4) if has_value else None), attrs


async def async_setup_pump_energy_tracking(
    hass: HomeAssistant,
    entry: ConfigEntry,
    state: PumpEnergyState,
    store: Store[dict[str, Any]],
) -> list[Any]:
    """Track mapped pump proxy switches and persist duty-cycle state."""
    unsubs: list[Any] = []
    merged = entry_merged_config(entry)
    control_mappings = merged.get("control_mappings", {})

    async def _persist() -> None:
        try:
            await async_save_pump_energy_state(store, state)
        except Exception:  # noqa: BLE001
            LOGGER.debug("Failed to persist pump energy state for %s", entry.entry_id)
        async_dispatcher_send(hass, pump_energy_dispatcher_signal(entry.entry_id))

    @callback
    def _make_handler(pump_role: str):
        @callback
        def _on_switch(_event) -> None:
            switch_id = pump_switch_entity_id(hass, entry, pump_role)
            if not switch_id:
                return
            switch_state = hass.states.get(switch_id)
            if switch_state is None:
                return
            record_pump_switch_state(
                state,
                pump_role,
                switch_state.state == STATE_ON,
                dt_util.utcnow(),
            )
            hass.async_create_task(_persist())

        return _on_switch

    for pump_role in PUMP_CONTROL_ROLES:
        if pump_role not in control_mappings:
            continue
        switch_id = pump_switch_entity_id(hass, entry, pump_role)
        if not switch_id:
            continue
        switch_state = hass.states.get(switch_id)
        if switch_state is not None:
            record_pump_switch_state(
                state,
                pump_role,
                switch_state.state == STATE_ON,
                dt_util.utcnow(),
            )
        unsubs.append(
            async_track_state_change_event(hass, switch_id, _make_handler(pump_role))
        )

    return unsubs
