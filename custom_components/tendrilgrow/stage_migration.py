"""Entity ID and Lovelace migration helpers for TendrilGrow."""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import CTX_STAGE_STARTED, CTX_WEEK_IN_STAGE, DOMAIN
from .entity import grow_object_id_prefix, prefix_from_entity_id
from .repairs import (
    async_clear_retired_stage_clock_issue,
    async_raise_retired_stage_clock_issue,
)

LOGGER = logging.getLogger(__name__)

# Legacy AI health entities were created without a device, so Home Assistant
# generated global ids (e.g. sensor.ai_health_score, and _2 for a second entry).
# (domain, unique_id suffix, per-device object-id suffix == entity name slug).
_AI_ENTITY_IDS: tuple[tuple[str, str, str], ...] = (
    ("sensor", "ai_health_score", "ai_health_score"),
    ("sensor", "ai_health_summary", "ai_health_summary"),
    ("sensor", "ai_feeding_schedule", "ai_feeding_schedule"),
    ("sensor", "ai_health_last_check", "ai_last_health_check"),
    ("binary_sensor", "ai_health_critical_alert", "ai_health_critical_alert"),
    ("button", "run_ai_health_check", "run_ai_health_check"),
)

_STAGE_CLOCK_ENTITY_IDS: tuple[tuple[str, str, str], ...] = (
    ("date", CTX_STAGE_STARTED, "stage_started"),
    ("sensor", CTX_WEEK_IN_STAGE, "week_in_stage"),
)


