"""Environmental and derived insight sensors for TendrilGrow."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_registry import async_get as get_entity_registry
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_LEAF_TEMP_OFFSET,
    CTX_LIGHTS_OFF_TIME,
    CTX_LIGHTS_ON_HOURS,
    CTX_LIGHTS_ON_TIME,
    CTX_PRICE_PER_KWH,
    DEFAULT_LEAF_TEMP_OFFSET,
    DEW_POINT_MARGIN_SUFFIX,
    DOMAIN,
    DRIFT_DIAGNOSIS_SUFFIX,
    LEAF_VPD_SUFFIX,
    PHOTOPERIOD_HOURS_SUFFIX,
    PUMP_CONTROL_ROLES,
    SENSOR_ROLE_EC,
    SENSOR_ROLE_HUMIDITY,
    SENSOR_ROLE_LEAF_TEMPERATURE,
    SENSOR_ROLE_LIGHT,
    SENSOR_ROLE_PH,
    SENSOR_ROLE_TDS,
    SENSOR_ROLE_TEMPERATURE,
    SENSOR_ROLE_WATER_LEVEL,
    TRANSPIRATION_RATE_SUFFIX,
)
from ..entity import grow_device_info
from ..entry_config import entry_merged_config
from ..insights import (
    compute_dew_point_c,
    compute_dew_point_margin,
    compute_dli,
    compute_leaf_vpd_kpa,
    compute_photoperiod_hours,
    compute_transpiration_rate,
    diagnose_reservoir_drift,
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


class TendrilGrowLeafVpdSensor(_DerivedGrowSensor):
    """True Leaf VPD derived from measured leaf temperature or configured offset."""

    _attr_native_unit_of_measurement = "kPa"
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:leaf"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, LEAF_VPD_SUFFIX, "Leaf VPD")

    def _sensor_ids(self) -> tuple[str | None, str | None, str | None]:
        grow_space = self._grow_space()
        if grow_space is None:
            return None, None, None
        return (
            grow_space.sensor_mappings.get(SENSOR_ROLE_TEMPERATURE),
            grow_space.sensor_mappings.get(SENSOR_ROLE_HUMIDITY),
            grow_space.sensor_mappings.get(SENSOR_ROLE_LEAF_TEMPERATURE),
        )

    def _source_entity_ids(self) -> list[str]:
        return [eid for eid in self._sensor_ids() if eid]

    @property
    def native_value(self):
        temp_id, hum_id, leaf_id = self._sensor_ids()
        temp_state = self.hass.states.get(temp_id) if temp_id else None
        hum_state = self.hass.states.get(hum_id) if hum_id else None
        leaf_state = self.hass.states.get(leaf_id) if leaf_id else None

        if temp_state is None or hum_state is None:
            return None

        temp_c = GrowSpace.to_celsius(
            _to_float(temp_state.state),
            temp_state.attributes.get("unit_of_measurement"),
        )
        hum_pct = _to_float(hum_state.state)
        leaf_c = (
            GrowSpace.to_celsius(
                _to_float(leaf_state.state),
                leaf_state.attributes.get("unit_of_measurement"),
            )
            if leaf_state
            else None
        )

        offset_f = entry_merged_config(self._entry).get(
            CONF_LEAF_TEMP_OFFSET, DEFAULT_LEAF_TEMP_OFFSET
        )
        try:
            offset_f = float(offset_f)
        except (ValueError, TypeError):
            offset_f = DEFAULT_LEAF_TEMP_OFFSET

        return compute_leaf_vpd_kpa(
            temp_c, hum_pct, leaf_temp_c=leaf_c, offset_f=offset_f
        )

    @property
    def extra_state_attributes(self):
        temp_id, hum_id, leaf_id = self._sensor_ids()
        leaf_state = self.hass.states.get(leaf_id) if leaf_id else None
        offset_f = entry_merged_config(self._entry).get(
            CONF_LEAF_TEMP_OFFSET, DEFAULT_LEAF_TEMP_OFFSET
        )
        return {
            "air_temperature_entity": temp_id,
            "air_humidity_entity": hum_id,
            "leaf_temperature_entity": leaf_id,
            "leaf_temperature_source": "sensor" if leaf_state else "offset",
            "leaf_temp_offset_applied": offset_f if not leaf_state else None,
        }


class TendrilGrowDewPointMarginSensor(_DerivedGrowSensor):
    """Dew point margin (T_surface - T_dew) to monitor condensation risk."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:thermometer-chevron-up"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, DEW_POINT_MARGIN_SUFFIX, "Dew Point Margin")

    def _sensor_ids(self) -> tuple[str | None, str | None, str | None]:
        grow_space = self._grow_space()
        if grow_space is None:
            return None, None, None
        return (
            grow_space.sensor_mappings.get(SENSOR_ROLE_TEMPERATURE),
            grow_space.sensor_mappings.get(SENSOR_ROLE_HUMIDITY),
            grow_space.sensor_mappings.get(SENSOR_ROLE_LEAF_TEMPERATURE),
        )

    def _source_entity_ids(self) -> list[str]:
        return [eid for eid in self._sensor_ids() if eid]

    @property
    def native_unit_of_measurement(self) -> str:
        temp_id, _hum_id, _leaf_id = self._sensor_ids()
        state = self.hass.states.get(temp_id) if temp_id else None
        unit = (state.attributes.get("unit_of_measurement") if state else "") or ""
        if "f" in unit.lower():
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def native_value(self):
        temp_id, hum_id, leaf_id = self._sensor_ids()
        temp_state = self.hass.states.get(temp_id) if temp_id else None
        hum_state = self.hass.states.get(hum_id) if hum_id else None
        leaf_state = self.hass.states.get(leaf_id) if leaf_id else None

        if temp_state is None or hum_state is None:
            return None

        temp_c = GrowSpace.to_celsius(
            _to_float(temp_state.state),
            temp_state.attributes.get("unit_of_measurement"),
        )
        hum_pct = _to_float(hum_state.state)
        leaf_c = (
            GrowSpace.to_celsius(
                _to_float(leaf_state.state),
                leaf_state.attributes.get("unit_of_measurement"),
            )
            if leaf_state
            else None
        )

        margin_c = compute_dew_point_margin(temp_c, hum_pct, leaf_temp_c=leaf_c)
        if margin_c is None:
            return None

        if self.native_unit_of_measurement == UnitOfTemperature.FAHRENHEIT:
            return round(margin_c * 1.8, 1)
        return margin_c

    @property
    def extra_state_attributes(self):
        temp_id, hum_id, leaf_id = self._sensor_ids()
        temp_state = self.hass.states.get(temp_id) if temp_id else None
        hum_state = self.hass.states.get(hum_id) if hum_id else None
        temp_c = (
            GrowSpace.to_celsius(
                _to_float(temp_state.state),
                temp_state.attributes.get("unit_of_measurement"),
            )
            if temp_state
            else None
        )
        hum_pct = _to_float(hum_state.state) if hum_state else None
        dew_point_c = compute_dew_point_c(temp_c, hum_pct)
        return {
            "dew_point_c": dew_point_c,
            "surface_temperature_source": "leaf" if leaf_id else "air",
        }


