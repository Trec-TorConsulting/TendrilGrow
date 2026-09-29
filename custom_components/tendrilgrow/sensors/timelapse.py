"""Timelapse sensors for TendrilGrow."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from ..const import CONF_TIMELAPSE_DIR, DOMAIN
from ..entity import grow_device_info
from ..timelapse import (
    list_frame_files,
    parse_frame_timestamp,
    resolve_timelapse_paths,
    timelapse_dispatcher_signal,
)


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
