"""Reservoir flush tracking sensors for TendrilGrow."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from ..const import (
    DOMAIN,
    FLUSH_DAYS_SINCE_SUFFIX,
    FLUSH_DAYS_UNTIL_SUFFIX,
    FLUSH_LAST_SUFFIX,
    FLUSH_NEXT_DUE_SUFFIX,
)
from ..entity import grow_device_info
from ..flush import flush_dispatcher_signal, flush_status


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
