"""Time entities for TendrilGrow light schedule."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CTX_LIGHTS_OFF_TIME, CTX_LIGHTS_ON_TIME
from .entity import grow_device_info
from .grow_targets import sync_lights_on_hours_from_schedule


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up light schedule time entities."""
    async_add_entities(
        [
            GrowLightsOnTime(hass, entry),
            GrowLightsOffTime(hass, entry),
        ]
    )


class _GrowScheduleTime(TimeEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        *,
        suffix: str,
        name: str,
        default: time,
        icon: str,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_value = default

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    def _parse_time(self, raw: str) -> time | None:
        try:
            parts = [int(p) for p in str(raw).split(":")]
            return time(parts[0], parts[1], parts[2] if len(parts) > 2 else 0)
        except (ValueError, IndexError):
            return None

    async def async_set_value(self, value: time) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
        sync_lights_on_hours_from_schedule(self.hass, self._entry)


class GrowLightsOnTime(_GrowScheduleTime):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            entry,
            suffix=CTX_LIGHTS_ON_TIME,
            name="Lights On Time",
            default=time(6, 0),
            icon="mdi:weather-sunset-up",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (
            None,
            "",
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            parsed = self._parse_time(last.state)
            if parsed is not None:
                self._attr_native_value = parsed
        sync_lights_on_hours_from_schedule(self.hass, self._entry)


class GrowLightsOffTime(_GrowScheduleTime):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            entry,
            suffix=CTX_LIGHTS_OFF_TIME,
            name="Lights Off Time",
            default=time(0, 0),
            icon="mdi:weather-sunset-down",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (
            None,
            "",
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            parsed = self._parse_time(last.state)
            if parsed is not None:
                self._attr_native_value = parsed
        sync_lights_on_hours_from_schedule(self.hass, self._entry)
