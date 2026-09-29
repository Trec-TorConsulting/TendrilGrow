"""Pump power monitoring sensors for TendrilGrow."""

from __future__ import annotations

import sys

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_registry import async_get as get_entity_registry
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)

from ..const import PUMP_LABELS, PUMP_POWER_ROLE_FOR
from ..entity import grow_device_info
from ..entry_config import entry_merged_config
from ..pump_energy import pump_power_entity_id


def _resolve_pump_power_id(
    hass: HomeAssistant, entry: ConfigEntry, pump_role: str
) -> str | None:
    sensor_mod = sys.modules.get("custom_components.tendrilgrow.sensor")
    if sensor_mod is not None and hasattr(sensor_mod, "pump_power_entity_id"):
        return sensor_mod.pump_power_entity_id(hass, entry, pump_role)
    return pump_power_entity_id(hass, entry, pump_role)


async def _resolve_pump_power_source(
    hass: HomeAssistant,
    entry: ConfigEntry,
    pump_role: str,
) -> str | None:
    """Resolve power source for a pump: explicit mapping or auto-discovery.

    Returns entity_id of power sensor or None if not found.
    """
    merged = entry_merged_config(entry)
    sensor_mappings = merged.get("sensor_mappings", {})
    control_mappings = merged.get("control_mappings", {})

    # Check explicit power mapping first.
    power_role = PUMP_POWER_ROLE_FOR.get(pump_role)
    if power_role and power_role in sensor_mappings:
        return sensor_mappings[power_role]

    # Try auto-discovery from the pump switch's device.
    if pump_role not in control_mappings:
        return None

    pump_entity_id = control_mappings[pump_role]
    entity_registry = get_entity_registry(hass)
    pump_entity = entity_registry.async_get(pump_entity_id)

    if pump_entity is None or pump_entity.device_id is None:
        return None

    # Find power sensors on the same device.
    for entity in entity_registry.entities.values():
        if (
            entity.device_id == pump_entity.device_id
            and entity.domain == "sensor"
            and entity.device_class == SensorDeviceClass.POWER
        ):
            return entity.entity_id

    return None


class TendrilGrowPumpPowerSensor(SensorEntity):
    """Power sensor for a pump control entity."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        pump_role: str,
        power_entity_id: str | None,
    ) -> None:
        """Initialize pump power sensor."""
        self.hass = hass
        self._entry = entry
        self._pump_role = pump_role
        self._power_entity_id = power_entity_id
        self._unsub_state_change: object = None

        # Use pump label for display name.
        pump_label = PUMP_LABELS.get(pump_role, pump_role)
        self._attr_unique_id = f"{entry.entry_id}_{pump_role}_power"
        self._attr_name = f"{pump_label} Power"
        self._attr_device_info = grow_device_info(entry)

    async def async_added_to_hass(self) -> None:
        """Subscribe to power entity state changes."""
        if self._power_entity_id:
            self._unsub_state_change = async_track_state_change_event(
                self.hass,
                self._power_entity_id,
                self._on_power_state_change,
            )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from state changes."""
        if self._unsub_state_change:
            self._unsub_state_change()

    @property
    def available(self) -> bool:
        """Return availability based on power source state."""
        if not self._power_entity_id:
            return False
        state = self.hass.states.get(self._power_entity_id)
        return state is not None and state.state not in (
            "unavailable",
            "unknown",
        )

    @property
    def native_value(self) -> float | None:
        """Return power value from source entity."""
        if not self._power_entity_id:
            return None
        state = self.hass.states.get(self._power_entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    @callback
    def _on_power_state_change(self, event):
        """Handle state change in power entity."""
        self.async_write_ha_state()


class TendrilGrowTotalPumpPowerSensor(SensorEntity):
    """Total power sensor summing all mapped pump powers."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False
    _attr_name = "Total Pump Power"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        pump_roles: list[str],
    ) -> None:
        """Initialize total pump power sensor."""
        self.hass = hass
        self._entry = entry
        self._pump_roles = pump_roles
        self._pump_power_sensors: list[str] = []
        self._unsub_state_changes: list[object] = []

        self._attr_unique_id = f"{entry.entry_id}_total_pump_power"
        self._attr_device_info = grow_device_info(entry)

    def _resolve_power_entity_ids(self) -> list[str]:
        entity_ids: list[str] = []
        for pump_role in self._pump_roles:
            entity_id = _resolve_pump_power_id(self.hass, self._entry, pump_role)
            if entity_id:
                entity_ids.append(entity_id)
        return entity_ids

    @callback
    def _subscribe_power_entities(self, _now=None) -> None:
        for unsub in self._unsub_state_changes:
            if unsub:
                unsub()
        self._unsub_state_changes = []
        self._pump_power_sensors = self._resolve_power_entity_ids()
        for sensor_id in self._pump_power_sensors:
            unsub = async_track_state_change_event(
                self.hass,
                sensor_id,
                self._on_power_state_change,
            )
            self._unsub_state_changes.append(unsub)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to all pump power sensor state changes."""
        self._subscribe_power_entities()
        async_call_later(self.hass, 5, self._subscribe_power_entities)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from all state changes."""
        for unsub in self._unsub_state_changes:
            if unsub:
                unsub()

    @property
    def available(self) -> bool:
        """Return True if at least one pump power sensor is available."""
        for sensor_id in self._pump_power_sensors:
            state = self.hass.states.get(sensor_id)
            if state is not None and state.state not in ("unavailable", "unknown"):
                return True
        return False

    @property
    def native_value(self) -> float | None:
        """Return sum of all available pump power values."""
        total = 0.0
        has_value = False

        for sensor_id in self._pump_power_sensors:
            state = self.hass.states.get(sensor_id)
            if state is not None and state.state not in ("unavailable", "unknown"):
                try:
                    total += float(state.state)
                    has_value = True
                except (ValueError, TypeError):
                    continue

        return total if has_value else None

    @callback
    def _on_power_state_change(self, event):
        """Handle state change in any power entity."""
        self.async_write_ha_state()