def _migrate_ai_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Rename legacy generic AI entity ids to per-grow-space ids.

    Now that the AI health entities are attached to the grow-space device, an
    auto-generated global id such as ``sensor.ai_health_score`` (or ``_2`` for a
    second entry) is migrated to ``<domain>.<grow_slug>_<name>``. Ids the user
    has customized are left untouched, and an already-migrated id is a no-op.
    """
    slug = slugify(getattr(entry, "title", "") or "")
    if not slug:
        return
    try:
        registry = er.async_get(hass)
    except Exception:  # noqa: BLE001
        return

    for domain, uid_suffix, obj_suffix in _AI_ENTITY_IDS:
        unique_id = f"{entry.entry_id}_{uid_suffix}"
        current = registry.async_get_entity_id(domain, DOMAIN, unique_id)
        if not current:
            continue
        desired = f"{domain}.{slug}_{obj_suffix}"
        if current == desired:
            continue
        current_object = current.split(".", 1)[1]
        # Only migrate auto-generated ids ("<name>" or "<name>_<n>").
        if current_object != obj_suffix and not re.fullmatch(
            rf"{re.escape(obj_suffix)}_\d+", current_object
        ):
            continue
        if registry.async_get(desired) is not None:
            continue
        try:
            registry.async_update_entity(current, new_entity_id=desired)
            LOGGER.info(
                "Migrated AI entity %s -> %s for %s",
                current,
                desired,
                entry.entry_id,
            )
        except (ValueError, KeyError):
            LOGGER.debug("Could not migrate %s -> %s", current, desired, exc_info=True)


def _seed_stage_started_from_week_number(
    hass: HomeAssistant, entry: ConfigEntry
) -> date | None:
    """Backdate Stage Started from the retired Week In Stage number.

    Week 2 becomes about 14 days ago. The leftover number entity is removed
    so it does not linger unavailable after the date entity takes over.
    """
    try:
        registry = er.async_get(hass)
    except Exception:  # noqa: BLE001
        return None
    week_id = registry.async_get_entity_id(
        "number", DOMAIN, f"{entry.entry_id}_{CTX_WEEK_IN_STAGE}"
    )
    if not week_id:
        return None
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    prefix = prefix_from_entity_id(week_id, "week_in_stage")
    if runtime is not None:
        runtime.legacy_week_entity_id = week_id
        if prefix:
            runtime.grow_object_prefix = prefix
    week_state = None
    current = hass.states.get(week_id)
    if current is not None and current.state not in (
        None,
        "",
        STATE_UNKNOWN,
        STATE_UNAVAILABLE,
    ):
        week_state = current.state
    if week_state is None:
        try:
            from homeassistant.helpers.restore_state import (
                async_get as async_get_restore,
            )

            stored = async_get_restore(hass).last_states.get(week_id)
            if stored is not None and stored.state.state not in (
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
                "",
            ):
                week_state = stored.state.state
        except Exception:  # noqa: BLE001
            week_state = None
    try:
        registry.async_remove(week_id)
    except Exception:  # noqa: BLE001
        LOGGER.debug("Could not remove legacy week-in-stage number %s", week_id)
    if week_state is None:
        return None
    try:
        weeks = float(week_state)
    except (TypeError, ValueError):
        return None
    return dt_util.now().date() - timedelta(days=max(0, int(round(weeks * 7))))


def _migrate_stage_clock_entity_ids(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, str]:
    """Rename Stage Started / Week In Stage ids to match Cultivation Plan cards.

    First-load ids are often ``date.stage_started`` / ``date.stage_started_2``
    because the device is not attached yet. Dashboards use
    ``date.<grow_prefix>_stage_started`` like the Growth Stage select.
    """
    renamed: dict[str, str] = {}
    prefix = grow_object_id_prefix(hass, entry)
    if not prefix:
        return renamed
    try:
        registry = er.async_get(hass)
    except Exception:  # noqa: BLE001
        return renamed

    for domain, uid_suffix, obj_suffix in _STAGE_CLOCK_ENTITY_IDS:
        unique_id = f"{entry.entry_id}_{uid_suffix}"
        current = registry.async_get_entity_id(domain, DOMAIN, unique_id)
        if not current:
            continue
        desired = f"{domain}.{prefix}_{obj_suffix}"
        renamed[current] = desired
        if current == desired:
            continue
        current_object = current.split(".", 1)[1]
        generic = current_object == obj_suffix or bool(
            re.fullmatch(rf"{re.escape(obj_suffix)}_\d+", current_object)
        )
        device_prefixed = current_object.endswith(f"_{obj_suffix}")
        if not generic and not device_prefixed:
            continue
        if registry.async_get(desired) is not None:
            continue
        try:
            registry.async_update_entity(current, new_entity_id=desired)
            LOGGER.info(
                "Migrated stage-clock entity %s -> %s for %s",
                current,
                desired,
                entry.entry_id,
            )
        except (ValueError, KeyError):
            LOGGER.debug("Could not migrate %s -> %s", current, desired, exc_info=True)
    return renamed


def rewrite_lovelace_stage_clock(
    config: Any,
    list_replacements: dict[str, list[str]],
    string_replacements: dict[str, str],
) -> tuple[Any, bool]:
    """Swap retired week-in-stage number ids for Stage Started + Week In Stage."""
    ordered_strings = sorted(string_replacements, key=len, reverse=True)

    def _swap_text(value: str) -> tuple[str, bool]:
        updated = value
        for old in ordered_strings:
            updated = updated.replace(old, string_replacements[old])
        return updated, updated != value

    def _entity_id_of(item: Any) -> str | None:
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            entity = item.get("entity")
            if isinstance(entity, str):
                return entity
        return None

    def _walk(value: Any) -> tuple[Any, bool]:
        if isinstance(value, dict):
            changed = False
            out: dict[Any, Any] = {}
            for key, child in value.items():
                if key == "entities" and isinstance(child, list):
                    rewritten, child_changed = _rewrite_entities(child)
                else:
                    rewritten, child_changed = _walk(child)
                out[key] = rewritten
                changed = changed or child_changed
            return out, changed
        if isinstance(value, list):
            changed = False
            out_list = []
            for child in value:
                rewritten, child_changed = _walk(child)
                out_list.append(rewritten)
                changed = changed or child_changed
            return out_list, changed
        if isinstance(value, str):
            return _swap_text(value)
        return value, False

    def _rewrite_entities(rows: list[Any]) -> tuple[list[Any], bool]:
        present: set[str] = set()
        for item in rows:
            eid = _entity_id_of(item)
            if eid:
                present.add(eid)
        out: list[Any] = []
        changed = False
        for item in rows:
            eid = _entity_id_of(item)
            replacements = list_replacements.get(eid or "")
            if replacements:
                changed = True
                for new_id in replacements:
                    if new_id in present:
                        continue
                    out.append(new_id)
                    present.add(new_id)
                continue
            rewritten, child_changed = _walk(item)
            new_eid = _entity_id_of(rewritten)
            if new_eid and new_eid in present and new_eid != eid:
                changed = True
                continue
            out.append(rewritten)
            changed = changed or child_changed
        return out, changed

    return _walk(config)


def _stage_clock_lovelace_replacements(
    hass: HomeAssistant,
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Map retired/guessed Cultivation Plan ids to the live registry ids."""
    list_replacements: dict[str, list[str]] = {}
    string_replacements: dict[str, str] = {}
    try:
        registry = er.async_get(hass)
        entries = hass.config_entries.async_entries(DOMAIN)
    except Exception:  # noqa: BLE001
        return list_replacements, string_replacements

    for entry in entries:
        prefix = grow_object_id_prefix(hass, entry)
        date_id = registry.async_get_entity_id(
            "date", DOMAIN, f"{entry.entry_id}_{CTX_STAGE_STARTED}"
        )
        sensor_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{CTX_WEEK_IN_STAGE}"
        )
        runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        legacy = getattr(runtime, "legacy_week_entity_id", None)
        old_number = legacy or (f"number.{prefix}_week_in_stage" if prefix else None)
        replacements = [eid for eid in (date_id, sensor_id) if eid]
        if old_number and replacements:
            list_replacements[old_number] = replacements
            string_replacements[old_number] = sensor_id or date_id or old_number
        if prefix and date_id:
            guessed = f"date.{prefix}_stage_started"
            if guessed != date_id:
                string_replacements[guessed] = date_id
                list_replacements[guessed] = [date_id]
        if prefix and sensor_id:
            guessed = f"sensor.{prefix}_week_in_stage"
            if guessed != sensor_id:
                string_replacements[guessed] = sensor_id
                list_replacements[guessed] = [sensor_id]
    return list_replacements, string_replacements


