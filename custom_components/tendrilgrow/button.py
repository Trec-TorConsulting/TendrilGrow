"""Button entities for TendrilGrow."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import _async_run_ai_health_check
from .const import DOMAIN, FLUSH_NOW_SUFFIX
from .entity import grow_device_info
from .flush import async_record_flush


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up per-tent action buttons."""
    async_add_entities(
        [
            RunAIHealthCheckButton(hass, entry),
            FlushNowButton(hass, entry),
        ]
    )


class RunAIHealthCheckButton(ButtonEntity):
    """Manually trigger one AI health check for a grow space."""

    _attr_has_entity_name = True
    _attr_name = "Run AI Health Check"
    _attr_icon = "mdi:brain"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_run_ai_health_check"

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    async def async_press(self) -> None:
        await _async_run_ai_health_check(self.hass, self._entry, reason="manual_button")


class FlushNowButton(ButtonEntity):
    """Record that a full reservoir flush just happened for a grow space."""

    _attr_has_entity_name = True
    _attr_name = "Flush Now"
    _attr_icon = "mdi:water-sync"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{FLUSH_NOW_SUFFIX}"

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    async def async_press(self) -> None:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None:
            return
        await async_record_flush(self.hass, self._entry, runtime)
