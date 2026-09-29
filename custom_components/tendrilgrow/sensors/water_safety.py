"""Water safety status sensor entity for TendrilGrow."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from ..const import DOMAIN, WATER_SAFETY_STATUS_OK, WATER_SAFETY_STATUSES
from ..entity import grow_device_info
from ..water_safety import WaterSafetyMonitor, water_safety_dispatcher_signal


class TendrilGrowWaterSafetyStatusSensor(SensorEntity):
    """Sensor reporting the water safety status (ok / no_flow / leak)."""

    _attr_has_entity_name = True
    _attr_name = "Water Safety Status"
    _attr_icon = "mdi:shield-water"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(WATER_SAFETY_STATUSES)
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_water_safety_status"
        self._attr_device_info = grow_device_info(entry)

    @property
    def _monitor(self) -> WaterSafetyMonitor | None:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is not None:
            return getattr(runtime, "water_safety_monitor", None)
        return None

    @property
    def native_value(self) -> str:
        mon = self._monitor
        if mon is not None:
            return mon.status
        return WATER_SAFETY_STATUS_OK

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        mon = self._monitor
        if mon is None:
            return {}
        return {
            "active_leaks": mon.active_leaks,
            "flow_ok": mon.flow_ok,
            "flow_rate": mon.flow_rate,
            "last_transition": mon.last_transition,
            "shutoff_triggered": mon.shutoff_triggered,
            "leak_shutoff_enabled": mon._leak_shutoff_enabled,
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                water_safety_dispatcher_signal(self._entry.entry_id),
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
