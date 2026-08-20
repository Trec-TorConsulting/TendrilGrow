"""Sensor platform for TendrilGrow."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get as get_entity_registry
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .ai.health_checks import ai_dispatcher_signal
from .const import (
    CONF_TIMELAPSE_DIR,
    CTX_LIGHTS_ON_HOURS,
    CTX_PRICE_PER_KWH,
    CTX_STAGE,
    CTX_WEEK_IN_STAGE,
    DOMAIN,
    FLUSH_DAYS_SINCE_SUFFIX,
    FLUSH_DAYS_UNTIL_SUFFIX,
    FLUSH_LAST_SUFFIX,
    FLUSH_NEXT_DUE_SUFFIX,
    PUMP_CONTROL_ROLES,
    PUMP_LABELS,
    PUMP_POWER_ROLE_FOR,
    SENSOR_ROLE_CF,
    SENSOR_ROLE_EC,
    SENSOR_ROLE_HUMIDITY,
    SENSOR_ROLE_LIGHT,
    SENSOR_ROLE_ORP,
    SENSOR_ROLE_PH,
    SENSOR_ROLE_TDS,
    SENSOR_ROLE_TEMPERATURE,
    SENSOR_ROLE_WATER_TEMPERATURE,
    STAGE_DURATIONS_DAYS,
    STAGE_PIPELINE,
    WATER_SOURCE_CLOUD,
)
from .coordinator import TendrilGrowTuyaCoordinator, tuya_device_ids
from .entity import grow_device_info
from .flush import flush_dispatcher_signal, flush_status
from .insights import (
    compose_weekly_journal,
    compute_daily_energy_kwh,
    compute_dew_point_c,
    compute_dli,
    estimate_daily_cost,
)
from .local_water_source import effective_water_source
from .models.grow import GrowSpace
from .timelapse import (
    list_frame_files,
    parse_frame_timestamp,
    resolve_timelapse_paths,
    timelapse_dispatcher_signal,
)

LOGGER = logging.getLogger(__name__)

# Cloud Tuya metrics that auto-map onto water roles. Probe ambient humidity must
# NOT bind to the canopy humidity role used for VPD.
_METRIC_TO_ROLE: dict[str, str] = {
    "ph": SENSOR_ROLE_PH,
    "ec": SENSOR_ROLE_EC,
    "cf": SENSOR_ROLE_CF,
    "orp": SENSOR_ROLE_ORP,
    "tds": SENSOR_ROLE_TDS,
    "water_temp_c": SENSOR_ROLE_WATER_TEMPERATURE,
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
    entities: list[SensorEntity] = []

    # VPD and AI health sensors are independent of Tuya cloud polling.
    entities.extend(
        [
            AIHealthScoreSensor(hass, entry),
            AIHealthSummarySensor(hass, entry),
            AIFeedingScheduleSensor(hass, entry),
            AIHealthLastCheckSensor(hass, entry),
            AIWeeklyJournalSensor(hass, entry),
            TendrilGrowVpdSensor(hass, entry),
        ]
    )

    # Cloud Tuya metric sensors only when cloud is the effective water source.
    if effective_water_source(hass, entry) == WATER_SOURCE_CLOUD:
        device_ids = tuya_device_ids(entry)
        if device_ids:
            coordinator = TendrilGrowTuyaCoordinator(hass, entry)
            await coordinator.async_refresh()

            for device_id in device_ids:
                for metric in METRICS:
                    entities.append(
                        TuyaMetricSensor(coordinator, entry, device_id, metric)
                    )
                entities.append(TuyaLastUpdatedSensor(coordinator, entry, device_id))

    # Pump power sensors (independent of Tuya configuration).
    data = entry.data
    control_mappings = data.get("control_mappings", {})
    pump_power_sensors: list[str] = []

    for pump_role in PUMP_CONTROL_ROLES:
        if pump_role in control_mappings:
            power_source = await _resolve_pump_power_source(hass, entry, pump_role)
            entities.append(
                TendrilGrowPumpPowerSensor(hass, entry, pump_role, power_source)
            )
            # Track pump power sensor IDs for total power calculation.
            if power_source:
                pump_power_sensor_id = f"sensor.{entry.entry_id}_{pump_role}_power"
                pump_power_sensors.append(pump_power_sensor_id)

    # Add total pump power sensor if any pump powers are mapped.
    if pump_power_sensors:
        entities.append(
            TendrilGrowTotalPumpPowerSensor(hass, entry, pump_power_sensors)
        )

    # Reservoir full-flush tracking sensors (independent of Tuya).
    entities.extend(
        [
            FlushLastSensor(hass, entry),
            FlushDaysSinceSensor(hass, entry),
            FlushDaysUntilSensor(hass, entry),
            FlushNextDueSensor(hass, entry),
        ]
    )

    # Lifecycle stage projection (independent of Tuya).
    entities.append(TendrilGrowStageProjectionSensor(hass, entry))

    # Derived climate/light/energy insights (independent of Tuya).
    entities.extend(
        [
            TendrilGrowDewPointSensor(hass, entry),
            TendrilGrowDliSensor(hass, entry),
            TendrilGrowEnergyCostSensor(hass, entry),
            TendrilGrowTimelapseFramesSensor(hass, entry),
            TendrilGrowTimelapseLastFrameSensor(hass, entry),
        ]
    )

    if entities:
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
    parts: list[str] = []
    for i, item in enumerate(schedule, 1):
        # Promote the phase label (text before first '|') as a bold header.
        if "|" in item:
            header, _, rest = item.partition("|")
            header = header.strip()
            body = rest.strip()
            entry = f"**{i}. {header}**\n{body}"
        else:
            entry = f"**{i}.** {item}"
        parts.append(entry)
    return "\n\n---\n\n".join(parts)


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


class _DerivedGrowSensor(SensorEntity):
    """Base for sensors derived from other mapped or context entities."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, suffix: str, name: str
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_device_info = grow_device_info(entry)
        self._attr_name = name
        self._state_unsubs: list = []
        self._timer_unsubs: list = []

    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    def _grow_space(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        return getattr(runtime, "grow_space", None)

    def _number_entity(self, suffix: str) -> str | None:
        registry = get_entity_registry(self.hass)
        return registry.async_get_entity_id(
            "number", DOMAIN, f"{self._entry.entry_id}_{suffix}"
        )

    def _read_float(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        return _to_float(state.state) if state else None

    def _source_entity_ids(self) -> list[str]:
        return []

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
        tracked = self._source_entity_ids()
        if tracked:
            self._state_unsubs.append(
                async_track_state_change_event(self.hass, tracked, self._on_change)
            )
        self.async_write_ha_state()

    @callback
    def _on_change(self, _event) -> None:
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        for unsub in (*self._timer_unsubs, *self._state_unsubs):
            unsub()
        self._timer_unsubs = []
        self._state_unsubs = []


class TendrilGrowDewPointSensor(_DerivedGrowSensor):
    """Dew point derived from mapped AIR temperature and humidity."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:thermometer-water"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "dew_point", "Dew Point")

    def _air_ids(self) -> tuple[str | None, str | None]:
        grow_space = self._grow_space()
        if grow_space is None:
            return None, None
        return (
            grow_space.sensor_mappings.get(SENSOR_ROLE_TEMPERATURE),
            grow_space.sensor_mappings.get(SENSOR_ROLE_HUMIDITY),
        )

    def _source_entity_ids(self) -> list[str]:
        return [eid for eid in self._air_ids() if eid]

    @property
    def native_value(self):
        temp_id, hum_id = self._air_ids()
        temp_state = self.hass.states.get(temp_id) if temp_id else None
        hum_state = self.hass.states.get(hum_id) if hum_id else None
        if temp_state is None or hum_state is None:
            return None
        temp_c = GrowSpace.to_celsius(
            _to_float(temp_state.state),
            temp_state.attributes.get("unit_of_measurement"),
        )
        dew = compute_dew_point_c(temp_c, _to_float(hum_state.state))
        return round(dew, 1) if dew is not None else None


class TendrilGrowDliSensor(_DerivedGrowSensor):
    """Estimated Daily Light Integral from mapped PPFD and photoperiod."""

    _attr_native_unit_of_measurement = "mol/m\u00b2/d"
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:white-balance-sunny"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "dli", "DLI")

    def _ppfd_id(self) -> str | None:
        grow_space = self._grow_space()
        if grow_space is None:
            return None
        return grow_space.sensor_mappings.get(SENSOR_ROLE_LIGHT)

    def _source_entity_ids(self) -> list[str]:
        ids = [self._ppfd_id(), self._number_entity(CTX_LIGHTS_ON_HOURS)]
        return [eid for eid in ids if eid]

    @property
    def native_value(self):
        ppfd = self._read_float(self._ppfd_id())
        hours = self._read_float(self._number_entity(CTX_LIGHTS_ON_HOURS))
        dli = compute_dli(ppfd, hours)
        return round(dli, 1) if dli is not None else None

    @property
    def extra_state_attributes(self):
        return {
            "estimated": True,
            "photoperiod_hours": self._read_float(
                self._number_entity(CTX_LIGHTS_ON_HOURS)
            ),
        }


class TendrilGrowEnergyCostSensor(_DerivedGrowSensor):
    """Estimated daily pump electricity cost (total pump power x 24h x price)."""

    _attr_icon = "mdi:cash-clock"
    _attr_suggested_display_precision = 2

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "pump_daily_cost", "Pump Daily Cost (est.)")
        self._attr_native_unit_of_measurement = getattr(
            getattr(hass, "config", None), "currency", None
        )

    def _power_id(self) -> str | None:
        registry = get_entity_registry(self.hass)
        return registry.async_get_entity_id(
            "sensor", DOMAIN, f"{self._entry.entry_id}_total_pump_power"
        )

    def _source_entity_ids(self) -> list[str]:
        ids = [self._power_id(), self._number_entity(CTX_PRICE_PER_KWH)]
        return [eid for eid in ids if eid]

    def _energy_kwh(self) -> float | None:
        return compute_daily_energy_kwh(self._read_float(self._power_id()))

    @property
    def native_value(self):
        cost = estimate_daily_cost(
            self._energy_kwh(),
            self._read_float(self._number_entity(CTX_PRICE_PER_KWH)),
        )
        return round(cost, 2) if cost is not None else None

    @property
    def extra_state_attributes(self):
        energy = self._energy_kwh()
        return {
            "estimated": True,
            "energy_kwh_per_day": round(energy, 3) if energy is not None else None,
            "assumes_hours_per_day": 24,
        }


class TimelapseBaseSensor(SensorEntity):
    """Base class for timelapse status sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, suffix: str, name: str):
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_name = name
        self._attr_device_info = grow_device_info(entry)
        self._unsub_dispatcher = None
        self._unsub_timer = None

    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    def _merged_config(self) -> dict[str, object]:
        merged = dict(self._entry.data)
        merged.update(getattr(self._entry, "options", {}))
        return merged

    def _paths(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        grow_space = getattr(runtime, "grow_space", None)
        grow_space_name = getattr(grow_space, "name", self._entry.title)
        return resolve_timelapse_paths(
            self.hass.config.config_dir,
            grow_space_name,
            str(self._merged_config().get(CONF_TIMELAPSE_DIR, "")),
        )

    def _frames(self) -> list:
        paths = self._paths()
        if not paths.directory.exists():
            return []
        return list_frame_files(paths.directory)

    async def async_added_to_hass(self) -> None:
        @callback
        def _handle(*_args) -> None:
            self.async_write_ha_state()

        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            timelapse_dispatcher_signal(self._entry.entry_id),
            _handle,
        )
        self._unsub_timer = async_track_time_interval(
            self.hass,
            _handle,
            timedelta(minutes=30),
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_dispatcher is not None:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None


class TendrilGrowTimelapseFramesSensor(TimelapseBaseSensor):
    """Frame-count sensor for per-space timelapse captures."""

    _attr_icon = "mdi:image-multiple"
    _attr_translation_key = "timelapse_frames"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "timelapse_frames", "Timelapse Frames")

    @property
    def native_value(self):
        return len(self._frames())

    @property
    def extra_state_attributes(self):
        paths = self._paths()
        frames = self._frames()
        latest = frames[-1] if frames else None
        latest_url = None
        if latest is not None and paths.local_url_base is not None:
            latest_url = f"{paths.local_url_base}/{latest.name}"
        return {
            "capture_directory": str(paths.directory),
            "capture_local_url": paths.local_url_base,
            "latest_frame_path": str(latest) if latest is not None else None,
            "latest_frame_url": latest_url,
        }


class TendrilGrowTimelapseLastFrameSensor(TimelapseBaseSensor):
    """Timestamp of the newest captured timelapse frame."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clock-image"
    _attr_translation_key = "timelapse_last_frame"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            entry,
            "timelapse_last_frame",
            "Timelapse Last Frame",
        )

    @property
    def native_value(self):
        frames = self._frames()
        if not frames:
            return None
        latest = frames[-1]
        parsed = parse_frame_timestamp(latest)
        if parsed is not None:
            return parsed
        modified = latest.stat().st_mtime
        return datetime.fromtimestamp(modified, tz=dt_util.UTC)


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

    @property
    def device_info(self):
        return grow_device_info(self._entry)

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


class AIWeeklyJournalSensor(AIHealthBaseSensor):
    """A weekly recap composed from the recorded AI health checks."""

    _attr_icon = "mdi:notebook-outline"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "ai_weekly_journal", "AI Weekly Journal")

    def _journal(self) -> dict[str, str]:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        state = getattr(runtime, "ai_health_state", None)
        history = getattr(state, "history", None) or []
        return compose_weekly_journal(history, dt_util.now())

    @property
    def native_value(self):
        return self._journal()["headline"][:255]

    @property
    def extra_state_attributes(self):
        return {"journal_markdown": self._journal()["markdown"]}


async def _resolve_pump_power_source(
    hass: HomeAssistant,
    entry: ConfigEntry,
    pump_role: str,
) -> str | None:
    """Resolve power source for a pump: explicit mapping or auto-discovery.

    Returns entity_id of power sensor or None if not found.
    """
    data = entry.data
    sensor_mappings = data.get("sensor_mappings", {})
    control_mappings = data.get("control_mappings", {})

    # Check explicit power mapping first.
    power_role = PUMP_POWER_ROLE_FOR.get(pump_role)
    if power_role and power_role in sensor_mappings:
        return sensor_mappings[power_role]

    # Try auto-discovery from the pump switch's device.
    if pump_role not in control_mappings:
        return None

    pump_entity_id = control_mappings[pump_role]
    entity_registry = get_entity_registry(hass)
    pump_entity = entity_registry.async_get(pump_entity_id)

    if pump_entity is None or pump_entity.device_id is None:
        return None

    # Find power sensors on the same device.
    for entity in entity_registry.entities.values():
        if (
            entity.device_id == pump_entity.device_id
            and entity.domain == "sensor"
            and entity.device_class == SensorDeviceClass.POWER
        ):
            return entity.entity_id

    return None


class TendrilGrowPumpPowerSensor(SensorEntity):
    """Power sensor for a pump control entity."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        pump_role: str,
        power_entity_id: str | None,
    ) -> None:
        """Initialize pump power sensor."""
        self.hass = hass
        self._entry = entry
        self._pump_role = pump_role
        self._power_entity_id = power_entity_id
        self._unsub_state_change: object = None

        # Use pump label for display name.
        pump_label = PUMP_LABELS.get(pump_role, pump_role)
        self._attr_unique_id = f"{entry.entry_id}_{pump_role}_power"
        self._attr_name = f"{pump_label} Power"
        self._attr_device_info = grow_device_info(entry)

    async def async_added_to_hass(self) -> None:
        """Subscribe to power entity state changes."""
        if self._power_entity_id:
            self._unsub_state_change = async_track_state_change_event(
                self.hass,
                self._power_entity_id,
                self._on_power_state_change,
            )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from state changes."""
        if self._unsub_state_change:
            self._unsub_state_change()

    @property
    def available(self) -> bool:
        """Return availability based on power source state."""
        if not self._power_entity_id:
            return False
        state = self.hass.states.get(self._power_entity_id)
        return state is not None and state.state not in (
            "unavailable",
            "unknown",
        )

    @property
    def native_value(self) -> float | None:
        """Return power value from source entity."""
        if not self._power_entity_id:
            return None
        state = self.hass.states.get(self._power_entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    @callback
    def _on_power_state_change(self, event):
        """Handle state change in power entity."""
        self.async_write_ha_state()


class TendrilGrowTotalPumpPowerSensor(SensorEntity):
    """Total power sensor summing all mapped pump powers."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False
    _attr_name = "Total Pump Power"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        pump_power_sensors: list[str],
    ) -> None:
        """Initialize total pump power sensor."""
        self.hass = hass
        self._entry = entry
        self._pump_power_sensors = pump_power_sensors
        self._unsub_state_changes: list[object] = []

        self._attr_unique_id = f"{entry.entry_id}_total_pump_power"
        self._attr_device_info = grow_device_info(entry)

    async def async_added_to_hass(self) -> None:
        """Subscribe to all pump power sensor state changes."""
        for sensor_id in self._pump_power_sensors:
            unsub = async_track_state_change_event(
                self.hass,
                sensor_id,
                self._on_power_state_change,
            )
            self._unsub_state_changes.append(unsub)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from all state changes."""
        for unsub in self._unsub_state_changes:
            if unsub:
                unsub()

    @property
    def available(self) -> bool:
        """Return True if at least one pump power sensor is available."""
        for sensor_id in self._pump_power_sensors:
            state = self.hass.states.get(sensor_id)
            if state is not None and state.state not in ("unavailable", "unknown"):
                return True
        return False

    @property
    def native_value(self) -> float | None:
        """Return sum of all available pump power values."""
        total = 0.0
        has_value = False

        for sensor_id in self._pump_power_sensors:
            state = self.hass.states.get(sensor_id)
            if state is not None and state.state not in ("unavailable", "unknown"):
                try:
                    total += float(state.state)
                    has_value = True
                except (ValueError, TypeError):
                    continue

        return total if has_value else None

    @callback
    def _on_power_state_change(self, event):
        """Handle state change in any power entity."""
        self.async_write_ha_state()


class FlushBaseSensor(SensorEntity):
    """Base for reservoir-flush status sensors driven by runtime flush state."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, suffix: str, name: str
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_name = name
        self._unsub_dispatcher: object | None = None
        self._unsub_timer: object | None = None

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    def _status(self) -> dict | None:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None:
            return None
        return flush_status(runtime.flush_state, dt_util.utcnow())

    async def async_added_to_hass(self) -> None:
        @callback
        def _handle_update(*_args) -> None:
            self.async_write_ha_state()

        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            flush_dispatcher_signal(self._entry.entry_id),
            _handle_update,
        )
        self._unsub_timer = async_track_time_interval(
            self.hass, _handle_update, timedelta(hours=1)
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_dispatcher is not None:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None


class FlushLastSensor(FlushBaseSensor):
    """Timestamp of the most recent recorded full flush."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-check"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, FLUSH_LAST_SUFFIX, "Last Flush")

    @property
    def native_value(self):
        status = self._status()
        return status["last_flush"] if status else None


class FlushNextDueSensor(FlushBaseSensor):
    """Timestamp of the next scheduled full flush."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, FLUSH_NEXT_DUE_SUFFIX, "Next Flush Due")

    @property
    def native_value(self):
        status = self._status()
        return status["next_due"] if status else None


class FlushDaysSinceSensor(FlushBaseSensor):
    """Whole days since the last full flush."""

    _attr_icon = "mdi:calendar-range"
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, FLUSH_DAYS_SINCE_SUFFIX, "Days Since Flush")

    @property
    def native_value(self):
        status = self._status()
        return status["days_since"] if status else None


