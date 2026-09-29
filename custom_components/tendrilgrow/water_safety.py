"""Water safety monitoring.

Provides flow verification, leak detection, and opt-in RDWC pump shutoff.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)

from .const import (
    CONF_LEAK_DEBOUNCE_SECONDS,
    CONF_LEAK_SHUTOFF_ENABLED,
    CONF_NO_FLOW_GRACE_SECONDS,
    CONTROL_ROLE_RDWC_PUMP,
    DEFAULT_LEAK_DEBOUNCE_SECONDS,
    DEFAULT_LEAK_SHUTOFF_ENABLED,
    DEFAULT_NO_FLOW_GRACE_SECONDS,
    DOMAIN,
    SENSOR_ROLE_LEAK,
    SENSOR_ROLE_WATER_FLOW,
    WATER_SAFETY_STATUS_LEAK,
    WATER_SAFETY_STATUS_NO_FLOW,
    WATER_SAFETY_STATUS_OK,
)
from .models.grow import GrowSpace

LOGGER = logging.getLogger(__name__)


def water_safety_dispatcher_signal(entry_id: str) -> str:
    """Dispatcher signal for water-safety updates."""
    return f"{DOMAIN}_water_safety_{entry_id}"


def parse_leak_entities(val: Any) -> list[str]:
    """Parse leak entity mapping (list, comma-separated string, or empty)."""
    if isinstance(val, list):
        return [str(item).strip() for item in val if str(item).strip()]
    if isinstance(val, str):
        return [part.strip() for part in val.split(",") if part.strip()]
    return []


class WaterSafetyMonitor:
    """Monitors circulation flow and leak sensors with opt-in pump shutoff."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        grow_space: GrowSpace,
        merged_config: dict[str, Any],
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id
        self.grow_space = grow_space
        self.merged_config = merged_config

        self.flow_ok: bool = True
        self.leak_detected: bool = False
        self.status: str = WATER_SAFETY_STATUS_OK
        self.active_leaks: list[str] = []
        self.flow_rate: float | None = None
        self.shutoff_triggered: bool = False
        self.last_transition: str | None = None

        self._leak_debounce_seconds: int = max(
            0,
            int(
                merged_config.get(
                    CONF_LEAK_DEBOUNCE_SECONDS, DEFAULT_LEAK_DEBOUNCE_SECONDS
                )
            ),
        )
        self._no_flow_grace_seconds: int = max(
            1,
            int(
                merged_config.get(
                    CONF_NO_FLOW_GRACE_SECONDS, DEFAULT_NO_FLOW_GRACE_SECONDS
                )
            ),
        )
        self._leak_shutoff_enabled: bool = bool(
            merged_config.get(CONF_LEAK_SHUTOFF_ENABLED, DEFAULT_LEAK_SHUTOFF_ENABLED)
        )

        self._unsub_trackers: list[Any] = []
        self._unsub_leak_timer: Any = None
        self._unsub_flow_timer: Any = None

    @property
    def flow_entity_id(self) -> str | None:
        return self.grow_space.sensor_mappings.get(SENSOR_ROLE_WATER_FLOW)

    @property
    def leak_entities(self) -> list[str]:
        raw = self.grow_space.sensor_mappings.get(SENSOR_ROLE_LEAK)
        return parse_leak_entities(raw)

    @property
    def rdwc_pump_entity_id(self) -> str | None:
        return self.grow_space.control_mappings.get(CONTROL_ROLE_RDWC_PUMP)

    async def async_start(self) -> None:
        """Start tracking subscribed entities and initialize state."""
        entities_to_track: set[str] = set()

        if self.flow_entity_id:
            entities_to_track.add(self.flow_entity_id)

        for leak_eid in self.leak_entities:
            entities_to_track.add(leak_eid)

        if self.rdwc_pump_entity_id:
            entities_to_track.add(self.rdwc_pump_entity_id)

        if entities_to_track:
            self._unsub_trackers.append(
                async_track_state_change_event(
                    self.hass,
                    list(entities_to_track),
                    self._async_handle_state_event,
                )
            )

        # Initial evaluation
        self._evaluate_state(initial=True)

    def async_stop(self) -> None:
        """Stop tracking and cancel active timers."""
        for unsub in self._unsub_trackers:
            unsub()
        self._unsub_trackers.clear()

        if self._unsub_leak_timer:
            self._unsub_leak_timer()
            self._unsub_leak_timer = None

        if self._unsub_flow_timer:
            self._unsub_flow_timer()
            self._unsub_flow_timer = None

    @callback
    def _async_handle_state_event(self, event: Event[EventStateChangedData]) -> None:
        """Handle state change for any subscribed entity."""
        self._evaluate_state()

    def _is_pump_on(self) -> bool:
        pump_eid = self.rdwc_pump_entity_id
        if not pump_eid:
            return False
        st = self.hass.states.get(pump_eid)
        return st is not None and st.state == STATE_ON

    def _is_flow_present(self) -> bool | None:
        flow_eid = self.flow_entity_id
        if not flow_eid:
            return None
        st = self.hass.states.get(flow_eid)
        if st is None or st.state in (STATE_OFF, "unavailable", "unknown"):
            self.flow_rate = 0.0 if st and st.state == STATE_OFF else None
            return False

        if st.state in (STATE_ON, "flowing", "true", "True"):
            return True

        try:
            val = float(st.state)
            self.flow_rate = val
            return val > 0.0
        except (ValueError, TypeError):
            return False

    def _active_leak_entities(self) -> list[str]:
        active: list[str] = []
        for eid in self.leak_entities:
            st = self.hass.states.get(eid)
            if st is not None and st.state == STATE_ON:
                active.append(eid)
        return active

    def _evaluate_state(self, initial: bool = False) -> None:
        """Evaluate leak and flow state."""
        active_leaks = self._active_leak_entities()

        # 1. Leak evaluation
        if active_leaks:
            if not self.leak_detected:
                if self._leak_debounce_seconds > 0 and not initial:
                    if self._unsub_leak_timer is None:
                        self._unsub_leak_timer = async_call_later(
                            self.hass,
                            self._leak_debounce_seconds,
                            self._async_handle_leak_debounce_fired,
                        )
                else:
                    self._apply_leak_confirmed(active_leaks)
            else:
                self.active_leaks = active_leaks
        else:
            if self._unsub_leak_timer:
                self._unsub_leak_timer()
                self._unsub_leak_timer = None
            if self.leak_detected:
                self.leak_detected = False
                self.active_leaks = []
                self.shutoff_triggered = False
                self._update_status()
                self.hass.bus.async_fire(
                    "tendrilgrow_water_safety_event",
                    {
                        "entry_id": self.entry_id,
                        "space_name": self.grow_space.name,
                        "event": "leak_cleared",
                    },
                )

        # 2. Flow evaluation
        pump_on = self._is_pump_on()
        flow_present = self._is_flow_present()

        if pump_on and flow_present is False:
            if self.flow_ok:
                if self._no_flow_grace_seconds > 0 and not initial:
                    if self._unsub_flow_timer is None:
                        self._unsub_flow_timer = async_call_later(
                            self.hass,
                            self._no_flow_grace_seconds,
                            self._async_handle_flow_grace_fired,
                        )
                else:
                    self._apply_no_flow_confirmed()
        else:
            if self._unsub_flow_timer:
                self._unsub_flow_timer()
                self._unsub_flow_timer = None
            if not self.flow_ok:
                self.flow_ok = True
                self._update_status()
                self.hass.bus.async_fire(
                    "tendrilgrow_water_safety_event",
                    {
                        "entry_id": self.entry_id,
                        "space_name": self.grow_space.name,
                        "event": "flow_resumed",
                    },
                )

        self._update_status()

    @callback
    def _async_handle_leak_debounce_fired(self, _now: Any) -> None:
        """Called when leak debounce timer expires."""
        self._unsub_leak_timer = None
        active = self._active_leak_entities()
        if active:
            self._apply_leak_confirmed(active)

    def _apply_leak_confirmed(self, active_leaks: list[str]) -> None:
        """Confirm a leak and trigger alert and optional shutoff."""
        self.leak_detected = True
        self.active_leaks = active_leaks
        self._update_status()

        LOGGER.error(
            "TendrilGrow [%s]: Water leak detected on %s!",
            self.grow_space.name,
            ", ".join(active_leaks),
        )

        self.hass.bus.async_fire(
            "tendrilgrow_water_safety_event",
            {
                "entry_id": self.entry_id,
                "space_name": self.grow_space.name,
                "event": "leak_detected",
                "active_leaks": active_leaks,
            },
        )

        if self._leak_shutoff_enabled and not self.shutoff_triggered:
            self.shutoff_triggered = True
            self.hass.async_create_task(self._async_command_pump_shutoff())

    @callback
    def _async_handle_flow_grace_fired(self, _now: Any) -> None:
        """Called when no-flow grace timer expires."""
        self._unsub_flow_timer = None
        if self._is_pump_on() and self._is_flow_present() is False:
            self._apply_no_flow_confirmed()

    def _apply_no_flow_confirmed(self) -> None:
        """Confirm a no-flow condition."""
        self.flow_ok = False
        self._update_status()
        LOGGER.warning(
            "TendrilGrow [%s]: RDWC circulation pump is ON but no water flow detected!",
            self.grow_space.name,
        )
        self.hass.bus.async_fire(
            "tendrilgrow_water_safety_event",
            {
                "entry_id": self.entry_id,
                "space_name": self.grow_space.name,
                "event": "no_flow_detected",
            },
        )

    async def _async_command_pump_shutoff(self) -> None:
        """Command the RDWC pump off via Home Assistant service."""
        pump_eid = self.rdwc_pump_entity_id
        if not pump_eid:
            return

        domain = pump_eid.split(".")[0] if "." in pump_eid else "homeassistant"
        service_domain = (
            domain if domain in ("switch", "input_boolean") else "homeassistant"
        )
        LOGGER.warning(
            "TendrilGrow [%s]: Shutting down RDWC pump (%s) due to active water leak",
            self.grow_space.name,
            pump_eid,
        )
        try:
            await self.hass.services.async_call(
                service_domain,
                "turn_off",
                {"entity_id": pump_eid},
                blocking=False,
            )
            self.hass.bus.async_fire(
                "tendrilgrow_water_safety_event",
                {
                    "entry_id": self.entry_id,
                    "space_name": self.grow_space.name,
                    "event": "pump_shutoff_commanded",
                    "pump_entity_id": pump_eid,
                },
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception(
                "TendrilGrow [%s]: Failed to shut off pump %s",
                self.grow_space.name,
                pump_eid,
            )

    def _update_status(self) -> None:
        """Recalculate overall status with leak having precedence over no-flow."""
        old_status = self.status
        if self.leak_detected:
            new_status = WATER_SAFETY_STATUS_LEAK
        elif not self.flow_ok:
            new_status = WATER_SAFETY_STATUS_NO_FLOW
        else:
            new_status = WATER_SAFETY_STATUS_OK

        if new_status != old_status:
            self.status = new_status
            self.last_transition = datetime.now(UTC).isoformat()

        async_dispatcher_send(self.hass, water_safety_dispatcher_signal(self.entry_id))


async def async_setup_water_safety(
    hass: HomeAssistant,
    entry: ConfigEntry,
    grow_space: GrowSpace,
    merged_config: dict[str, Any],
) -> WaterSafetyMonitor:
    """Create and start the water safety monitor for a grow space."""
    monitor = WaterSafetyMonitor(hass, entry, grow_space, merged_config)
    await monitor.async_start()
    return monitor
