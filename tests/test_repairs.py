"""Tests for TendrilGrow repair-issue evaluation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from custom_components.tendrilgrow.repairs import (
    ISSUE_AI_NO_CAMERA,
    ISSUE_AI_NO_MODEL,
    ISSUE_RETIRED_STAGE_CLOCK,
    ISSUE_TIMELAPSE_NOT_ALLOWLISTED,
    async_clear_retired_stage_clock_issue,
    async_clear_timelapse_allowlist_issue,
    async_raise_retired_stage_clock_issue,
    async_raise_timelapse_allowlist_issue,
    evaluate_config_issues,
)


def test_no_issues_when_ai_disabled() -> None:
    result = evaluate_config_issues("none", None, None)
    assert result[ISSUE_AI_NO_CAMERA] is False
    assert result[ISSUE_AI_NO_MODEL] is False


def test_both_issues_when_ai_configured_without_camera_or_model() -> None:
    result = evaluate_config_issues("gemini", None, None)
    assert result[ISSUE_AI_NO_CAMERA] is True
    assert result[ISSUE_AI_NO_MODEL] is True


def test_no_issues_when_fully_configured() -> None:
    result = evaluate_config_issues("openai", "gpt-4o", "camera.tent")
    assert result[ISSUE_AI_NO_CAMERA] is False
    assert result[ISSUE_AI_NO_MODEL] is False


def test_model_issue_only_when_camera_set_but_no_model() -> None:
    result = evaluate_config_issues("ollama", None, "camera.tent")
    assert result[ISSUE_AI_NO_CAMERA] is False
    assert result[ISSUE_AI_NO_MODEL] is True


def test_timelapse_allowlist_issue_create_and_clear(monkeypatch) -> None:
    create_issue = Mock()
    delete_issue = Mock()

    from custom_components.tendrilgrow import repairs as repairs_module

    monkeypatch.setattr(repairs_module.ir, "async_create_issue", create_issue)
    monkeypatch.setattr(repairs_module.ir, "async_delete_issue", delete_issue)

    hass = SimpleNamespace()
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A")

    async_raise_timelapse_allowlist_issue(hass, entry, "/config/www/tendrilgrow")
    create_issue.assert_called_once()
    kwargs = create_issue.call_args.kwargs
    assert kwargs["translation_key"] == ISSUE_TIMELAPSE_NOT_ALLOWLISTED
    assert kwargs["translation_placeholders"]["path"] == "/config/www/tendrilgrow"

    async_clear_timelapse_allowlist_issue(hass, entry)
    delete_issue.assert_called_once()


def test_retired_stage_clock_issue_create_and_clear(monkeypatch) -> None:
    create_issue = Mock()
    delete_issue = Mock()

    from custom_components.tendrilgrow import repairs as repairs_module

    monkeypatch.setattr(repairs_module.ir, "async_create_issue", create_issue)
    monkeypatch.setattr(repairs_module.ir, "async_delete_issue", delete_issue)

    hass = SimpleNamespace()
    async_raise_retired_stage_clock_issue(
        hass,
        issue_id="retired_stage_clock_number.tent_week_in_stage",
        retired_entity="number.tent_week_in_stage",
        replacement_entity="sensor.tent_week_in_stage",
    )
    create_issue.assert_called_once()
    kwargs = create_issue.call_args.kwargs
    assert kwargs["translation_key"] == ISSUE_RETIRED_STAGE_CLOCK
    assert (
        kwargs["translation_placeholders"]["retired_entity"]
        == "number.tent_week_in_stage"
    )
    assert (
        kwargs["translation_placeholders"]["replacement_entity"]
        == "sensor.tent_week_in_stage"
    )

    async_clear_retired_stage_clock_issue(
        hass, issue_id="retired_stage_clock_number.tent_week_in_stage"
    )
    delete_issue.assert_called_once()