class FlushDaysUntilSensor(FlushBaseSensor):
    """Days until the next full flush (negative when overdue)."""

    _attr_icon = "mdi:calendar-alert"
    _attr_native_unit_of_measurement = UnitOfTime.DAYS

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, FLUSH_DAYS_UNTIL_SUFFIX, "Days Until Flush")

    @property
    def native_value(self):
        status = self._status()
        return status["days_until"] if status else None


def compute_stage_projection(
    stage: str | None, week_in_stage: object, now: datetime
) -> dict[str, object | None]:
    """Project remaining days and milestone dates from stage + week-in-stage.

    `days_in_stage` comes from the operator-entered week-in-stage. Indefinite
    (`mother`) and terminal (`ready`) stages return no remaining days or dates.
    """
    stage = (stage or "").strip().lower()
    result: dict[str, object | None] = {
        "stage": stage or None,
        "days_in_stage": None,
        "days_remaining": None,
        "projected_stage_end": None,
        "projected_harvest_date": None,
        "projected_ready_date": None,
        "pipeline_position": None,
    }
    try:
        weeks = float(week_in_stage)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        weeks = 0.0
    days_in = max(0, int(round(weeks * 7)))
    result["days_in_stage"] = days_in
    if stage in STAGE_PIPELINE:
        result["pipeline_position"] = STAGE_PIPELINE.index(stage) + 1

    duration = STAGE_DURATIONS_DAYS.get(stage)
    if duration is None:
        return result

    days_remaining = max(0, duration - days_in)
    result["days_remaining"] = days_remaining
    result["projected_stage_end"] = (
        (now + timedelta(days=days_remaining)).date().isoformat()
    )

    def _project_to(target: str) -> str | None:
        if stage not in STAGE_PIPELINE or target not in STAGE_PIPELINE:
            return None
        start = STAGE_PIPELINE.index(stage)
        end = STAGE_PIPELINE.index(target)
        if end < start:
            return None
        total = days_remaining
        for name in STAGE_PIPELINE[start + 1 : end + 1]:
            step = STAGE_DURATIONS_DAYS.get(name)
            if step:
                total += step
        return (now + timedelta(days=total)).date().isoformat()

    result["projected_harvest_date"] = _project_to("harvest")
    result["projected_ready_date"] = _project_to("ready")
    return result


