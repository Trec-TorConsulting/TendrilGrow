"""Resolve and auto-map LocalTuya / Tuya Local water-monitor devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_TUYA_DEVICE_IDS,
    CONF_WATER_MONITOR_DEVICE_ID,
    LOCALTUYA_DOMAIN,
    SENSOR_ROLE_CF,
    SENSOR_ROLE_EC,
    SENSOR_ROLE_ORP,
    SENSOR_ROLE_PH,
    SENSOR_ROLE_TDS,
    SENSOR_ROLE_WATER_TEMPERATURE,
    SENSOR_ROLES_LOCAL_WATER_AUTOMAP,
    TUYA_LOCAL_DOMAIN,
    WATER_SOURCE_CLOUD,
    WATER_SOURCE_LOCALTUYA,
    WATER_SOURCE_NONE,
    WATER_SOURCE_TUYA_LOCAL,
)
from .coordinator import has_tuya_credentials, tuya_device_ids, tuya_enabled

LOGGER = logging.getLogger(__name__)

_EC_UNITS = frozenset({"ms/cm", "µs/cm", "us/cm", "μs/cm"})
_TDS_UNITS = frozenset({"ppm"})
_ORP_UNITS = frozenset({"mv"})


def _entry_merged_config(entry: ConfigEntry) -> dict[str, Any]:
    merged = dict(entry.data)
    merged.update(getattr(entry, "options", {}) or {})
    return merged


def stored_water_monitor_device_id(entry: ConfigEntry) -> str | None:
    """Return the configured HA device id, if any."""
    raw = _entry_merged_config(entry).get(CONF_WATER_MONITOR_DEVICE_ID, "")
    device_id = str(raw or "").strip()
    return device_id or None


def _iter_identifiers(device: dr.DeviceEntry):
    """Yield ``(domain, ident)`` pairs from a device registry entry.

    Home Assistant 2026+ can store 3-tuples in ``identifiers``; unpacking as
    ``domain, ident = item`` then crashes the sensor platform.
    """
    for item in getattr(device, "identifiers", None) or ():
        if not item:
            continue
        domain = str(item[0])
        ident = str(item[1]) if len(item) > 1 else ""
        yield domain, ident


def _device_local_domain(device: dr.DeviceEntry) -> str | None:
    """Return localtuya or tuya_local if the device identifiers include that domain."""
    domains = {domain for domain, _ident in _iter_identifiers(device)}
    if LOCALTUYA_DOMAIN in domains:
        return LOCALTUYA_DOMAIN
    if TUYA_LOCAL_DOMAIN in domains:
        return TUYA_LOCAL_DOMAIN
    return None


def _identifier_matches_tuya_id(device: dr.DeviceEntry, tuya_ids: set[str]) -> bool:
    for _domain, ident in _iter_identifiers(device):
        if ident in tuya_ids:
            return True
    return False


def find_unique_local_match(
    hass: HomeAssistant,
    tuya_ids: list[str],
) -> tuple[str, str] | None:
    """Match stored Tuya device ids to exactly one local HA device.

    Prefers ``localtuya`` over ``tuya_local``. Returns ``(ha_device_id, domain)``
    or ``None`` when zero or multiple matches exist.
    """
    cleaned = {
        str(device_id).strip() for device_id in tuya_ids if str(device_id).strip()
    }
    if not cleaned:
        return None

    try:
        registry = dr.async_get(hass)
    except Exception:  # noqa: BLE001
        return None

    matches: list[tuple[str, str]] = []
    for device in registry.devices.values():
        try:
            domain = _device_local_domain(device)
            if domain is None:
                continue
            if _identifier_matches_tuya_id(device, cleaned):
                matches.append((device.id, domain))
        except Exception:  # noqa: BLE001
            continue

    if not matches:
        return None

    localtuya_hits = [m for m in matches if m[1] == LOCALTUYA_DOMAIN]
    if len(localtuya_hits) == 1:
        return localtuya_hits[0]
    if len(localtuya_hits) > 1:
        return None

    tuya_local_hits = [m for m in matches if m[1] == TUYA_LOCAL_DOMAIN]
    if len(tuya_local_hits) == 1:
        return tuya_local_hits[0]
    return None


async def async_resolve_water_monitor_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    persist: bool = True,
) -> tuple[str, str] | None:
    """Resolve a bound local water-monitor device for this grow space.

    Returns ``(ha_device_id, domain)`` where domain is ``localtuya`` or
    ``tuya_local``, or ``None`` when unbound / invalid.
    """
    stored = stored_water_monitor_device_id(entry)
    try:
        registry = dr.async_get(hass)
    except Exception:  # noqa: BLE001
        return None

    if stored:
        device = registry.async_get(stored)
        if device is not None:
            domain = _device_local_domain(device)
            if domain is not None:
                return stored, domain
        LOGGER.warning(
            "Configured water monitor device %s is missing or not localtuya/"
            "tuya_local for entry %s",
            stored,
            entry.entry_id,
        )

    cfg = _entry_merged_config(entry)
    raw_ids = cfg.get(CONF_TUYA_DEVICE_IDS, [])
    if isinstance(raw_ids, str):
        tuya_ids = [part.strip() for part in raw_ids.split(",") if part.strip()]
    elif isinstance(raw_ids, list):
        tuya_ids = [str(part).strip() for part in raw_ids if str(part).strip()]
    else:
        tuya_ids = []

    match = find_unique_local_match(hass, tuya_ids)
    if match is None:
        return None

    device_id, domain = match
    if persist and stored != device_id:
        new_data = dict(entry.data)
        new_data[CONF_WATER_MONITOR_DEVICE_ID] = device_id
        hass.config_entries.async_update_entry(entry, data=new_data)
        LOGGER.info(
            "Auto-bound water monitor device %s (%s) for entry %s",
            device_id,
            domain,
            entry.entry_id,
        )
    return device_id, domain


def effective_water_source(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """Return ``localtuya`` | ``tuya_local`` | ``cloud`` | ``none``.

    A bound local device always wins over ``tuya_enabled``.
    """
    stored = stored_water_monitor_device_id(entry)
    if stored:
        try:
            registry = dr.async_get(hass)
            device = registry.async_get(stored)
        except Exception:  # noqa: BLE001
            device = None
        if device is not None:
            domain = _device_local_domain(device)
            if domain == LOCALTUYA_DOMAIN:
                return WATER_SOURCE_LOCALTUYA
            if domain == TUYA_LOCAL_DOMAIN:
                return WATER_SOURCE_TUYA_LOCAL

    # Unique registry match without requiring persist (read-only check).
    match = find_unique_local_match(hass, tuya_device_ids(entry))
    if match is not None:
        _device_id, domain = match
        if domain == LOCALTUYA_DOMAIN:
            return WATER_SOURCE_LOCALTUYA
        return WATER_SOURCE_TUYA_LOCAL

    if tuya_enabled(entry) and has_tuya_credentials(entry) and tuya_device_ids(entry):
        return WATER_SOURCE_CLOUD
    return WATER_SOURCE_NONE


def _entity_text(entity: er.RegistryEntry) -> str:
    parts = [
        str(entity.entity_id or ""),
        str(entity.original_name or ""),
        str(entity.name or ""),
        str(getattr(entity, "original_device_class", "") or ""),
    ]
    return " ".join(parts).lower()


def _unit_of_measurement(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id) if hasattr(hass, "states") else None
    if state is None:
        return ""
    return str(state.attributes.get("unit_of_measurement") or "").strip().lower()


def _device_class(entity: er.RegistryEntry) -> str:
    raw = getattr(entity, "device_class", None) or getattr(
        entity, "original_device_class", None
    )
    return str(raw or "").lower()


def classify_local_water_sensors(
    hass: HomeAssistant,
    device_id: str,
) -> dict[str, str]:
    """Classify sensor entities on a local water device into water roles."""
    try:
        entity_registry = er.async_get(hass)
    except Exception:  # noqa: BLE001
        return {}

    candidates: list[er.RegistryEntry] = []
    for entity in entity_registry.entities.values():
        if entity.device_id != device_id:
            continue
        if entity.domain != "sensor":
            continue
        if getattr(entity, "disabled", False) or getattr(entity, "hidden", False):
            continue
        text = _entity_text(entity)
        # Never treat humidity / battery / warning config sensors as water roles.
        if "humidity" in text or "battery" in text:
            continue
        if "warning" in text or "alarm" in text:
            continue
        candidates.append(entity)

    claimed: set[str] = set()
    result: dict[str, str] = {}

    def _claim(entity: er.RegistryEntry) -> bool:
        if entity.entity_id in claimed:
            return False
        claimed.add(entity.entity_id)
        return True

    # pH
    for entity in candidates:
        if _device_class(entity) == SensorDeviceClass.PH:
            if _claim(entity):
                result[SENSOR_ROLE_PH] = entity.entity_id
                break
    if SENSOR_ROLE_PH not in result:
        for entity in candidates:
            if "ph" in _entity_text(entity) and _claim(entity):
                result[SENSOR_ROLE_PH] = entity.entity_id
                break

    # EC (unit first, then name)
    for entity in candidates:
        unit = _unit_of_measurement(hass, entity.entity_id)
        if unit in _EC_UNITS and _claim(entity):
            result[SENSOR_ROLE_EC] = entity.entity_id
            break
    if SENSOR_ROLE_EC not in result:
        for entity in candidates:
            text = _entity_text(entity)
            if ("ec" in text or "conductivity" in text) and "cf" not in text:
                if _claim(entity):
                    result[SENSOR_ROLE_EC] = entity.entity_id
                    break

    # TDS
    for entity in candidates:
        unit = _unit_of_measurement(hass, entity.entity_id)
        if unit in _TDS_UNITS and _claim(entity):
            result[SENSOR_ROLE_TDS] = entity.entity_id
            break
    if SENSOR_ROLE_TDS not in result:
        for entity in candidates:
            text = _entity_text(entity)
            if ("tds" in text or "dissolved" in text) and _claim(entity):
                result[SENSOR_ROLE_TDS] = entity.entity_id
                break

    # ORP
    for entity in candidates:
        unit = _unit_of_measurement(hass, entity.entity_id)
        if unit in _ORP_UNITS and _claim(entity):
            result[SENSOR_ROLE_ORP] = entity.entity_id
            break
    if SENSOR_ROLE_ORP not in result:
        for entity in candidates:
            text = _entity_text(entity)
            if (
                "orp" in text or "redox" in text or "oxidation" in text
            ) and _claim(entity):
                result[SENSOR_ROLE_ORP] = entity.entity_id
                break

    # CF by name only (do not steal an EC entity)
    for entity in candidates:
        text = _entity_text(entity)
        if "cf" in text and entity.entity_id not in claimed and _claim(entity):
            result[SENSOR_ROLE_CF] = entity.entity_id
            break

    # Water temperature
    temp_entities = [
        entity
        for entity in candidates
        if _device_class(entity) == SensorDeviceClass.TEMPERATURE
        or "temperature" in _entity_text(entity)
        or "temp" in _entity_text(entity)
    ]
    water_named = [
        entity for entity in temp_entities if "water" in _entity_text(entity)
    ]
    chosen: er.RegistryEntry | None = None
    if len(water_named) == 1:
        chosen = water_named[0]
    elif len(water_named) > 1:
        chosen = water_named[0]
    elif len(temp_entities) == 1:
        chosen = temp_entities[0]
    if chosen is not None and _claim(chosen):
        result[SENSOR_ROLE_WATER_TEMPERATURE] = chosen.entity_id

    return result


def apply_local_water_automap(
    hass: HomeAssistant,
    entry: ConfigEntry,
    grow_space: Any,
    auto_mapped_store: dict[str, str],
    *,
    device_id: str | None = None,
) -> dict[str, str]:
    """Auto-map unmapped water roles from the bound local device.

    Does not override existing mappings. Returns the roles newly mapped.
    """
    resolved_id = device_id
    if not resolved_id:
        stored = stored_water_monitor_device_id(entry)
        if stored:
            resolved_id = stored
        else:
            match = find_unique_local_match(hass, tuya_device_ids(entry))
            if match:
                resolved_id = match[0]

    if not resolved_id:
        return {}

    classified = classify_local_water_sensors(hass, resolved_id)
    newly: dict[str, str] = {}
    for role in SENSOR_ROLES_LOCAL_WATER_AUTOMAP:
        if grow_space.sensor_mappings.get(role):
            continue
        entity_id = classified.get(role)
        if not entity_id:
            continue
        grow_space.sensor_mappings[role] = entity_id
        auto_mapped_store[role] = entity_id
        newly[role] = entity_id
        LOGGER.info(
            "Auto-mapped TendrilGrow role %s -> %s from local device %s (%s)",
            role,
            entity_id,
            resolved_id,
            entry.entry_id,
        )
    return newly


async def async_prepare_local_water_source(
    hass: HomeAssistant,
    entry: ConfigEntry,
    grow_space: Any,
    auto_mapped_store: dict[str, str],
) -> str:
    """Resolve/bind local device, auto-map water roles, return effective source."""
    await async_resolve_water_monitor_device(hass, entry, persist=True)
    source = effective_water_source(hass, entry)
    if source in (WATER_SOURCE_LOCALTUYA, WATER_SOURCE_TUYA_LOCAL):
        apply_local_water_automap(
            hass, entry, grow_space, auto_mapped_store
        )
    return source
