"""Binary sensor entities for TendrilGrow."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ai.health_checks import ai_dispatcher_signal, has_critical_alert
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TendrilGrow binary sensors."""
    async_add_entities([AIHealthAlertBinarySensor(hass, entry)])


class AIHealthAlertBinarySensor(BinarySensorEntity):
    """Turns on when AI health score enters the configured critical range."""

    _attr_has_entity_name = True
    _attr_name = "AI Health Critical Alert"
    _attr_icon = "mdi:alert"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_ai_health_critical_alert"
        self._unsub_dispatcher = None

    async def async_added_to_hass(self) -> None:
        @callback
        def _async_handle_update() -> None:
            self.async_write_ha_state()

        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            ai_dispatcher_signal(self._entry.entry_id),
            _async_handle_update,
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_dispatcher is not None:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None

    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    @property
    def is_on(self) -> bool:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None:
            return False
        return has_critical_alert(self._entry, runtime.ai_health_state)

    @property
    def extra_state_attributes(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None:
            return None
        latest = runtime.ai_health_state.latest
        if latest is None:
            return {"running": runtime.ai_health_state.running}
        return {
            "score": latest.score,
            "severity": latest.severity,
            "summary": latest.summary,
            "checked_at": latest.checked_at.isoformat(),
            "running": runtime.ai_health_state.running,
        }
