"""Tests for AI provider validation and discovery behavior."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.tendrilgrow.ai.providers import (
    PROVIDERS,
    ProviderDiscoveryError,
    ProviderValidationError,
    discover_models,
    generate_vision_health_report,
    validate_provider_config,
)


def test_validate_provider_config_requires_api_key() -> None:
    with pytest.raises(ProviderValidationError):
        validate_provider_config("gemini", {})


def test_validate_provider_config_requires_valid_ollama_url() -> None:
    with pytest.raises(ProviderValidationError):
        validate_provider_config("ollama", {"base_url": "localhost:11434"})


@pytest.mark.asyncio
async def test_discovery_failure_is_wrapped() -> None:
    class DummyProvider:
        key = "dummy"

        async def list_models(self, hass, config):
            _ = hass
            _ = config
            raise ProviderDiscoveryError("boom")

    with patch(
        "custom_components.tendrilgrow.ai.providers.PROVIDERS",
        {"dummy": DummyProvider()},
    ):
        with pytest.raises(ProviderDiscoveryError):
            await discover_models(hass=None, provider="dummy", config={})


@pytest.mark.asyncio
async def test_discovery_success_returns_sorted_unique_models() -> None:
    class DummyProvider:
        key = "dummy"

        async def list_models(self, hass, config):
            _ = hass
            _ = config
            return ["b", "a", "b"]

    with patch(
        "custom_components.tendrilgrow.ai.providers.PROVIDERS",
        {"dummy": DummyProvider()},
    ):
        models = await discover_models(hass=None, provider="dummy", config={})
        assert models == ["a", "b"]


@pytest.mark.asyncio
async def test_discovery_raises_when_no_models_found() -> None:
    class DummyProvider:
        key = "dummy"

        async def list_models(self, hass, config):
            _ = hass
            _ = config
            return []

    with patch(
        "custom_components.tendrilgrow.ai.providers.PROVIDERS",
        {"dummy": DummyProvider()},
    ):
        with pytest.raises(ProviderDiscoveryError):
            await discover_models(hass=None, provider="dummy", config={})


@pytest.mark.asyncio
async def test_gemini_list_models_url_has_no_key_and_uses_header() -> None:
    session = MagicMock()
    response = AsyncMock()
    response.status = 200
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(
        return_value={"models": [{"name": "models/gemini-1.5-flash"}]}
    )
    session.get.return_value.__aenter__.return_value = response

    hass = MagicMock()
    with patch(
        "custom_components.tendrilgrow.ai.providers.async_get_clientsession",
        return_value=session,
    ):
        provider = PROVIDERS["gemini"]
        models = await provider.list_models(hass, {"api_key": "MY_GEMINI_KEY"})

    assert models == ["gemini-1.5-flash"]
    call_args = session.get.call_args
    url = call_args[0][0]
    headers = call_args[1].get("headers", {})
    assert "key=" not in url
    assert headers.get("x-goog-api-key") == "MY_GEMINI_KEY"


@pytest.mark.asyncio
async def test_gemini_vision_report_url_has_no_key_and_uses_header() -> None:
    session = MagicMock()
    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock(
        return_value={
            "candidates": [{"content": {"parts": [{"text": '{"score": 90}'}]}}]
        }
    )
    session.post.return_value.__aenter__.return_value = response

    hass = MagicMock()
    with patch(
        "custom_components.tendrilgrow.ai.providers.async_get_clientsession",
        return_value=session,
    ):
        text = await generate_vision_health_report(
            hass,
            "gemini",
            "gemini-1.5-flash",
            {"api_key": "MY_GEMINI_KEY"},
            prompt="Analyze this plant",
            image_bytes=b"fake-image",
        )

    assert text == '{"score": 90}'
    call_args = session.post.call_args
    url = call_args[0][0]
    headers = call_args[1].get("headers", {})
    assert "key=" not in url
    assert headers.get("x-goog-api-key") == "MY_GEMINI_KEY"
