"""Select entities for TendrilGrow cultivation context."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CTX_STAGE, STAGE_OPTIONS
from .entity import grow_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up cultivation select entities."""
    async_add_entities([GrowStageSelect(entry)])


class GrowStageSelect(SelectEntity, RestoreEntity):
    """Editable, persisted growth stage for one grow space."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Growth Stage"
    _attr_icon = "mdi:sprout"
    _attr_options = list(STAGE_OPTIONS)

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{CTX_STAGE}"
        self._attr_current_option = STAGE_OPTIONS[1]

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in self._attr_options:
            self._attr_current_option = last.state

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()
