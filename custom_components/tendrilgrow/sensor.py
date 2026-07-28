"""Sensor platform for TendrilGrow."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import TendrilGrowTuyaCoordinator, has_tuya_credentials, tuya_device_ids, tuya_enabled
from .const import (
    DOMAIN,
    SENSOR_ROLE_CF,
    SENSOR_ROLE_EC,
    SENSOR_ROLE_HUMIDITY,
    SENSOR_ROLE_ORP,
    SENSOR_ROLE_PH,
    SENSOR_ROLE_TDS,
    SENSOR_ROLE_TEMPERATURE,
)

LOGGER = logging.getLogger(__name__)

_METRIC_TO_ROLE: dict[str, str] = {
    "ph": SENSOR_ROLE_PH,
    "ec": SENSOR_ROLE_EC,
    "cf": SENSOR_ROLE_CF,
    "orp": SENSOR_ROLE_ORP,
    "tds": SENSOR_ROLE_TDS,
    "water_temp_c": SENSOR_ROLE_TEMPERATURE,
    "ambient_humidity": SENSOR_ROLE_HUMIDITY,
}


@dataclass(slots=True, frozen=True)
class TendrilGrowMetricDescription(SensorEntityDescription):
    """Describes one normalized Tuya metric."""


METRICS: tuple[TendrilGrowMetricDescription, ...] = (
    TendrilGrowMetricDescription(key="ph", name="pH", suggested_display_precision=2),
    TendrilGrowMetricDescription(
        key="ec",
        name="EC",
        native_unit_of_measurement="mS/cm",
        suggested_display_precision=3,
    ),
    TendrilGrowMetricDescription(
        key="cf",
        name="CF",
        native_unit_of_measurement="mS/cm",
        suggested_display_precision=3,
    ),
    TendrilGrowMetricDescription(
        key="tds",
        name="TDS",
        native_unit_of_measurement="ppm",
        suggested_display_precision=1,
    ),
    TendrilGrowMetricDescription(
        key="orp",
        name="ORP",
        native_unit_of_measurement="mV",
        suggested_display_precision=0,
    ),
    TendrilGrowMetricDescription(
        key="water_temp_c",
        name="Water Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
    ),
    TendrilGrowMetricDescription(
        key="ambient_humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        suggested_display_precision=0,
    ),
    TendrilGrowMetricDescription(
        key="battery_pct",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TendrilGrow sensors for one config entry."""
    if not tuya_enabled(entry) or not has_tuya_credentials(entry):
        return

    device_ids = tuya_device_ids(entry)
    if not device_ids:
        return

    coordinator = TendrilGrowTuyaCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entities: list[TuyaMetricSensor] = []
    for device_id in device_ids:
        for metric in METRICS:
            entities.append(TuyaMetricSensor(coordinator, entry, device_id, metric))
    async_add_entities(entities)


class TuyaMetricSensor(CoordinatorEntity[TendrilGrowTuyaCoordinator], SensorEntity):
    """Sensor backed by normalized Tuya cloud metric data."""

    entity_description: TendrilGrowMetricDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TendrilGrowTuyaCoordinator,
        entry: ConfigEntry,
        device_id: str,
        description: TendrilGrowMetricDescription,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self.entity_description = description

        suffix = device_id[-6:] if len(device_id) >= 6 else device_id
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_{description.key}"
        self._attr_name = f"{description.name} ({suffix})"

    @property
    def device_info(self):
        name = self.coordinator.device_names.get(self._device_id, f"Tuya {self._device_id[-6:]}")
        return {
            "identifiers": {("tendrilgrow", f"{self._entry.entry_id}_{self._device_id}")},
            "name": f"{self._entry.title} {name}",
            "manufacturer": "Tuya",
            "model": "Water Monitor",
        }

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        metrics = self.coordinator.data.get(self._device_id)
        if not metrics:
            return False
        return self.entity_description.key in metrics

    @property
    def native_value(self):
        metrics = self.coordinator.data.get(self._device_id, {})
        return metrics.get(self.entity_description.key)

    async def async_added_to_hass(self) -> None:
        """Backfill grow role mappings from Tuya entities when missing."""
        await super().async_added_to_hass()
        if not self.entity_id:
            return

        role = _METRIC_TO_ROLE.get(self.entity_description.key)
        if not role:
            return

        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        grow_space = getattr(runtime, "grow_space", None)
        if grow_space is None:
            return

        if grow_space.sensor_mappings.get(role):
            return

        grow_space.sensor_mappings[role] = self.entity_id
        LOGGER.debug(
            "Auto-mapped TendrilGrow role %s to entity %s for entry %s",
            role,
            self.entity_id,
            self._entry.entry_id,
        )