class TendrilGrowReservoirDriftSensor(_DerivedGrowSensor):
    """RDWC reservoir EC vs. pH drift diagnostic classification."""

    _attr_icon = "mdi:chart-bell-curve-cumulative"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass, entry, DRIFT_DIAGNOSIS_SUFFIX, "Reservoir Drift Diagnosis"
        )
        self._samples: list[tuple[datetime, float, float, float | None]] = []
        self._last_sample_time: datetime | None = None

    def _water_ids(self) -> tuple[str | None, str | None, str | None]:
        grow_space = self._grow_space()
        if grow_space is None:
            return None, None, None
        return (
            grow_space.sensor_mappings.get(SENSOR_ROLE_EC)
            or grow_space.sensor_mappings.get(SENSOR_ROLE_TDS),
            grow_space.sensor_mappings.get(SENSOR_ROLE_PH),
            grow_space.sensor_mappings.get(SENSOR_ROLE_WATER_LEVEL),
        )

    def _source_entity_ids(self) -> list[str]:
        return [eid for eid in self._water_ids() if eid]

    def _record_sample(
        self,
        now: datetime,
        ec: float | None,
        ph: float | None,
        water: float | None,
    ) -> None:
        if ec is None or ph is None:
            return
        if self._last_sample_time is not None:
            if (now - self._last_sample_time).total_seconds() < 300:  # 5 min
                return
        self._last_sample_time = now
        self._samples.append((now, ec, ph, water))
        cutoff = now - timedelta(hours=24)
        self._samples = [s for s in self._samples if s[0] >= cutoff]

    def _diagnose(self) -> dict[str, Any]:
        ec_id, ph_id, water_id = self._water_ids()
        ec = self._read_float(ec_id)
        ph = self._read_float(ph_id)
        water = self._read_float(water_id)

        now = dt_util.now()
        self._record_sample(now, ec, ph, water)
        return diagnose_reservoir_drift(self._samples, ec, ph, water)

    @property
    def native_value(self):
        diag = self._diagnose()
        return diag.get("status")

    @property
    def extra_state_attributes(self):
        diag = self._diagnose()
        ec_id, ph_id, water_id = self._water_ids()
        return {
            "ec_current": self._read_float(ec_id),
            "ph_current": self._read_float(ph_id),
            "water_current": self._read_float(water_id),
            "ec_delta_24h": diag.get("ec_delta_24h"),
            "ph_delta_24h": diag.get("ph_delta_24h"),
            "water_delta_24h": diag.get("water_delta_24h"),
            "recommendation": diag.get("recommendation"),
            "sample_count": len(self._samples),
        }