class TendrilGrowStageProjectionSensor(SensorEntity):
    """Projected days remaining and milestone dates for the current stage."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Stage Projection"
    _attr_icon = "mdi:calendar-clock"
    _attr_native_unit_of_measurement = UnitOfTime.DAYS

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_stage_projection"
        self._unsub_state: object | None = None
        self._unsub_timer: object | None = None

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    def _source_entity_ids(self) -> list[str]:
        registry = get_entity_registry(self.hass)
        stage_id = registry.async_get_entity_id(
            "select", DOMAIN, f"{self._entry.entry_id}_{CTX_STAGE}"
        )
        week_id = registry.async_get_entity_id(
            "number", DOMAIN, f"{self._entry.entry_id}_{CTX_WEEK_IN_STAGE}"
        )
        return [eid for eid in (stage_id, week_id) if eid]

    def _projection(self) -> dict[str, object | None]:
        registry = get_entity_registry(self.hass)
        stage_id = registry.async_get_entity_id(
            "select", DOMAIN, f"{self._entry.entry_id}_{CTX_STAGE}"
        )
        week_id = registry.async_get_entity_id(
            "number", DOMAIN, f"{self._entry.entry_id}_{CTX_WEEK_IN_STAGE}"
        )
        stage_state = self.hass.states.get(stage_id) if stage_id else None
        week_state = self.hass.states.get(week_id) if week_id else None
        stage = stage_state.state if stage_state else None
        week = week_state.state if week_state else None
        return compute_stage_projection(stage, week, dt_util.now())

    @property
    def native_value(self):
        return self._projection().get("days_remaining")

    @property
    def extra_state_attributes(self):
        projection = self._projection()
        return {
            key: value for key, value in projection.items() if key != "days_remaining"
        }

    @callback
    def _subscribe(self) -> None:
        if self._unsub_state is not None:
            return
        source_ids = self._source_entity_ids()
        if source_ids:
            self._unsub_state = async_track_state_change_event(
                self.hass, source_ids, self._async_source_changed
            )

    @callback
    def _async_source_changed(self, _event) -> None:
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        @callback
        def _refresh(*_args) -> None:
            self._subscribe()
            self.async_write_ha_state()

        self._subscribe()
        self._unsub_timer = async_track_time_interval(
            self.hass, _refresh, timedelta(minutes=30)
        )
        # The sensor platform loads before select/number; retry once they exist.
        async_call_later(self.hass, 15, _refresh)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None
