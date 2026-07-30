"""Repair issues surfaced for common TendrilGrow misconfigurations."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import (
    CONF_AI_MODEL,
    CONF_AI_PROVIDER,
    DOMAIN,
    PROVIDER_NONE,
    SENSOR_ROLE_CAMERA,
)

_DOCS_URL = "https://trec-torconsulting.github.io/TendrilGrow/troubleshooting/"

ISSUE_AI_NO_CAMERA = "ai_no_camera"
ISSUE_AI_NO_MODEL = "ai_no_model"
ISSUE_TIMELAPSE_NOT_ALLOWLISTED = "timelapse_not_allowlisted"
_ALL_ISSUES = (
    ISSUE_AI_NO_CAMERA,
    ISSUE_AI_NO_MODEL,
    ISSUE_TIMELAPSE_NOT_ALLOWLISTED,
)


def _issue_id(entry_id: str, key: str) -> str:
    return f"{key}_{entry_id}"


def evaluate_config_issues(
    provider: str | None, model: str | None, camera: str | None
) -> dict[str, bool]:
    """Return which repair issues are active for the given AI configuration."""
    ai_configured = bool(provider) and provider != PROVIDER_NONE
    return {
        ISSUE_AI_NO_CAMERA: ai_configured and not camera,
        ISSUE_AI_NO_MODEL: ai_configured and not model,
    }


@callback
def async_evaluate_repair_issues(
    hass: HomeAssistant,
    entry: ConfigEntry,
    merged_config: dict[str, Any],
    grow_space: Any,
) -> None:
    """Create or clear repair issues based on the entry configuration."""
    provider = merged_config.get(CONF_AI_PROVIDER) or PROVIDER_NONE
    model = merged_config.get(CONF_AI_MODEL)
    camera = None
    if grow_space is not None:
        camera = grow_space.sensor_mappings.get(SENSOR_ROLE_CAMERA)

    for key, active in evaluate_config_issues(provider, model, camera).items():
        if active:
            ir.async_create_issue(
                hass,
                DOMAIN,
                _issue_id(entry.entry_id, key),
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=key,
                translation_placeholders={"grow_space": entry.title},
                learn_more_url=_DOCS_URL,
            )
        else:
            ir.async_delete_issue(hass, DOMAIN, _issue_id(entry.entry_id, key))


@callback
def async_clear_repair_issues(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete all TendrilGrow repair issues for an entry (on unload)."""
    for key in _ALL_ISSUES:
        ir.async_delete_issue(hass, DOMAIN, _issue_id(entry.entry_id, key))


@callback
def async_raise_timelapse_allowlist_issue(
    hass: HomeAssistant,
    entry: ConfigEntry,
    capture_path: str,
) -> None:
    """Create/refresh a timelapse repair issue with the required allow-list path."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        _issue_id(entry.entry_id, ISSUE_TIMELAPSE_NOT_ALLOWLISTED),
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_TIMELAPSE_NOT_ALLOWLISTED,
        translation_placeholders={
            "grow_space": entry.title,
            "path": capture_path,
        },
        learn_more_url=_DOCS_URL,
    )


@callback
def async_clear_timelapse_allowlist_issue(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Clear the timelapse allow-list repair issue for an entry."""
    ir.async_delete_issue(
        hass,
        DOMAIN,
        _issue_id(entry.entry_id, ISSUE_TIMELAPSE_NOT_ALLOWLISTED),
    )
