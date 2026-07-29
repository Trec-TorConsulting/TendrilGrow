"""Data coordinators for TendrilGrow runtime polling."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_TUYA_ACCESS_ID,
    CONF_TUYA_ACCESS_SECRET,
    CONF_TUYA_DEVICE_IDS,
    CONF_TUYA_ENABLED,
    CONF_TUYA_REGION,
    CONF_TUYA_SCAN_INTERVAL,
    CONF_TUYA_UID,
)
from .tuya_client import TuyaCloudClient, normalize_tuya_statuses

LOGGER = logging.getLogger(__name__)


def _entry_merged_config(entry: ConfigEntry) -> dict[str, Any]:
    merged = dict(entry.data)
    merged.update(entry.options)
    return merged


def tuya_enabled(entry: ConfigEntry) -> bool:
    cfg = _entry_merged_config(entry)
    return bool(cfg.get(CONF_TUYA_ENABLED, False))


def tuya_device_ids(entry: ConfigEntry) -> list[str]:
    cfg = _entry_merged_config(entry)
    raw = cfg.get(CONF_TUYA_DEVICE_IDS, [])
    if isinstance(raw, list):
        return [str(device_id).strip() for device_id in raw if str(device_id).strip()]
    if isinstance(raw, str):
        return [device_id.strip() for device_id in raw.split(",") if device_id.strip()]
    return []


def has_tuya_credentials(entry: ConfigEntry) -> bool:
    cfg = _entry_merged_config(entry)
    return bool(cfg.get(CONF_TUYA_ACCESS_ID) and cfg.get(CONF_TUYA_ACCESS_SECRET))


class TendrilGrowTuyaCoordinator(DataUpdateCoordinator[dict[str, dict[str, float]]]):
    """Poll Tuya cloud and expose latest normalized metric values by device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._entry = entry
        cfg = _entry_merged_config(entry)
        scan_interval = max(30, int(cfg.get(CONF_TUYA_SCAN_INTERVAL, 60) or 60))

        super().__init__(
            hass,
            LOGGER,
            name=f"{entry.entry_id}_tuya",
            update_interval=timedelta(seconds=scan_interval),
        )

        self.device_names: dict[str, str] = {}
        self.device_last_updated: dict[str, datetime] = {}
        access_id = str(cfg.get(CONF_TUYA_ACCESS_ID, "")).strip()
        access_secret = str(cfg.get(CONF_TUYA_ACCESS_SECRET, "")).strip()
        region = str(cfg.get(CONF_TUYA_REGION, "us")).strip().lower() or "us"
        self._client = TuyaCloudClient(
            async_get_clientsession(hass),
            access_id,
            access_secret,
            region,
        )
        self._uid = str(cfg.get(CONF_TUYA_UID, "")).strip()
        LOGGER.info(
            "Configured TendrilGrow Tuya polling for %s: region=%s, "
            "uid_set=%s, device_count=%d",
            entry.entry_id,
            region,
            bool(self._uid),
            len(tuya_device_ids(entry)),
        )

    async def _async_update_data(self) -> dict[str, dict[str, float]]:
        device_ids = tuya_device_ids(self._entry)
        if not device_ids:
            return {}

        if self._uid:
            try:
                for device in await self._client.list_user_devices(self._uid):
                    device_id = str(device.get("id", "")).strip()
                    if not device_id:
                        continue
                    name = str(device.get("name", "")).strip()
                    if name:
                        self.device_names[device_id] = name
            except Exception as err:  # noqa: BLE001
                LOGGER.debug("Unable to refresh Tuya device names: %s", err)

        readings: dict[str, dict[str, float]] = {}
        failures: list[str] = []

        for device_id in device_ids:
            try:
                statuses = await self._client.fetch_device_statuses(device_id)
                readings[device_id] = normalize_tuya_statuses(statuses)
                self.device_last_updated[device_id] = datetime.now(UTC)
            except Exception as err:  # noqa: BLE001
                failures.append(f"{device_id}: {err}")

        if not readings and failures:
            raise UpdateFailed("; ".join(failures))

        if failures:
            LOGGER.warning(
                "Partial Tuya poll failure for %s: %s",
                self._entry.entry_id,
                "; ".join(failures),
            )

        populated_devices = sum(1 for metrics in readings.values() if metrics)
        LOGGER.info(
            "TendrilGrow Tuya poll for %s completed: devices=%d, populated=%d",
            self._entry.entry_id,
            len(readings),
            populated_devices,
        )

        return readings
