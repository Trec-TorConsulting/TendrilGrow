"""Binary sensor entities for TendrilGrow."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .ai.health_checks import ai_dispatcher_signal, has_critical_alert
from .const import DOMAIN, FLUSH_DUE_SUFFIX
from .entity import grow_device_info
from .flush import flush_dispatcher_signal, flush_status


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
