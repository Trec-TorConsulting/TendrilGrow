"""The TendrilGrow integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .models.grow import GrowSpace

LOGGER = logging.getLogger(__name__)
PLATFORMS: list[str] = ["sensor"]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass(slots=True)
class RuntimeData:
    """Runtime data for one grow-space config entry."""

    grow_space: GrowSpace
    auto_mapped_sensor_roles: dict[str, str]
    unsubscribe_update_listener: Any


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up from yaml (unused)."""
    _ = config
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TendrilGrow from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    merged_config = dict(entry.data)
    merged_config.update(getattr(entry, "options", {}))
    grow_space = GrowSpace.from_dict(merged_config)
    unsubscribe = entry.add_update_listener(async_update_options)

    runtime = RuntimeData(
        grow_space=grow_space,
        auto_mapped_sensor_roles={},
        unsubscribe_update_listener=unsubscribe,
    )
    hass.data[DOMAIN][entry.entry_id] = runtime
    entry.runtime_data = runtime

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    LOGGER.info("Configured grow space entry '%s' (%s)", entry.title, entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    runtime = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if runtime and runtime.unsubscribe_update_listener:
        runtime.unsubscribe_update_listener()
    LOGGER.info("Unloaded grow space entry '%s' (%s)", entry.title, entry.entry_id)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading only the changed entry."""
    await hass.config_entries.async_reload(entry.entry_id)
