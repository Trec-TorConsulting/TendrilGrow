"""Sensor platform for TendrilGrow."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .ai.health_checks import ai_dispatcher_signal
from .const import (
    DOMAIN,
    SENSOR_ROLE_CF,
    SENSOR_ROLE_EC,
    SENSOR_ROLE_HUMIDITY,
    SENSOR_ROLE_ORP,
    SENSOR_ROLE_PH,
    SENSOR_ROLE_TDS,
    SENSOR_ROLE_TEMPERATURE,
    SENSOR_ROLE_WATER_TEMPERATURE,
)
from .coordinator import (
    TendrilGrowTuyaCoordinator,
    has_tuya_credentials,
    tuya_device_ids,
    tuya_enabled,
)
from .entity import grow_device_info
from .models.grow import GrowSpace

LOGGER = logging.getLogger(__name__)

_METRIC_TO_ROLE: dict[str, str] = {
    "ph": SENSOR_ROLE_PH,
    "ec": SENSOR_ROLE_EC,
    "cf": SENSOR_ROLE_CF,
    "orp": SENSOR_ROLE_ORP,
    "tds": SENSOR_ROLE_TDS,
    "water_temp_c": SENSOR_ROLE_WATER_TEMPERATURE,
    "ambient_humidity": SENSOR_ROLE_HUMIDITY,
}


def _to_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


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
    entities: list[SensorEntity] = [
        AIHealthScoreSensor(hass, entry),
        AIHealthSummarySensor(hass, entry),
        AIFeedingScheduleSensor(hass, entry),
        AIHealthLastCheckSensor(hass, entry),
        TendrilGrowVpdSensor(hass, entry),
    ]

    if device_ids:
        coordinator = TendrilGrowTuyaCoordinator(hass, entry)
        await coordinator.async_refresh()

        for device_id in device_ids:
            for metric in METRICS:
                entities.append(TuyaMetricSensor(coordinator, entry, device_id, metric))
            entities.append(TuyaLastUpdatedSensor(coordinator, entry, device_id))
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
        name = self.coordinator.device_names.get(
            self._device_id, f"Tuya {self._device_id[-6:]}"
        )
        return {
            "identifiers": {
                ("tendrilgrow", f"{self._entry.entry_id}_{self._device_id}")
            },
            "name": f"{self._entry.title} {name}",
            "manufacturer": "Tuya",
            "model": "Water Monitor",
        }

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if not isinstance(self.coordinator.data, dict):
            return False
        metrics = self.coordinator.data.get(self._device_id)
        if not metrics:
            return False
        return self.entity_description.key in metrics

    @property
    def native_value(self):
        if not isinstance(self.coordinator.data, dict):
            return None
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
        auto_map_store = getattr(runtime, "auto_mapped_sensor_roles", None)
        if isinstance(auto_map_store, dict):
            auto_map_store[role] = self.entity_id

        LOGGER.info(
            "Auto-mapped TendrilGrow role %s -> %s for entry %s",
            role,
            self.entity_id,
            self._entry.entry_id,
        )


class TuyaLastUpdatedSensor(
    CoordinatorEntity[TendrilGrowTuyaCoordinator], SensorEntity
):
    """Timestamp sensor showing when a device was last refreshed successfully."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: TendrilGrowTuyaCoordinator,
        entry: ConfigEntry,
        device_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id

        suffix = device_id[-6:] if len(device_id) >= 6 else device_id
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_last_updated"
        self._attr_name = f"Last Updated ({suffix})"

    @property
    def device_info(self):
        name = self.coordinator.device_names.get(
            self._device_id, f"Tuya {self._device_id[-6:]}"
        )
        return {
            "identifiers": {
                ("tendrilgrow", f"{self._entry.entry_id}_{self._device_id}")
            },
            "name": f"{self._entry.title} {name}",
            "manufacturer": "Tuya",
            "model": "Water Monitor",
        }

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return self._device_id in self.coordinator.device_last_updated

    @property
    def native_value(self):
        return self.coordinator.device_last_updated.get(self._device_id)


_STATE_MAX_LENGTH = 255


def _compose_report(latest) -> str:
    """Build a human-readable markdown report from an AI health result."""
    score = latest.score if latest.score is not None else "n/a"
    confidence = (
        f", confidence {latest.confidence}%" if latest.confidence is not None else ""
    )
    lines: list[str] = [
        f"**Score {score}/100** — severity: {latest.severity}{confidence}"
    ]

    if getattr(latest, "confidence_rationale", ""):
        lines += ["", f"_{latest.confidence_rationale}_"]
    if latest.summary:
        lines += ["", latest.summary]
    if latest.observations:
        lines += [
            "",
            "**Observations**",
            *[f"- {item}" for item in latest.observations],
        ]
    if latest.issues:
        lines += ["", "**Issues**", *[f"- {item}" for item in latest.issues]]
    if latest.recommended_actions:
        lines += [
            "",
            "**Recommended actions**",
            *[f"- {item}" for item in latest.recommended_actions],
        ]

    return "\n".join(lines)


def _compose_feeding_schedule_md(latest) -> str:
    """Build a markdown feeding schedule from an AI health result."""
    schedule = getattr(latest, "feeding_schedule", None) or []
    if not schedule:
        return "_No feeding schedule generated yet. Run an AI health check._"
    return "\n".join(f"- {item}" for item in schedule)


