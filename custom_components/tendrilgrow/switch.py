"""Switch platform for TendrilGrow pump controls."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    PUMP_CONTROL_ROLES,
    PUMP_LABELS,
)
from .entity import grow_device_info

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TendrilGrow pump proxy switches for one config entry."""
    data = entry.data
    control_mappings = data.get("control_mappings", {})

    entities: list[SwitchEntity] = []

    # Create one proxy switch per mapped pump role.
    for pump_role in PUMP_CONTROL_ROLES:
        if pump_role in control_mappings:
            entity_id = control_mappings[pump_role]
            entities.append(
                TendrilGrowPumpSwitch(hass, entry, pump_role, entity_id)
            )

    if entities:
        async_add_entities(entities)


class TendrilGrowPumpSwitch(SwitchEntity):
    """Proxy switch for a mapped pump control entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        pump_role: str,
        mapped_entity_id: str,
    ) -> None:
        """Initialize pump proxy switch."""
        self.hass = hass
        self._entry = entry
        self._pump_role = pump_role
        self._mapped_entity_id = mapped_entity_id
        self._unsub_state_change: Any = None

        # Use pump label for display name.
        pump_label = PUMP_LABELS.get(pump_role, pump_role)
        self._attr_unique_id = f"{entry.entry_id}_{pump_role}"
        self._attr_name = pump_label
        self._attr_device_info = grow_device_info(entry)

    async def async_added_to_hass(self) -> None:
        """Subscribe to mapped entity state changes."""
        self._unsub_state_change = async_track_state_change_event(
            self.hass,
            self._mapped_entity_id,
            self._on_state_change,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from state changes."""
        if self._unsub_state_change:
            self._unsub_state_change()

    @property
    def is_on(self) -> bool:
        """Return True if mapped entity is on."""
        state = self.hass.states.get(self._mapped_entity_id)
        if state is None or state.state == STATE_UNKNOWN:
            return False
        return state.state == STATE_ON

    @property
    def available(self) -> bool:
        """Return True if mapped entity is available."""
        state = self.hass.states.get(self._mapped_entity_id)
        return state is not None and state.state not in (
            STATE_UNKNOWN,
            "unavailable",
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the mapped entity."""
        await self._call_service("turn_on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the mapped entity."""
        await self._call_service("turn_off")

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the mapped entity."""
        await self._call_service("toggle")

    async def _call_service(self, action: str) -> None:
        """Route service call to appropriate domain."""
        domain = self._mapped_entity_id.split(".")[0]

        # Map domain-specific service names.
        service_map = {
            "switch": f"switch/{action}",
            "input_boolean": f"input_boolean/{action}",
        }

        service = service_map.get(domain, f"homeassistant/{action}")

        try:
            await self.hass.services.async_call(
                *service.split("/"),
                {"entity_id": self._mapped_entity_id},
            )
        except Exception as err:
            LOGGER.error(
                "Failed to %s pump %s (entity %s): %s",
                action,
                self._pump_role,
                self._mapped_entity_id,
                err,
            )
            raise HomeAssistantError(
                f"Failed to {action} pump entity {self._mapped_entity_id}"
            ) from err

    @callback
    def _on_state_change(self, event):
        """Handle state change in mapped entity."""
        self.async_write_ha_state()
