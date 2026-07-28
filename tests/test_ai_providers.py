"""Tests for AI provider validation and discovery behavior."""

from unittest.mock import patch

import pytest

from custom_components.tendrilgrow.ai.providers import (
    ProviderDiscoveryError,
    ProviderValidationError,
    discover_models,
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
