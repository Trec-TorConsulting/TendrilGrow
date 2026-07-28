"""Tests for diagnostics redaction."""

from types import SimpleNamespace

import pytest

from custom_components.tendrilgrow.diagnostics import async_get_config_entry_diagnostics


@pytest.mark.asyncio
async def test_diagnostics_redacts_api_key() -> None:
    entry = SimpleNamespace(
        entry_id="123",
        title="Tent A",
        data={"api_key": "secret", "grow_space_name": "Tent A"},
        options={"api_key": "another-secret"},
    )

    payload = await async_get_config_entry_diagnostics(hass=None, entry=entry)

    assert payload["data"]["api_key"] == "**REDACTED**"
    assert payload["options"]["api_key"] == "**REDACTED**"
