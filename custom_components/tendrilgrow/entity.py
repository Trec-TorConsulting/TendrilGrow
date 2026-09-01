"""Shared entity helpers for TendrilGrow."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify

from .const import CTX_STAGE, DOMAIN


def grow_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return a shared device for grouping a grow space's context entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_grow_space")},
        name=entry.title,
        manufacturer="TendrilGrow",
        model="Grow Space",
    )


def prefix_from_entity_id(entity_id: str, name_suffix: str) -> str | None:
    """Return the grow-space object-id prefix from a known entity id."""
    if "." not in entity_id:
        return None
    obj = entity_id.split(".", 1)[1]
    tail = f"_{name_suffix}"
    if obj.endswith(tail) and len(obj) > len(tail):
        return obj[: -len(tail)]
    return None


def grow_object_id_prefix(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """Return the object-id prefix already used by this grow space's helpers.

    Cultivation Plan cards are hardcoded to ids like ``select.clone_growth_stage``.
    New date/week entities must reuse that prefix, not a later device rename
    (``basement_clone``) or a generic ``stage_started`` id.
    """
    try:
        registry = er.async_get(hass)
    except Exception:  # noqa: BLE001
        registry = None
    if registry is not None:
        stage_id = registry.async_get_entity_id(
            "select", DOMAIN, f"{entry.entry_id}_{CTX_STAGE}"
        )
        if stage_id:
            prefix = prefix_from_entity_id(stage_id, "growth_stage")
            if prefix:
                return prefix

    runtime = None
    try:
        runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    except Exception:  # noqa: BLE001
        runtime = None
    saved = getattr(runtime, "grow_object_prefix", None)
    if saved:
        return str(saved)

    return slugify(getattr(entry, "title", "") or "") or "grow"


def assign_prefixed_entity_id(
    entity: object,
    hass: HomeAssistant,
    entry: ConfigEntry,
    domain: str,
    name_suffix: str,
) -> None:
    """Pin a first-time entity_id to ``{domain}.{prefix}_{name_suffix}``."""
    prefix = grow_object_id_prefix(hass, entry)
    if not prefix:
        return
    setattr(entity, "entity_id", f"{domain}.{prefix}_{name_suffix}")
