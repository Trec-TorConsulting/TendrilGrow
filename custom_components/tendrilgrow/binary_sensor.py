"""Binary sensor entities for TendrilGrow."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get as get_entity_registry
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .ai.health_checks import ai_dispatcher_signal, has_critical_alert
from .const import (
    CTX_STAGE,
    DOMAIN,
    FLUSH_DUE_SUFFIX,
    MOLD_RISK_SUFFIX,
    SENSOR_ROLE_HUMIDITY,
    SENSOR_ROLE_LEAF_TEMPERATURE,
    SENSOR_ROLE_TEMPERATURE,
)
from .entity import grow_device_info
from .flush import flush_dispatcher_signal, flush_status
from .insights import compute_dew_point_margin, compute_mold_risk
from .metric_bands import (
    METRIC_EC,
    METRIC_PH,
    METRIC_VPD,
    metric_band_dispatcher_signal,
)
from .models.grow import GrowSpace
from .sensors.tuya import _to_float
from .water_safety import water_safety_dispatcher_signal


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TendrilGrow binary sensors."""
    async_add_entities(
        [
            AIHealthAlertBinarySensor(hass, entry),
            FlushDueBinarySensor(hass, entry),
            MetricBandBinarySensor(hass, entry, METRIC_PH, "pH Out of Range"),
            MetricBandBinarySensor(hass, entry, METRIC_EC, "EC Out of Range"),
            MetricBandBinarySensor(hass, entry, METRIC_VPD, "VPD Out of Range"),
            MetricBandSummaryBinarySensor(hass, entry),
            FlowOkBinarySensor(hass, entry),
            LeakDetectedBinarySensor(hass, entry),
            TendrilGrowMoldRiskBinarySensor(hass, entry),
        ]
    )