def find_stale_stage_clock_references(
    config: Any,
    stale_entities: set[str] | dict[str, Any],
) -> set[str]:
    """Find all retired stage-clock entity ids present in Lovelace config."""
    found: set[str] = set()
    targets = set(stale_entities)
    if not targets:
        return found

    def _search(item: Any) -> None:
        if isinstance(item, str):
            for old_id in targets:
                if old_id in item:
                    found.add(old_id)
        elif isinstance(item, dict):
            for val in item.values():
                _search(val)
        elif isinstance(item, list):
            for val in item:
                _search(val)

    _search(config)
    return found


async def _async_scan_lovelace_stage_clock_repairs(hass: HomeAssistant) -> None:
    """Scan storage dashboards for retired stage-clock references and manage repairs."""
    lovelace = hass.data.get("lovelace")
    dashboards = getattr(lovelace, "dashboards", None)
    if dashboards is None and isinstance(lovelace, dict):
        dashboards = lovelace.get("dashboards")
    if not isinstance(dashboards, dict) or not dashboards:
        return
    _list_replacements, string_replacements = _stage_clock_lovelace_replacements(hass)
    if not string_replacements:
        return

    found_stale: dict[str, str] = {}
    scanned_any = False

    for url_path, dash in dashboards.items():
        if dash is None:
            continue
        config = getattr(dash, "config", None)
        if config is None and hasattr(dash, "async_load"):
            try:
                config = await dash.async_load(False)
            except Exception:  # noqa: BLE001
                LOGGER.debug(
                    "Could not load Lovelace dashboard %s for repair scan",
                    url_path,
                    exc_info=True,
                )
                continue
        if config is None:
            continue

        scanned_any = True
        stale_in_dash = find_stale_stage_clock_references(config, string_replacements)
        for old_id in stale_in_dash:
            found_stale[old_id] = string_replacements[old_id]

    if not scanned_any:
        return

    for old_id, new_id in string_replacements.items():
        issue_id = f"retired_stage_clock_{old_id}"
        if old_id in found_stale:
            async_raise_retired_stage_clock_issue(
                hass,
                issue_id=issue_id,
                retired_entity=old_id,
                replacement_entity=new_id,
            )
        else:
            async_clear_retired_stage_clock_issue(hass, issue_id=issue_id)
