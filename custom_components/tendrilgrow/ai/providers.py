"""AI provider abstraction and model discovery."""

from __future__ import annotations

import base64
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

    async def list_models(
        self, hass: HomeAssistant, config: dict[str, Any]
    ) -> list[str]:
        """Return provider model ids available to the user."""


@dataclass(frozen=True, slots=True)
class ProviderDefinition:
    """Metadata and behavior for a concrete provider."""

    key: str
    display_name: str
    fields: tuple[str, ...]

    def required_fields(self) -> tuple[str, ...]:
        return self.fields

    async def list_models(
        self, hass: HomeAssistant, config: dict[str, Any]
    ) -> list[str]:
        session = async_get_clientsession(hass)

        if self.key == PROVIDER_GEMINI:
            api_key = config[CONF_API_KEY]
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            )
            async with session.get(url) as resp:
                resp.raise_for_status()
                payload = await resp.json()
            return [
                item["name"].replace("models/", "")
                for item in payload.get("models", [])
            ]

        if self.key == PROVIDER_OPENAI:
            api_key = config[CONF_API_KEY]
            headers = {"Authorization": f"Bearer {api_key}"}
            async with session.get(
                "https://api.openai.com/v1/models", headers=headers
            ) as resp:
                resp.raise_for_status()
                payload = await resp.json()
            return [item["id"] for item in payload.get("data", []) if "id" in item]

        if self.key == PROVIDER_OLLAMA:
            base_url = config[CONF_BASE_URL].rstrip("/")
            async with session.get(f"{base_url}/api/tags") as resp:
                resp.raise_for_status()
                payload = await resp.json()
            return [
                item["name"] for item in payload.get("models", []) if "name" in item
            ]

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


class ProviderExecutionError(RuntimeError):
    """Runtime error while executing an AI provider request."""


def validate_provider_config(provider: str, config: dict[str, Any]) -> None:
    """Ensure required fields exist and look non-empty."""
    definition = PROVIDERS.get(provider)
    if definition is None:
        raise ProviderValidationError("unsupported_provider")

    missing = [
        field
        for field in definition.required_fields()
        if not str(config.get(field, "")).strip()
    ]
    if missing:
        raise ProviderValidationError(f"missing_required:{','.join(missing)}")

    if provider == PROVIDER_OLLAMA:
        base_url = str(config.get(CONF_BASE_URL, ""))
        if not (base_url.startswith("http://") or base_url.startswith("https://")):
            raise ProviderValidationError("invalid_base_url")


async def discover_models(
    hass: HomeAssistant, provider: str, config: dict[str, Any]
) -> list[str]:
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


def _extract_openai_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [part.get("text", "") for part in content if isinstance(part, dict)]
        return "\n".join(part for part in parts if part).strip()
    return ""


def _extract_gemini_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    chunks = [part.get("text", "") for part in parts if isinstance(part, dict)]
    return "\n".join(chunk for chunk in chunks if chunk).strip()


async def _read_json_or_raise(resp: Any, provider: str) -> dict[str, Any]:
    """Return parsed JSON, or raise ProviderExecutionError with the response body."""
    if resp.status >= 400:
        body = await resp.text()
        raise ProviderExecutionError(
            f"{provider} HTTP {resp.status}: {body[:400].strip()}"
        )
    return await resp.json(content_type=None)


async def generate_vision_health_report(
    hass: HomeAssistant,
    provider: str,
    model: str,
    config: dict[str, Any],
    *,
    prompt: str,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
) -> str:
    """Generate a vision-aware health report for one grow-space snapshot."""
    definition = PROVIDERS.get(provider)
    if definition is None:
        raise ProviderExecutionError("unsupported_provider")

    encoded = base64.b64encode(image_bytes).decode("ascii")
    session = async_get_clientsession(hass)

    try:
        if provider == PROVIDER_GEMINI:
            api_key = str(config.get(CONF_API_KEY, "")).strip()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": encoded,
                                }
                            },
                        ]
                    }
                ],
            }
            async with session.post(url, json=payload) as resp:
                body = await _read_json_or_raise(resp, provider)
            return _extract_gemini_text(body)

        if provider == PROVIDER_OPENAI:
            api_key = str(config.get(CONF_API_KEY, "")).strip()
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{encoded}"
                                },
                            },
                        ],
                    }
                ],
            }
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            ) as resp:
                body = await _read_json_or_raise(resp, provider)
            return _extract_openai_text(body)

        if provider == PROVIDER_OLLAMA:
            base_url = str(config.get(CONF_BASE_URL, "")).rstrip("/")
            payload = {
                "model": model,
                "stream": False,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [encoded],
                    }
                ],
            }
            async with session.post(f"{base_url}/api/chat", json=payload) as resp:
                body = await _read_json_or_raise(resp, provider)
            return str(body.get("message", {}).get("content", "")).strip()
    except ClientError as err:
        raise ProviderExecutionError(str(err)) from err

    raise ProviderExecutionError("unsupported_provider")
