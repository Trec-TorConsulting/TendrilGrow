"""Sensor platform for TendrilGrow."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    PUMP_CONTROL_ROLES,
    WATER_SOURCE_CLOUD,
)
from .coordinator import TendrilGrowTuyaCoordinator, tuya_device_ids
from .entry_config import entry_merged_config
from .local_water_source import effective_water_source
from .pump_energy import pump_power_entity_id
from .sensors.ai import (
    AIFeedingScheduleSensor,
    AIHealthBaseSensor,
    AIHealthLastCheckSensor,
    AIHealthScoreSensor,
    AIHealthSummarySensor,
    AIWeeklyJournalSensor,
    _compose_feeding_schedule_md,
    _compose_report,
)
from .sensors.environment import (
    TendrilGrowDewPointSensor,
    TendrilGrowDliSensor,
    TendrilGrowEnergyCostSensor,
    TendrilGrowVpdSensor,
    _DerivedGrowSensor,
)
from .sensors.flush import (
    FlushBaseSensor,
    FlushDaysSinceSensor,
    FlushDaysUntilSensor,
    FlushLastSensor,
    FlushNextDueSensor,
)
from .sensors.pump_power import (
    TendrilGrowPumpPowerSensor,
    TendrilGrowTotalPumpPowerSensor,
    _resolve_pump_power_source,
)
from .sensors.stage import (
    TendrilGrowStageProjectionSensor,
    TendrilGrowWeekInStageSensor,
    compute_stage_projection,
    resolve_stage_clock,
)
from .sensors.timelapse import (
    TendrilGrowTimelapseFramesSensor,
    TendrilGrowTimelapseLastFrameSensor,
    TimelapseBaseSensor,
)
from .sensors.tuya import (
    _METRIC_TO_ROLE,
    METRICS,
    TendrilGrowMetricDescription,
    TuyaLastUpdatedSensor,
    TuyaMetricSensor,
    _to_float,
)
from .sensors.water_safety import TendrilGrowWaterSafetyStatusSensor

LOGGER = logging.getLogger(__name__)

__all__ = [
    "AIFeedingScheduleSensor",
    "AIHealthBaseSensor",
    "AIHealthLastCheckSensor",
    "AIHealthScoreSensor",
    "AIHealthSummarySensor",
    "AIWeeklyJournalSensor",
    "FlushBaseSensor",
    "FlushDaysSinceSensor",
    "FlushDaysUntilSensor",
    "FlushLastSensor",
    "FlushNextDueSensor",
    "METRICS",
    "TendrilGrowDewPointSensor",
    "TendrilGrowDliSensor",
    "TendrilGrowEnergyCostSensor",
    "TendrilGrowMetricDescription",
    "TendrilGrowPumpPowerSensor",
    "TendrilGrowStageProjectionSensor",
    "TendrilGrowTimelapseFramesSensor",
    "TendrilGrowTimelapseLastFrameSensor",
    "TendrilGrowTotalPumpPowerSensor",
    "TendrilGrowVpdSensor",
    "TendrilGrowWeekInStageSensor",
    "TimelapseBaseSensor",
    "TuyaLastUpdatedSensor",
    "TuyaMetricSensor",
    "_DerivedGrowSensor",
    "_METRIC_TO_ROLE",
    "_compose_feeding_schedule_md",
    "_compose_report",
    "_resolve_pump_power_source",
    "_to_float",
    "async_setup_entry",
    "compute_stage_projection",
    "effective_water_source",
    "pump_power_entity_id",
    "resolve_stage_clock",
    "tuya_device_ids",
]


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
    control_mappings = entry_merged_config(entry).get("control_mappings", {})
    mapped_pump_roles: list[str] = []

    for pump_role in PUMP_CONTROL_ROLES:
        if pump_role in control_mappings:
            power_source = await _resolve_pump_power_source(hass, entry, pump_role)
            entities.append(
                TendrilGrowPumpPowerSensor(hass, entry, pump_role, power_source)
            )
            mapped_pump_roles.append(pump_role)

    # Add total pump power sensor if any pumps are mapped.
    if mapped_pump_roles:
        entities.append(TendrilGrowTotalPumpPowerSensor(hass, entry, mapped_pump_roles))

    # Reservoir full-flush tracking sensors (independent of Tuya).
    entities.extend(
        [
            FlushLastSensor(hass, entry),
            FlushDaysSinceSensor(hass, entry),
            FlushDaysUntilSensor(hass, entry),
            FlushNextDueSensor(hass, entry),
        ]
    )

    # Lifecycle stage clock and projection (independent of Tuya).
    entities.append(TendrilGrowWeekInStageSensor(hass, entry))
    entities.append(TendrilGrowStageProjectionSensor(hass, entry))

    # Derived climate/light/energy insights (independent of Tuya).
    entities.extend(
        [
            TendrilGrowDewPointSensor(hass, entry),
            TendrilGrowDliSensor(hass, entry),
            TendrilGrowEnergyCostSensor(hass, entry),
            TendrilGrowTimelapseFramesSensor(hass, entry),
            TendrilGrowTimelapseLastFrameSensor(hass, entry),
            TendrilGrowWaterSafetyStatusSensor(hass, entry),
        ]
    )

    if entities:
        async_add_entities(entities)
