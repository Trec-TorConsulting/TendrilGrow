"""Environmental and derived insight sensors for TendrilGrow."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_registry import async_get as get_entity_registry
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)
from homeassistant.util import dt as dt_util

from ..const import (
    CTX_LIGHTS_ON_HOURS,
    CTX_PRICE_PER_KWH,
    DOMAIN,
    PUMP_CONTROL_ROLES,
    SENSOR_ROLE_HUMIDITY,
    SENSOR_ROLE_LIGHT,
    SENSOR_ROLE_TEMPERATURE,
)
from ..entity import grow_device_info
from ..entry_config import entry_merged_config
from ..insights import (
    compute_dew_point_c,
    compute_dli,
    estimate_daily_cost,
)
from ..models.grow import GrowSpace
from ..pump_energy import (
    compute_daily_pump_energy_kwh,
    pump_energy_dispatcher_signal,
    pump_power_entity_id,
    pump_switch_entity_id,
)
from .tuya import _to_float


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
    """Estimated daily pump electricity cost from observed on-time."""

    _attr_icon = "mdi:cash-clock"
    _attr_suggested_display_precision = 2

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "pump_daily_cost", "Pump Daily Cost (est.)")
        self._attr_native_unit_of_measurement = getattr(
            getattr(hass, "config", None), "currency", None
        )
        self._unsub_pump_energy: Any = None

    def _power_id(self) -> str | None:
        registry = get_entity_registry(self.hass)
        return registry.async_get_entity_id(
            "sensor", DOMAIN, f"{self._entry.entry_id}_total_pump_power"
        )

    def _source_entity_ids(self) -> list[str]:
        ids = [self._number_entity(CTX_PRICE_PER_KWH), self._power_id()]
        merged = entry_merged_config(self._entry)
        for pump_role in PUMP_CONTROL_ROLES:
            if pump_role not in merged.get("control_mappings", {}):
                continue
            for resolver in (pump_power_entity_id, pump_switch_entity_id):
                entity_id = resolver(self.hass, self._entry, pump_role)
                if entity_id:
                    ids.append(entity_id)
        return [eid for eid in ids if eid]

    def _energy_kwh(self) -> tuple[float | None, dict[str, Any]]:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        state = getattr(runtime, "pump_energy_state", None)
        if state is None:
            return None, {"estimated": True}
        return compute_daily_pump_energy_kwh(
            self.hass, self._entry, state, dt_util.now()
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _on_pump_energy() -> None:
            self.async_write_ha_state()

        self._unsub_pump_energy = async_dispatcher_connect(
            self.hass,
            pump_energy_dispatcher_signal(self._entry.entry_id),
            _on_pump_energy,
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_pump_energy:
            self._unsub_pump_energy()
            self._unsub_pump_energy = None
        await super().async_will_remove_from_hass()

    @property
    def native_value(self):
        energy, _attrs = self._energy_kwh()
        cost = estimate_daily_cost(
            energy,
            self._read_float(self._number_entity(CTX_PRICE_PER_KWH)),
        )
        return round(cost, 2) if cost is not None else None

    @property
    def extra_state_attributes(self):
        energy, attrs = self._energy_kwh()
        result = dict(attrs)
        result["energy_kwh_per_day"] = round(energy, 3) if energy is not None else None
        return result
