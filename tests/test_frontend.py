"""Tests for TendrilGrow frontend card registration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.tendrilgrow import _async_register_frontend


@pytest.mark.asyncio
async def test_frontend_card_file_exists() -> None:
    """Verify that tendrilgrow-card.js exists in the frontend directory."""
    card_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "tendrilgrow"
        / "frontend"
        / "tendrilgrow-card.js"
    )
    assert card_path.is_file(), f"Missing frontend card at {card_path}"
    content = card_path.read_text(encoding="utf-8")
    assert "tendrilgrow-twin-card" in content
    assert "tendrilgrow-overview-card" in content


@pytest.mark.asyncio
async def test_async_register_frontend_success() -> None:
    """Test successful static path and extra js url registration."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()

    with patch("homeassistant.components.frontend.add_extra_js_url") as mock_add_url:
        await _async_register_frontend(hass)

        assert hass.data.get("tendrilgrow_frontend_registered") is True
        hass.http.async_register_static_paths.assert_awaited_once()
        mock_add_url.assert_called_once_with(
            hass, "/tendrilgrow_static/tendrilgrow-card.js"
        )

        # Calling a second time should be idempotent (early exit)
        await _async_register_frontend(hass)
        assert hass.http.async_register_static_paths.await_count == 1


@pytest.mark.asyncio
async def test_async_register_frontend_without_http() -> None:
    """Test frontend registration gracefully handles missing http or frontend."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.http = None

    await _async_register_frontend(hass)
    assert hass.data.get("tendrilgrow_frontend_registered") is True
