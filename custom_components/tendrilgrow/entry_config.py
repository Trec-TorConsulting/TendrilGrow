"""Merged config entry helpers for TendrilGrow."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_CONTROL_MAPPINGS,
    CONF_SENSOR_MAPPINGS,
    CONF_TUYA_ACCESS_ID,
    CONF_TUYA_ACCESS_SECRET,
    CONF_TUYA_DEVICE_IDS,
    CONF_TUYA_ENABLED,
    CONF_WATER_MONITOR_DEVICE_ID,
    CONTROL_ROLES,
    PUMP_CONTROL_ROLES,
    PUMP_POWER_ROLE_FOR,
    SENSOR_ROLE_EC_TDS_LEGACY,
    SENSOR_ROLE_TDS,
    SENSOR_ROLES_CONFIGURABLE,
    SENSOR_ROLES_TUYA_OPTIONAL,
)


def normalize_sensor_mappings(sensor_mappings: dict[str, str]) -> dict[str, str]:
    normalized = dict(sensor_mappings)
    if SENSOR_ROLE_EC_TDS_LEGACY in normalized and SENSOR_ROLE_TDS not in normalized:
        normalized[SENSOR_ROLE_TDS] = normalized[SENSOR_ROLE_EC_TDS_LEGACY]
    return normalized


def entry_merged_config(entry: ConfigEntry) -> dict[str, Any]:
    """Return entry.data overlaid by entry.options."""
    merged = dict(entry.data)
    merged.update(getattr(entry, "options", {}) or {})
    return merged


def hide_water_quality_fields(tuya_enabled: bool, local_device_id: str) -> bool:
    """Hide water roles only for cloud fallback with no local device bound."""
    return bool(tuya_enabled) and not bool(local_device_id)


def options_visible_sensor_roles(merged_config: dict[str, Any]) -> list[str]:
    """Sensor roles shown on the options form for the current config."""
    tuya_enabled = bool(merged_config.get(CONF_TUYA_ENABLED, False))
    local_device_id = str(merged_config.get(CONF_WATER_MONITOR_DEVICE_ID, "") or "")
    hide_water = hide_water_quality_fields(tuya_enabled, local_device_id)
    return (
        list(SENSOR_ROLES_CONFIGURABLE)
        if not hide_water
        else list(SENSOR_ROLES_TUYA_OPTIONAL)
    )


def merge_mappings_from_options_input(
    merged_config: dict[str, Any],
    user_input: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    """Deep-merge sensor and control mappings from an options form submission.

    Roles not displayed on the form are preserved. Roles on the form update when
    the user selects an entity and are removed when the user clears the field.
    """
    sensor_mappings = normalize_sensor_mappings(
        dict(merged_config.get(CONF_SENSOR_MAPPINGS, {}))
    )
    control_mappings = dict(merged_config.get(CONF_CONTROL_MAPPINGS, {}))

    visible_sensor_roles = options_visible_sensor_roles(merged_config)

    for role in visible_sensor_roles:
        if role not in user_input:
            continue
        value = user_input.get(role)
        if value:
            sensor_mappings[role] = str(value)
        else:
            sensor_mappings.pop(role, None)

    for pump_role in PUMP_CONTROL_ROLES:
        power_role = PUMP_POWER_ROLE_FOR.get(pump_role)
        if not power_role or power_role not in user_input:
            continue
        value = user_input.get(power_role)
        if value:
            sensor_mappings[power_role] = str(value)
        else:
            sensor_mappings.pop(power_role, None)

    for role in CONTROL_ROLES:
        if role not in user_input:
            continue
        value = user_input.get(role)
        if value:
            control_mappings[role] = str(value)
        else:
            control_mappings.pop(role, None)

    return normalize_sensor_mappings(sensor_mappings), control_mappings


def preserve_blank_str(user_input: dict[str, Any], key: str, stored: str) -> str:
    """Blank or omitted form values keep the stored string."""
    if key not in user_input:
        return str(stored or "").strip()
    raw = user_input.get(key)
    if raw is None:
        return str(stored or "").strip()
    submitted = str(raw).strip()
    return submitted if submitted else str(stored or "").strip()


def preserve_blank_tuya_device_ids(
    user_input: dict[str, Any],
    stored: list[str] | str,
) -> list[str]:
    """Blank device-id field keeps the stored list."""
    if CONF_TUYA_DEVICE_IDS not in user_input:
        if isinstance(stored, str):
            return [part.strip() for part in stored.split(",") if part.strip()]
        return [str(part).strip() for part in stored if str(part).strip()]
    raw = str(user_input.get(CONF_TUYA_DEVICE_IDS, "") or "").strip()
    if not raw:
        if isinstance(stored, str):
            return [part.strip() for part in stored.split(",") if part.strip()]
        return [str(part).strip() for part in stored if str(part).strip()]
    return [device_id.strip() for device_id in raw.split(",") if device_id.strip()]


def water_monitor_device_id_from_input(
    user_input: dict[str, Any],
    stored: str,
) -> str:
    """Resolve water-monitor device id; blank submission keeps the stored id."""
    return preserve_blank_str(user_input, CONF_WATER_MONITOR_DEVICE_ID, stored)


def tuya_enabled_from_input(user_input: dict[str, Any], default: bool = False) -> bool:
    return bool(user_input.get(CONF_TUYA_ENABLED, default))


def resolved_tuya_access_id(user_input: dict[str, Any], stored: str) -> str:
    return preserve_blank_str(user_input, CONF_TUYA_ACCESS_ID, stored)


def resolved_tuya_access_secret(user_input: dict[str, Any], stored: str) -> str:
    return preserve_blank_str(user_input, CONF_TUYA_ACCESS_SECRET, stored)
