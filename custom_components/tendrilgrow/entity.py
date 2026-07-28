"""Shared entity helpers for TendrilGrow."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


def grow_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return a shared device for grouping a grow space's context entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_grow_space")},
        name=entry.title,
        manufacturer="TendrilGrow",
        model="Grow Space",
    )
