"""Tests for mobile notification action parsing."""

from __future__ import annotations

from custom_components.tendrilgrow import _parse_mobile_action


def test_parse_valid_actions() -> None:
    assert _parse_mobile_action("TENDRILGROW_MARK_FLUSH:entry-1") == (
        "MARK_FLUSH",
        "entry-1",
    )
    assert _parse_mobile_action("TENDRILGROW_RUN_CHECK:abc") == ("RUN_CHECK", "abc")


def test_parse_invalid_actions() -> None:
    assert _parse_mobile_action("OTHER_ACTION:x") is None
    assert _parse_mobile_action("TENDRILGROW_NOSEP") is None
    assert _parse_mobile_action("TENDRILGROW_:entry") is None
    assert _parse_mobile_action("TENDRILGROW_VERB:") is None
    assert _parse_mobile_action("") is None
