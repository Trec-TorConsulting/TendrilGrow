"""AI provider abstraction and model discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    PROVIDER_GEMINI,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
)


class AIProvider(Protocol):
    """Contract for a pluggable AI provider."""

    key: str
    display_name: str

    def required_fields(self) -> tuple[str, ...]:
        """Return required config fields for this provider."""

    async def list_models(self, hass: HomeAssistant, config: dict[str, Any]) -> list[str]:
        """Return provider model ids available to the user."""


@dataclass(frozen=True, slots=True)
class ProviderDefinition:
    """Metadata and behavior for a concrete provider."""

    key: str
    display_name: str
    fields: tuple[str, ...]

    def required_fields(self) -> tuple[str, ...]:
        return self.fields

    async def list_models(self, hass: HomeAssistant, config: dict[str, Any]) -> list[str]:
        session = async_get_clientsession(hass)

        if self.key == PROVIDER_GEMINI:
            api_key = config[CONF_API_KEY]
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            async with session.get(url) as resp:
                resp.raise_for_status()
                payload = await resp.json()
            return [item["name"].replace("models/", "") for item in payload.get("models", [])]

        if self.key == PROVIDER_OPENAI:
            api_key = config[CONF_API_KEY]
            headers = {"Authorization": f"Bearer {api_key}"}
            async with session.get("https://api.openai.com/v1/models", headers=headers) as resp:
                resp.raise_for_status()
                payload = await resp.json()
            return [item["id"] for item in payload.get("data", []) if "id" in item]

        if self.key == PROVIDER_OLLAMA:
            base_url = config[CONF_BASE_URL].rstrip("/")
            async with session.get(f"{base_url}/api/tags") as resp:
                resp.raise_for_status()
                payload = await resp.json()
            return [item["name"] for item in payload.get("models", []) if "name" in item]

        return []


PROVIDERS: dict[str, ProviderDefinition] = {
    PROVIDER_GEMINI: ProviderDefinition(
        key=PROVIDER_GEMINI,
        display_name="Google Gemini",
        fields=(CONF_API_KEY,),
    ),
    PROVIDER_OPENAI: ProviderDefinition(
        key=PROVIDER_OPENAI,
        display_name="OpenAI",
        fields=(CONF_API_KEY,),
    ),
    PROVIDER_OLLAMA: ProviderDefinition(
        key=PROVIDER_OLLAMA,
        display_name="Ollama",
        fields=(CONF_BASE_URL,),
    ),
}


class ProviderValidationError(ValueError):
    """Validation error for provider configuration."""


class ProviderDiscoveryError(RuntimeError):
    """Runtime error while discovering provider models."""


def validate_provider_config(provider: str, config: dict[str, Any]) -> None:
    """Ensure required fields exist and look non-empty."""
    definition = PROVIDERS.get(provider)
    if definition is None:
        raise ProviderValidationError("unsupported_provider")

    missing = [field for field in definition.required_fields() if not str(config.get(field, "")).strip()]
    if missing:
        raise ProviderValidationError(f"missing_required:{','.join(missing)}")

    if provider == PROVIDER_OLLAMA:
        base_url = str(config.get(CONF_BASE_URL, ""))
        if not (base_url.startswith("http://") or base_url.startswith("https://")):
            raise ProviderValidationError("invalid_base_url")


async def discover_models(hass: HomeAssistant, provider: str, config: dict[str, Any]) -> list[str]:
    """Fetch models from the selected provider using configured credentials."""
    definition = PROVIDERS.get(provider)
    if definition is None:
        raise ProviderValidationError("unsupported_provider")

    try:
        models = await definition.list_models(hass, config)
    except ClientError as err:
        raise ProviderDiscoveryError(str(err)) from err

    if not models:
        raise ProviderDiscoveryError("no_models_found")
    return sorted(set(models))