class TendrilGrowTranspirationRateSensor(_DerivedGrowSensor):
    """Daily water consumption / transpiration rate derived from water level."""

    _attr_icon = "mdi:water-minus"
    _attr_suggested_display_precision = 2
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass, entry, TRANSPIRATION_RATE_SUFFIX, "Daily Transpiration Rate"
        )
        self._water_samples: list[tuple[datetime, float]] = []
        self._last_sample_time: datetime | None = None

    def _water_level_id(self) -> str | None:
        grow_space = self._grow_space()
        if grow_space is None:
            return None
        return grow_space.sensor_mappings.get(SENSOR_ROLE_WATER_LEVEL)

    def _source_entity_ids(self) -> list[str]:
        eid = self._water_level_id()
        return [eid] if eid else []

    @property
    def native_unit_of_measurement(self) -> str | None:
        eid = self._water_level_id()
        if not eid:
            return "units/d"
        state = self.hass.states.get(eid)
        unit = (state.attributes.get("unit_of_measurement") if state else "") or ""
        return f"{unit}/d" if unit else "units/d"

    def _record_sample(self, now: datetime, water: float | None) -> None:
        if water is None:
            return
        if self._last_sample_time is not None:
            if (now - self._last_sample_time).total_seconds() < 600:  # 10 min
                return
        self._last_sample_time = now
        self._water_samples.append((now, water))
        cutoff = now - timedelta(hours=24)
        self._water_samples = [s for s in self._water_samples if s[0] >= cutoff]

    def _eval(self) -> dict[str, Any]:
        eid = self._water_level_id()
        water = self._read_float(eid)
        now = dt_util.now()
        self._record_sample(now, water)
        return compute_transpiration_rate(self._water_samples)

    @property
    def native_value(self):
        res = self._eval()
        return res.get("rate_daily")

    @property
    def extra_state_attributes(self):
        res = self._eval()
        eid = self._water_level_id()
        return {
            "consumption_status": res.get("status"),
            "stalled_alert": res.get("status") == "stalled",
            "water_level_entity": eid,
            "sample_count": len(self._water_samples),
        }


class TendrilGrowPhotoperiodSensor(_DerivedGrowSensor):
    """Photoperiod hours computed from schedule clock or lights-on setting."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:weather-sunny-alert"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, PHOTOPERIOD_HOURS_SUFFIX, "Photoperiod Hours")

    def _schedule_entities(self) -> tuple[str | None, str | None]:
        registry = get_entity_registry(self.hass)
        return (
            registry.async_get_entity_id(
                "time", DOMAIN, f"{self._entry.entry_id}_{CTX_LIGHTS_ON_TIME}"
            ),
            registry.async_get_entity_id(
                "time", DOMAIN, f"{self._entry.entry_id}_{CTX_LIGHTS_OFF_TIME}"
            ),
        )

    def _source_entity_ids(self) -> list[str]:
        on_id, off_id = self._schedule_entities()
        hours_id = self._number_entity(CTX_LIGHTS_ON_HOURS)
        return [eid for eid in (on_id, off_id, hours_id) if eid]

    @property
    def native_value(self):
        on_id, off_id = self._schedule_entities()
        on_state = self.hass.states.get(on_id) if on_id else None
        off_state = self.hass.states.get(off_id) if off_id else None

        if on_state and off_state and on_state.state and off_state.state:
            hours = compute_photoperiod_hours(on_state.state, off_state.state)
            if hours is not None:
                return hours

        return self._read_float(self._number_entity(CTX_LIGHTS_ON_HOURS))
