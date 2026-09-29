"""Home Assistant service handlers and mobile notification listener for TendrilGrow."""

from __future__ import annotations

import logging
import sys
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, PUMP_CONTROL_ROLES
from .flush import async_record_flush

LOGGER = logging.getLogger(__name__)

SERVICE_REBUILD_AUTOMAP = "rebuild_automap"
SERVICE_RUN_AI_HEALTH_CHECK = "run_ai_health_check"
SERVICE_SET_PUMP = "set_pump"
SERVICE_MARK_FLUSH = "mark_flush"
SERVICE_CAPTURE_TIMELAPSE_FRAME = "capture_timelapse_frame"
SERVICE_BUILD_TIMELAPSE = "build_timelapse"

ATTR_ENTRY_ID = "entry_id"
ATTR_REASON = "reason"
ATTR_PUMP = "pump"
ATTR_ACTION = "action"
_SERVICES_REGISTERED_KEY = "_services_registered"


def _get_runner(name: str):
    mod = sys.modules.get("custom_components.tendrilgrow")
    if mod and hasattr(mod, name):
        return getattr(mod, name)
    raise RuntimeError(f"Cannot resolve {name} from custom_components.tendrilgrow")


def _parse_mobile_action(action: str) -> tuple[str, str] | None:
    """Parse a TendrilGrow mobile-notification action into (verb, entry_id)."""
    prefix = "TENDRILGROW_"
    if not action.startswith(prefix) or ":" not in action:
        return None
    verb, entry_id = action[len(prefix) :].split(":", 1)
    if not verb or not entry_id:
        return None
    return verb, entry_id


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register all TendrilGrow integration services and notification listeners."""

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
                raise HomeAssistantError(
                    f"TendrilGrow entry not loaded: {requested_entry_id}"
                )
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

    async def _async_handle_run_ai_health_check(call: ServiceCall) -> None:
        requested_entry_id = str(call.data.get(ATTR_ENTRY_ID, "")).strip()
        reason = str(call.data.get(ATTR_REASON, "manual")).strip() or "manual"
        loaded_entries = [
            entry_id
            for entry_id in hass.data.get(DOMAIN, {})
            if not str(entry_id).startswith("_")
        ]

        if requested_entry_id:
            if requested_entry_id not in loaded_entries:
                raise HomeAssistantError(
                    f"TendrilGrow entry not loaded: {requested_entry_id}"
                )
            target_entries = [requested_entry_id]
        else:
            target_entries = loaded_entries

        for entry_id in target_entries:
            entry = None
            if hasattr(hass.config_entries, "async_get_entry"):
                entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None:
                entry = next(
                    (
                        loaded
                        for loaded in getattr(
                            hass.config_entries, "async_entries", lambda _domain: []
                        )(DOMAIN)
                        if loaded.entry_id == entry_id
                    ),
                    None,
                )
            if entry is None:
                continue
            await _get_runner("_async_run_ai_health_check")(hass, entry, reason=reason)

        LOGGER.info(
            "Ran TendrilGrow AI health checks for %d entr%s",
            len(target_entries),
            "y" if len(target_entries) == 1 else "ies",
        )

    async def _async_handle_set_pump(call: ServiceCall) -> None:
        entry_id = str(call.data.get(ATTR_ENTRY_ID, "")).strip()
        pump = str(call.data.get(ATTR_PUMP, "")).strip()
        action = str(call.data.get(ATTR_ACTION, "")).strip().lower()

        if not entry_id:
            raise HomeAssistantError("entry_id is required")
        if not pump:
            raise HomeAssistantError("pump is required")
        if action not in ("on", "off", "toggle"):
            raise HomeAssistantError(
                f"action must be 'on', 'off', or 'toggle', got '{action}'"
            )

        loaded_entries = [
            entry_id_item
            for entry_id_item in hass.data.get(DOMAIN, {})
            if not str(entry_id_item).startswith("_")
        ]

        if entry_id not in loaded_entries:
            raise HomeAssistantError(f"TendrilGrow entry not loaded: {entry_id}")

        runtime = hass.data.get(DOMAIN, {}).get(entry_id)
        if runtime is None:
            raise HomeAssistantError(f"TendrilGrow entry not loaded: {entry_id}")

        if pump not in PUMP_CONTROL_ROLES:
            raise HomeAssistantError(
                f"pump must be one of {PUMP_CONTROL_ROLES}, got '{pump}'"
            )

        grow_space = runtime.grow_space
        mapped_entity_id = grow_space.control_mappings.get(pump)

        if not mapped_entity_id:
            LOGGER.warning(
                "Skipping set_pump for entry %s pump %s: pump role not mapped",
                entry_id,
                pump,
            )
            return

        state = hass.states.get(mapped_entity_id)
        if state is None:
            LOGGER.warning(
                "Skipping set_pump for entry %s pump %s: entity %s not found",
                entry_id,
                pump,
                mapped_entity_id,
            )
            return

        if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            LOGGER.warning(
                "Skipping set_pump for entry %s pump %s: entity %s is %s",
                entry_id,
                pump,
                mapped_entity_id,
                state.state,
            )
            return

        # Determine the domain and action
        domain = mapped_entity_id.split(".")[0]
        action_name = action if action == "toggle" else f"turn_{action}"

        if domain not in ("switch", "input_boolean"):
            LOGGER.warning(
                "Skipping set_pump for entry %s pump %s: unsupported domain %s",
                entry_id,
                pump,
                domain,
            )
            return

        try:
            await hass.services.async_call(
                domain,
                action_name,
                {"entity_id": mapped_entity_id},
            )
            LOGGER.info(
                "Set pump %s (%s) to %s for entry %s",
                pump,
                mapped_entity_id,
                action,
                entry_id,
            )
        except Exception as err:  # noqa: BLE001
            LOGGER.error(
                "Failed to set pump %s (%s) to %s for entry %s: %s",
                pump,
                mapped_entity_id,
                action,
                entry_id,
                err,
            )
            raise HomeAssistantError(
                f"Failed to set pump {pump} ({mapped_entity_id}) to {action}: {err}"
            ) from err

    async def _async_handle_mark_flush(call: ServiceCall) -> None:
        entry_id = str(call.data.get(ATTR_ENTRY_ID, "")).strip()
        if not entry_id:
            raise HomeAssistantError("entry_id is required")

        runtime = hass.data.get(DOMAIN, {}).get(entry_id)
        if runtime is None or str(entry_id).startswith("_"):
            raise HomeAssistantError(f"TendrilGrow entry not loaded: {entry_id}")

        entry = None
        if hasattr(hass.config_entries, "async_get_entry"):
            entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            entry = next(
                (
                    loaded
                    for loaded in getattr(
                        hass.config_entries, "async_entries", lambda _domain: []
                    )(DOMAIN)
                    if loaded.entry_id == entry_id
                ),
                None,
            )
        if entry is None:
            raise HomeAssistantError(f"TendrilGrow entry not found: {entry_id}")

        await async_record_flush(hass, entry, runtime)
        LOGGER.info("Recorded reservoir flush via service for entry %s", entry_id)

    async def _async_handle_capture_timelapse_frame(call: ServiceCall) -> None:
        requested_entry_id = str(call.data.get(ATTR_ENTRY_ID, "")).strip()
        loaded_entries = [
            entry_id
            for entry_id in hass.data.get(DOMAIN, {})
            if not str(entry_id).startswith("_")
        ]

        if requested_entry_id:
            if requested_entry_id not in loaded_entries:
                raise HomeAssistantError(
                    f"TendrilGrow entry not loaded: {requested_entry_id}"
                )
            target_entries = [requested_entry_id]
        else:
            target_entries = loaded_entries

        for entry_id in target_entries:
            entry = None
            if hasattr(hass.config_entries, "async_get_entry"):
                entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None:
                entry = next(
                    (
                        loaded
                        for loaded in getattr(
                            hass.config_entries, "async_entries", lambda _domain: []
                        )(DOMAIN)
                        if loaded.entry_id == entry_id
                    ),
                    None,
                )
            if entry is None:
                continue
            await _get_runner("_async_capture_timelapse_frame")(
                hass,
                entry,
                reason="manual_service",
            )

    async def _async_handle_build_timelapse(call: ServiceCall) -> None:
        entry_id = str(call.data.get(ATTR_ENTRY_ID, "")).strip()
        if not entry_id:
            raise HomeAssistantError("entry_id is required")

        if entry_id not in hass.data.get(DOMAIN, {}):
            raise HomeAssistantError(f"TendrilGrow entry not loaded: {entry_id}")

        entry = None
        if hasattr(hass.config_entries, "async_get_entry"):
            entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            entry = next(
                (
                    loaded
                    for loaded in getattr(
                        hass.config_entries, "async_entries", lambda _domain: []
                    )(DOMAIN)
                    if loaded.entry_id == entry_id
                ),
                None,
            )
        if entry is None:
            raise HomeAssistantError(f"TendrilGrow entry not found: {entry_id}")

        await _get_runner("_async_build_timelapse")(hass, entry)

    hass.services.async_register(
        DOMAIN, SERVICE_REBUILD_AUTOMAP, _async_handle_rebuild_automap
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RUN_AI_HEALTH_CHECK,
        _async_handle_run_ai_health_check,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PUMP,
        _async_handle_set_pump,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MARK_FLUSH,
        _async_handle_mark_flush,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CAPTURE_TIMELAPSE_FRAME,
        _async_handle_capture_timelapse_frame,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_BUILD_TIMELAPSE,
        _async_handle_build_timelapse,
    )

    async def _async_handle_mobile_action(event: Any) -> None:
        parsed = _parse_mobile_action(str(event.data.get("action", "")))
        if parsed is None:
            return
        verb, entry_id = parsed
        if verb == "MARK_FLUSH":
            await hass.services.async_call(
                DOMAIN, SERVICE_MARK_FLUSH, {ATTR_ENTRY_ID: entry_id}, blocking=False
            )
        elif verb == "RUN_CHECK":
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RUN_AI_HEALTH_CHECK,
                {ATTR_ENTRY_ID: entry_id},
                blocking=False,
            )

    try:
        domain_data["_mobile_action_unsub"] = hass.bus.async_listen(
            "mobile_app_notification_action", _async_handle_mobile_action
        )
    except Exception:  # noqa: BLE001
        LOGGER.debug("Unable to register mobile action listener", exc_info=True)

    domain_data[_SERVICES_REGISTERED_KEY] = True


async def _async_maybe_unregister_services(hass: HomeAssistant) -> None:
    """Unregister TendrilGrow integration services when all entries are unloaded."""
    if not hasattr(hass, "services"):
        return

    domain_data = hass.data.get(DOMAIN, {})
    if not domain_data.get(_SERVICES_REGISTERED_KEY):
        return

    has_loaded_entries = any(not str(key).startswith("_") for key in domain_data)
    if has_loaded_entries:
        return

    hass.services.async_remove(DOMAIN, SERVICE_REBUILD_AUTOMAP)
    hass.services.async_remove(DOMAIN, SERVICE_RUN_AI_HEALTH_CHECK)
    hass.services.async_remove(DOMAIN, SERVICE_SET_PUMP)
    hass.services.async_remove(DOMAIN, SERVICE_MARK_FLUSH)
    hass.services.async_remove(DOMAIN, SERVICE_CAPTURE_TIMELAPSE_FRAME)
    hass.services.async_remove(DOMAIN, SERVICE_BUILD_TIMELAPSE)
    unsub = domain_data.pop("_mobile_action_unsub", None)
    if unsub:
        try:
            unsub()
        except Exception:  # noqa: BLE001
            LOGGER.debug("Unable to remove mobile action listener", exc_info=True)
    domain_data[_SERVICES_REGISTERED_KEY] = False
