"""Tests for TendrilGrow repair-issue evaluation."""

from __future__ import annotations

from custom_components.tendrilgrow.repairs import (
    ISSUE_AI_NO_CAMERA,
    ISSUE_AI_NO_MODEL,
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