class AIHealthAlertBinarySensor(BinarySensorEntity):
    """Turns on when AI health score enters the configured critical range."""

    _attr_has_entity_name = True
    _attr_name = "AI Health Critical Alert"
    _attr_icon = "mdi:alert"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_ai_health_critical_alert"
        self._unsub_dispatcher = None

    async def async_added_to_hass(self) -> None:
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
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    @property
    def is_on(self) -> bool:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None:
            return False
        return has_critical_alert(self._entry, runtime.ai_health_state)

    @property
    def extra_state_attributes(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None:
            return None
        latest = runtime.ai_health_state.latest
        if latest is None:
            return {"running": runtime.ai_health_state.running}
        return {
            "score": latest.score,
            "severity": latest.severity,
            "summary": latest.summary,
            "checked_at": latest.checked_at.isoformat(),
            "running": runtime.ai_health_state.running,
        }


class FlushDueBinarySensor(BinarySensorEntity):
    """Turns on when the reservoir flush interval has elapsed."""

    _attr_has_entity_name = True
    _attr_name = "Flush Due"
    _attr_icon = "mdi:water-alert"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{FLUSH_DUE_SUFFIX}"
        self._unsub_dispatcher: object | None = None
        self._unsub_timer: object | None = None

    @property
    def device_info(self):
        return grow_device_info(self._entry)

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

    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    def _status(self) -> dict | None:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None:
            return None
        return flush_status(runtime.flush_state, dt_util.utcnow())

    @property
    def is_on(self) -> bool:
        status = self._status()
        return bool(status["due"]) if status else False

    @property
    def extra_state_attributes(self):
        status = self._status()
        if status is None:
            return None
        last = status["last_flush"]
        nxt = status["next_due"]
        return {
            "days_since": status["days_since"],
            "days_until": status["days_until"],
            "interval_days": status["interval_days"],
            "last_flush": last.isoformat() if last else None,
            "next_due": nxt.isoformat() if nxt else None,
        }


class MetricBandBinarySensor(BinarySensorEntity):
    """Problem sensor when a live metric is outside its target band."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_should_poll = False
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        metric: str,
        name: str,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._metric = metric
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_metric_band_{metric}"
        self._unsub_dispatcher: object | None = None

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    async def async_added_to_hass(self) -> None:
        @callback
        def _handle_update() -> None:
            self.async_write_ha_state()

        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            metric_band_dispatcher_signal(self._entry.entry_id),
            _handle_update,
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_dispatcher is not None:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None

    def _band_state(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None:
            return None
        return runtime.metric_band_state

    @property
    def available(self) -> bool:
        state = self._band_state()
        if state is None:
            return False
        if not state.has_band.get(self._metric, False):
            return True
        return state.source_available.get(self._metric, False)

    @property
    def is_on(self) -> bool:
        state = self._band_state()
        if state is None or not state.has_band.get(self._metric, False):
            return False
        if not state.source_available.get(self._metric, False):
            return False
        return bool(state.out_of_range.get(self._metric, False))


class MetricBandSummaryBinarySensor(BinarySensorEntity):
    """Summary problem sensor when any metric band is breached."""

    _attr_has_entity_name = True
    _attr_name = "Metrics Out of Range"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_should_poll = False
    _attr_icon = "mdi:alert"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_metric_band_summary"
        self._unsub_dispatcher: object | None = None

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    async def async_added_to_hass(self) -> None:
        @callback
        def _handle_update() -> None:
            self.async_write_ha_state()

        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            metric_band_dispatcher_signal(self._entry.entry_id),
            _handle_update,
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_dispatcher is not None:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None

    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    @property
    def is_on(self) -> bool:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None:
            return False
        state = runtime.metric_band_state
        for metric, out in state.out_of_range.items():
            if (
                state.has_band.get(metric)
                and state.source_available.get(metric)
                and out
            ):
                return True
        return False


class FlowOkBinarySensor(BinarySensorEntity):
    """Turns on when circulation water flow is verified (or pump is idle)."""

    _attr_has_entity_name = True
    _attr_name = "Flow OK"
    _attr_icon = "mdi:water-check"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_flow_ok"
        self._unsub_dispatcher: object | None = None

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    async def async_added_to_hass(self) -> None:
        @callback
        def _handle_update() -> None:
            self.async_write_ha_state()

        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            water_safety_dispatcher_signal(self._entry.entry_id),
            _handle_update,
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_dispatcher is not None:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None

    @property
    def is_on(self) -> bool:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if (
            runtime is not None
            and getattr(runtime, "water_safety_monitor", None) is not None
        ):
            return runtime.water_safety_monitor.flow_ok
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        mon = getattr(runtime, "water_safety_monitor", None) if runtime else None
        if mon is None:
            return {}
        return {
            "flow_rate": mon.flow_rate,
            "pump_entity_id": mon.rdwc_pump_entity_id,
        }


class LeakDetectedBinarySensor(BinarySensorEntity):
    """Turns on when any mapped leak sensor detects moisture (debounced)."""

    _attr_has_entity_name = True
    _attr_name = "Leak Detected"
    _attr_icon = "mdi:water-alert"
    _attr_device_class = BinarySensorDeviceClass.MOISTURE
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_leak_detected"
        self._unsub_dispatcher: object | None = None

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    async def async_added_to_hass(self) -> None:
        @callback
        def _handle_update() -> None:
            self.async_write_ha_state()

        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            water_safety_dispatcher_signal(self._entry.entry_id),
            _handle_update,
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_dispatcher is not None:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None

    @property
    def is_on(self) -> bool:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if (
            runtime is not None
            and getattr(runtime, "water_safety_monitor", None) is not None
        ):
            return runtime.water_safety_monitor.leak_detected
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        mon = getattr(runtime, "water_safety_monitor", None) if runtime else None
        if mon is None:
            return {}
        return {
            "active_leaks": mon.active_leaks,
            "shutoff_triggered": mon.shutoff_triggered,
        }


class TendrilGrowMoldRiskBinarySensor(BinarySensorEntity):
    """Turns on when dew point margin is critical or humidity >=65% in flower/cure."""

    _attr_has_entity_name = True
    _attr_name = "Mold Risk"
    _attr_icon = "mdi:shield-alert"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{MOLD_RISK_SUFFIX}"
        self._state_unsubs: list = []
        self._timer_unsubs: list = []

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    def _grow_space(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        return getattr(runtime, "grow_space", None)

    def _tracked_entity_ids(self) -> list[str]:
        grow_space = self._grow_space()
        if grow_space is None:
            return []
        registry = get_entity_registry(self.hass)
        stage_eid = registry.async_get_entity_id(
            "select", DOMAIN, f"{self._entry.entry_id}_{CTX_STAGE}"
        )
        candidates = [
            grow_space.sensor_mappings.get(SENSOR_ROLE_TEMPERATURE),
            grow_space.sensor_mappings.get(SENSOR_ROLE_HUMIDITY),
            grow_space.sensor_mappings.get(SENSOR_ROLE_LEAF_TEMPERATURE),
            stage_eid,
        ]
        return [eid for eid in candidates if eid]

    def _eval(self) -> tuple[bool, list[str], str, float | None, float | None]:
        grow_space = self._grow_space()
        if grow_space is None:
            return False, [], "Grow space unavailable", None, None
        temp_id = grow_space.sensor_mappings.get(SENSOR_ROLE_TEMPERATURE)
        hum_id = grow_space.sensor_mappings.get(SENSOR_ROLE_HUMIDITY)
        leaf_id = grow_space.sensor_mappings.get(SENSOR_ROLE_LEAF_TEMPERATURE)

        temp_state = self.hass.states.get(temp_id) if temp_id else None
        hum_state = self.hass.states.get(hum_id) if hum_id else None
        leaf_state = self.hass.states.get(leaf_id) if leaf_id else None

        if temp_state is None or hum_state is None:
            return False, [], "Missing temperature or humidity data", None, None

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

        registry = get_entity_registry(self.hass)
        stage_eid = registry.async_get_entity_id(
            "select", DOMAIN, f"{self._entry.entry_id}_{CTX_STAGE}"
        )
        stage_state = self.hass.states.get(stage_eid) if stage_eid else None
        stage = stage_state.state if stage_state else None

        margin_c = compute_dew_point_margin(temp_c, hum_pct, leaf_temp_c=leaf_c)
        is_risk, factors, rec = compute_mold_risk(margin_c, hum_pct, stage=stage)
        return is_risk, factors, rec, margin_c, hum_pct

    @property
    def is_on(self) -> bool:
        is_risk, _factors, _rec, _margin, _hum = self._eval()
        return is_risk

    @property
    def extra_state_attributes(self):
        _is_risk, factors, rec, margin, hum = self._eval()
        return {
            "risk_factors": factors,
            "recommendation": rec,
            "dew_point_margin_c": margin,
            "humidity_pct": hum,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._resubscribe()
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
        tracked = self._tracked_entity_ids()
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
