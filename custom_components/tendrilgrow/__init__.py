"""The TendrilGrow integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .models.grow import GrowSpace

LOGGER = logging.getLogger(__name__)
PLATFORMS: list[str] = ["sensor"]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
SERVICE_REBUILD_AUTOMAP = "rebuild_automap"
ATTR_ENTRY_ID = "entry_id"
_SERVICES_REGISTERED_KEY = "_services_registered"


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
    await _async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TendrilGrow from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    await _async_register_services(hass)

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
    await _async_maybe_unregister_services(hass)
    LOGGER.info("Unloaded grow space entry '%s' (%s)", entry.title, entry.entry_id)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading only the changed entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_services(hass: HomeAssistant) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_SERVICES_REGISTERED_KEY):
        return
    if not hasattr(hass, "services"):
        return

    async def _async_handle_rebuild_automap(call: ServiceCall) -> None:
        requested_entry_id = str(call.data.get(ATTR_ENTRY_ID, "")).strip()
        loaded_entries = [
            entry_id
            for entry_id in hass.data.get(DOMAIN, {})
            if not str(entry_id).startswith("_")
        ]

        if requested_entry_id:
            if requested_entry_id not in loaded_entries:
                raise HomeAssistantError(f"TendrilGrow entry not loaded: {requested_entry_id}")
            target_entries = [requested_entry_id]
        else:
            target_entries = loaded_entries

        for entry_id in target_entries:
            await hass.config_entries.async_reload(entry_id)

        LOGGER.info(
            "Rebuilt TendrilGrow auto-mapping for %d entr%s",
            len(target_entries),
            "y" if len(target_entries) == 1 else "ies",
        )

    hass.services.async_register(DOMAIN, SERVICE_REBUILD_AUTOMAP, _async_handle_rebuild_automap)
    domain_data[_SERVICES_REGISTERED_KEY] = True


async def _async_maybe_unregister_services(hass: HomeAssistant) -> None:
    if not hasattr(hass, "services"):
        return

    domain_data = hass.data.get(DOMAIN, {})
    if not domain_data.get(_SERVICES_REGISTERED_KEY):
        return

    has_loaded_entries = any(not str(key).startswith("_") for key in domain_data)
    if has_loaded_entries:
        return

    hass.services.async_remove(DOMAIN, SERVICE_REBUILD_AUTOMAP)
    domain_data[_SERVICES_REGISTERED_KEY] = False
