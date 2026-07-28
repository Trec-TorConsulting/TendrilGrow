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
    _ = hass
    return {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "data": _safe_redact(entry.data),
        "options": _safe_redact(entry.options),
    }