class TendrilGrowVpdSensor(SensorEntity):
    """Derived canopy VPD (kPa) from mapped AIR temperature + AIR humidity."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = "VPD"
    _attr_native_unit_of_measurement = "kPa"
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:water-percent"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_vpd"
        self._attr_device_info = grow_device_info(entry)
        self._timer_unsubs: list = []
        self._state_unsubs: list = []

    def _grow_space(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        return getattr(runtime, "grow_space", None)

    def _air_entities(self) -> tuple[str | None, str | None]:
        grow_space = self._grow_space()
        if grow_space is None:
            return None, None
        return (
            grow_space.sensor_mappings.get(SENSOR_ROLE_TEMPERATURE),
            grow_space.sensor_mappings.get(SENSOR_ROLE_HUMIDITY),
        )

    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    @property
    def native_value(self):
        temp_id, hum_id = self._air_entities()
        if not temp_id or not hum_id:
            return None
        temp_state = self.hass.states.get(temp_id)
        hum_state = self.hass.states.get(hum_id)
        if temp_state is None or hum_state is None:
            return None
        temp = _to_float(temp_state.state)
        humidity = _to_float(hum_state.state)
        if temp is None or humidity is None:
            return None
        unit = temp_state.attributes.get("unit_of_measurement")
        vpd = GrowSpace.compute_vpd_kpa(temp, unit, humidity)
        return round(vpd, 2) if vpd is not None else None

    @property
    def extra_state_attributes(self):
        temp_id, hum_id = self._air_entities()
        return {
            "air_temperature_entity": temp_id,
            "air_humidity_entity": hum_id,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._resubscribe()
        # Re-resolve once after the Tuya auto-map backfill window.
        self._timer_unsubs.append(
            async_call_later(self.hass, 20, self._handle_delayed_resolve)
        )

    @callback
    def _handle_delayed_resolve(self, _now) -> None:
        self._resubscribe()

    @callback
    def _resubscribe(self) -> None:
        for unsub in self._state_unsubs:
            unsub()
        self._state_unsubs = []
        temp_id, hum_id = self._air_entities()
        tracked = [entity_id for entity_id in (temp_id, hum_id) if entity_id]
        if tracked:
            self._state_unsubs.append(
                async_track_state_change_event(
                    self.hass, tracked, self._handle_source_change
                )
            )
        self.async_write_ha_state()

    @callback
    def _handle_source_change(self, _event) -> None:
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        for unsub in (*self._timer_unsubs, *self._state_unsubs):
            unsub()
        self._timer_unsubs = []
        self._state_unsubs = []


class AIHealthBaseSensor(SensorEntity):
    """Base class for AI health entities driven by runtime state."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _unsub_dispatcher = None

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, suffix: str, name: str
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_name = name

    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    async def async_added_to_hass(self) -> None:
        """Subscribe to AI health state updates."""

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
    def extra_state_attributes(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None:
            return None
        latest = runtime.ai_health_state.latest
        if latest is None:
            attrs = {"running": runtime.ai_health_state.running}
            if runtime.ai_health_state.last_error:
                attrs["last_error"] = runtime.ai_health_state.last_error
            return attrs

        attrs = {
            "severity": latest.severity,
            "confidence": latest.confidence,
            "confidence_rationale": latest.confidence_rationale,
            "summary": latest.summary,
            "report": _compose_report(latest),
            "observations": latest.observations,
            "issues": latest.issues,
            "recommended_actions": latest.recommended_actions,
            "feeding_schedule": latest.feeding_schedule,
            "feeding_schedule_md": _compose_feeding_schedule_md(latest),
            "provider": latest.provider,
            "model": latest.model,
            "reason": latest.reason,
            "history_count": len(runtime.ai_health_state.history),
            "running": runtime.ai_health_state.running,
        }
        if runtime.ai_health_state.last_error:
            attrs["last_error"] = runtime.ai_health_state.last_error
        return attrs


class AIHealthScoreSensor(AIHealthBaseSensor):
    """Numeric AI health score for one grow space."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:heart-pulse"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "ai_health_score", "AI Health Score")

    @property
    def native_value(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None or runtime.ai_health_state.latest is None:
            return None
        return runtime.ai_health_state.latest.score


class AIHealthSummarySensor(AIHealthBaseSensor):
    """AI-generated summary string for one grow space."""

    _attr_icon = "mdi:text-box-search"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "ai_health_summary", "AI Health Summary")

    @property
    def native_value(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None or runtime.ai_health_state.latest is None:
            return None
        summary = runtime.ai_health_state.latest.summary or None
        if summary and len(summary) > _STATE_MAX_LENGTH:
            return summary[: _STATE_MAX_LENGTH - 3].rstrip() + "..."
        return summary


class AIFeedingScheduleSensor(AIHealthBaseSensor):
    """AI-generated dynamic feeding schedule for one grow space."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "ai_feeding_schedule", "AI Feeding Schedule")

    @property
    def native_value(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None or runtime.ai_health_state.latest is None:
            return None
        steps = runtime.ai_health_state.latest.feeding_schedule
        if not steps:
            return "No schedule yet"
        return f"{len(steps)} step plan"


class AIHealthLastCheckSensor(AIHealthBaseSensor):
    """Timestamp of the latest AI health check."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "ai_health_last_check", "AI Last Health Check")

    @property
    def native_value(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None or runtime.ai_health_state.latest is None:
            return None
        return runtime.ai_health_state.latest.checked_at
