"""Diagnostics support for TendrilGrow."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import SENSITIVE_KEYS


def _safe_redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return async_redact_data(dict(value), SENSITIVE_KEYS)
    if isinstance(value, list):
        return [_safe_redact(item) for item in value]
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry with secrets redacted."""
    runtime = hass.data.get("tendrilgrow", {}).get(entry.entry_id) if hass else None
    auto_mapped = {}
    effective_sensor_mappings = {}
    effective_control_mappings = {}
    ai_health = {}
    if runtime is not None:
        auto_mapped = dict(getattr(runtime, "auto_mapped_sensor_roles", {}) or {})
        grow_space = getattr(runtime, "grow_space", None)
        effective_sensor_mappings = dict(
            getattr(grow_space, "sensor_mappings", {}) or {}
        )
        effective_control_mappings = dict(
            getattr(grow_space, "control_mappings", {}) or {}
        )
        ai_state = getattr(runtime, "ai_health_state", None)
        if ai_state is not None:
            latest = ai_state.latest.to_dict() if ai_state.latest else None
            ai_health = {
                "running": bool(getattr(ai_state, "running", False)),
                "last_error": str(getattr(ai_state, "last_error", "") or ""),
                "history_count": len(getattr(ai_state, "history", []) or []),
                "latest": latest,
            }

    return {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "data": _safe_redact(entry.data),
        "options": _safe_redact(entry.options),
        "runtime": {
            "auto_mapped_sensor_roles": auto_mapped,
            "effective_sensor_mappings": effective_sensor_mappings,
            "effective_control_mappings": effective_control_mappings,
            "ai_health": _safe_redact(ai_health),
        },
    }
