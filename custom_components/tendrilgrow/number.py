"""Number entities for TendrilGrow cultivation context."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberMode,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CTX_FEED_INTERVAL_DAYS,
    CTX_FLUSH_INTERVAL_DAYS,
    CTX_LIGHTS_ON_HOURS,
    CTX_PRICE_PER_KWH,
    CTX_RESERVOIR_VOLUME,
    CTX_RUNOFF_TARGET_PCT,
    CTX_SITE_COUNT,
    CTX_TARGET_EC,
    CTX_TARGET_PH,
    DEFAULT_FLUSH_INTERVAL_DAYS,
    DOMAIN,
)
from .entity import grow_device_info
from .flush import async_save_flush_state, flush_dispatcher_signal


@dataclass(frozen=True, slots=True)
class GrowNumberDescription:
    """Describes one editable cultivation number."""

    key: str
    name: str
    minimum: float
    maximum: float
    step: float
    unit: str | None
    default: float
    icon: str


NUMBERS: tuple[GrowNumberDescription, ...] = (
    GrowNumberDescription(
        CTX_SITE_COUNT,
        "Sites / Plants",
        0.0,
        64.0,
        1.0,
        "sites",
        4.0,
        "mdi:sprout-outline",
    ),
    GrowNumberDescription(
        CTX_RESERVOIR_VOLUME,
        "Total System Volume",
        0.0,
        500.0,
        0.5,
        "gal",
        13.0,
        "mdi:cup-water",
    ),
    GrowNumberDescription(
        CTX_TARGET_PH, "Target pH", 4.0, 8.0, 0.1, "pH", 5.9, "mdi:ph"
    ),
    GrowNumberDescription(
        CTX_TARGET_EC, "Target EC", 0.0, 5.0, 0.1, "mS/cm", 1.6, "mdi:flash"
    ),
    GrowNumberDescription(
        CTX_FEED_INTERVAL_DAYS,
        "Feed Interval",
        0.0,
        14.0,
        1.0,
        "d",
        1.0,
        "mdi:calendar-clock",
    ),
    GrowNumberDescription(
        CTX_LIGHTS_ON_HOURS,
        "Lights On",
        0.0,
        24.0,
        0.5,
        "h",
        18.0,
        "mdi:lightbulb-on-outline",
    ),
    GrowNumberDescription(
        CTX_RUNOFF_TARGET_PCT,
        "Runoff Target",
        0.0,
        50.0,
        1.0,
        "%",
        15.0,
        "mdi:water-percent",
    ),
    GrowNumberDescription(
        CTX_PRICE_PER_KWH,
        "Electricity Price",
        0.0,
        2.0,
        0.01,
        "/kWh",
        0.15,
        "mdi:cash",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up cultivation number entities."""
    entities: list[NumberEntity] = [
        GrowContextNumber(entry, description) for description in NUMBERS
    ]
    entities.append(FlushIntervalNumber(hass, entry))
    async_add_entities(entities)


class GrowContextNumber(RestoreNumber):
    """Editable, persisted cultivation number for one grow space."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_mode = NumberMode.BOX

    def __init__(self, entry: ConfigEntry, description: GrowNumberDescription) -> None:
        self._entry = entry
        self._description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = description.name
        self._attr_native_min_value = description.minimum
        self._attr_native_max_value = description.maximum
        self._attr_native_step = description.step
        self._attr_native_unit_of_measurement = description.unit
        self._attr_icon = description.icon
        self._attr_native_value = description.default

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._attr_native_value = last.native_value

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()


class FlushIntervalNumber(NumberEntity):
    """Editable full-flush cadence (days) backed by the entry's flush state."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_mode = NumberMode.BOX
    _attr_name = "Flush Interval"
    _attr_icon = "mdi:calendar-refresh"
    _attr_native_min_value = 1
    _attr_native_max_value = 21
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "d"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{CTX_FLUSH_INTERVAL_DAYS}"

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    @property
    def native_value(self) -> float | None:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None:
            return float(DEFAULT_FLUSH_INTERVAL_DAYS)
        return float(runtime.flush_state.interval_days)

    async def async_set_native_value(self, value: float) -> None:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None:
            return
        interval = max(1, min(21, int(value)))
        runtime.flush_state.interval_days = interval
        await async_save_flush_state(runtime.flush_store, runtime.flush_state)
        async_dispatcher_send(self.hass, flush_dispatcher_signal(self._entry.entry_id))
        self.async_write_ha_state()
