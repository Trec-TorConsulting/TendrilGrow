"""Text entities for TendrilGrow cultivation context."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CTX_ADDITIVES, CTX_BASE_NUTRIENTS, CTX_NUTRIENT_LINE, CTX_STRAIN
from .entity import grow_device_info

_UNAVAILABLE_STATES = frozenset({"", "unknown", "unavailable"})


@dataclass(frozen=True, slots=True)
class GrowTextDescription:
    """Describes one editable cultivation text field."""

    key: str
    name: str
    icon: str


TEXTS: tuple[GrowTextDescription, ...] = (
    GrowTextDescription(CTX_STRAIN, "Strain / Genetics", "mdi:cannabis"),
    GrowTextDescription(CTX_NUTRIENT_LINE, "Nutrient Line", "mdi:bottle-tonic"),
    GrowTextDescription(CTX_BASE_NUTRIENTS, "Base Nutrients", "mdi:beaker-outline"),
    GrowTextDescription(CTX_ADDITIVES, "Additives", "mdi:flask-outline"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up cultivation text entities."""
    async_add_entities([GrowContextText(entry, description) for description in TEXTS])


class GrowContextText(TextEntity, RestoreEntity):
    """Editable, persisted cultivation text for one grow space."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_native_max = 255

    def __init__(self, entry: ConfigEntry, description: GrowTextDescription) -> None:
        self._entry = entry
        self._description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_native_value = ""

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in _UNAVAILABLE_STATES:
            self._attr_native_value = last.state

    async def async_set_value(self, value: str) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
