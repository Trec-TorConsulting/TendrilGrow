"""Config flow for TendrilGrow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL
from homeassistant.helpers import selector

from .ai.providers import (
    PROVIDERS,
    ProviderDiscoveryError,
    ProviderValidationError,
    discover_models,
    validate_provider_config,
)
from .const import (
    CONF_AI_MODEL,
    CONF_AI_PROVIDER,
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_CONTROL_MAPPINGS,
    CONF_GROW_SIZE,
    CONF_GROW_SPACE_NAME,
    CONF_GROW_TYPE,
    CONF_SCHEDULES,
    CONF_SENSOR_MAPPINGS,
    CONF_TUYA_ACCESS_ID,
    CONF_TUYA_ACCESS_SECRET,
    CONF_TUYA_DEVICE_IDS,
    CONF_TUYA_ENABLED,
    CONF_TUYA_REGION,
    CONF_TUYA_SCAN_INTERVAL,
    CONF_TUYA_UID,
    CONF_TARGETS,
    CONTROL_ROLES,
    DOMAIN,
    PROVIDER_GEMINI,
    PROVIDER_OLLAMA,
    PROVIDER_NONE,
    PROVIDER_OPENAI,
    SENSOR_ROLE_EC_TDS_LEGACY,
    SENSOR_ROLE_TDS,
    SENSOR_ROLES,
    SENSOR_ROLES_CONFIGURABLE,
)
from .models.grow import GrowSpace

TUYA_REGIONS: tuple[str, ...] = ("us", "eu", "cn", "in")


def _parse_tuya_device_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [device_id.strip() for device_id in raw.split(",") if device_id.strip()]


def _entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(multiple=False))


def _optional_entity_field(
    fields: dict[Any, Any],
    role: str,
    mapping: dict[str, str],
) -> None:
    existing = mapping.get(role, "")
    if existing:
        fields[vol.Optional(role, default=existing)] = _entity_selector()
        return
    fields[vol.Optional(role)] = _entity_selector()


def _normalize_sensor_mappings(sensor_mappings: dict[str, str]) -> dict[str, str]:
    normalized = dict(sensor_mappings)
    if SENSOR_ROLE_EC_TDS_LEGACY in normalized and SENSOR_ROLE_TDS not in normalized:
        normalized[SENSOR_ROLE_TDS] = normalized[SENSOR_ROLE_EC_TDS_LEGACY]
    return normalized


class TendrilGrowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TendrilGrow."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._models: list[str] = []
        self._provider_error: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Create one config entry per grow space."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_GROW_SPACE_NAME].strip()
            if any(entry.title.lower() == name.lower() for entry in self._async_current_entries()):
                errors["base"] = "duplicate_name"
            else:
                self._data.update(user_input)
                return await self.async_step_entity_mapping()

        schema = vol.Schema(
            {
                vol.Required(CONF_GROW_SPACE_NAME): str,
                vol.Required(CONF_GROW_TYPE, default="rdwc"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["rdwc", "soil", "coco", "other"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_GROW_SIZE, default=""): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_entity_mapping(self, user_input: dict[str, Any] | None = None):
        """Map sensor and control roles to user entities."""
        if user_input is not None:
            sensor_mappings = {
                role: value for role, value in user_input.items() if role in SENSOR_ROLES and value
            }
            control_mappings = {
                role: value for role, value in user_input.items() if role in CONTROL_ROLES and value
            }
            self._data[CONF_SENSOR_MAPPINGS] = sensor_mappings
            self._data[CONF_CONTROL_MAPPINGS] = control_mappings
            self._data[CONF_TUYA_ENABLED] = bool(user_input.get(CONF_TUYA_ENABLED, False))
            self._data[CONF_TUYA_ACCESS_ID] = str(user_input.get(CONF_TUYA_ACCESS_ID, "")).strip()
            self._data[CONF_TUYA_ACCESS_SECRET] = str(
                user_input.get(CONF_TUYA_ACCESS_SECRET, "")
            ).strip()
            self._data[CONF_TUYA_REGION] = str(user_input.get(CONF_TUYA_REGION, "us"))
            self._data[CONF_TUYA_UID] = str(user_input.get(CONF_TUYA_UID, "")).strip()
            self._data[CONF_TUYA_DEVICE_IDS] = _parse_tuya_device_ids(
                str(user_input.get(CONF_TUYA_DEVICE_IDS, ""))
            )
            self._data[CONF_TUYA_SCAN_INTERVAL] = int(user_input.get(CONF_TUYA_SCAN_INTERVAL, 60))
            self._data.setdefault(CONF_TARGETS, {})
            self._data.setdefault(CONF_SCHEDULES, {})
            return await self.async_step_ai_provider()

        fields: dict[Any, Any] = {}
        for role in SENSOR_ROLES_CONFIGURABLE:
            fields[vol.Optional(role)] = _entity_selector()
        for role in CONTROL_ROLES:
            fields[vol.Optional(role)] = _entity_selector()
        fields[vol.Optional(CONF_TUYA_ENABLED, default=False)] = bool
        fields[vol.Optional(CONF_TUYA_ACCESS_ID)] = str
        fields[vol.Optional(CONF_TUYA_ACCESS_SECRET)] = str
        fields[vol.Optional(CONF_TUYA_REGION, default="us")] = vol.In(TUYA_REGIONS)
        fields[vol.Optional(CONF_TUYA_UID)] = str
        fields[vol.Optional(CONF_TUYA_DEVICE_IDS)] = str
        fields[vol.Optional(CONF_TUYA_SCAN_INTERVAL, default=60)] = vol.All(
            vol.Coerce(int),
            vol.Range(min=30, max=3600),
        )
        schema = vol.Schema(fields)
        return self.async_show_form(step_id="entity_mapping", data_schema=schema, errors={})

    async def async_step_ai_provider(self, user_input: dict[str, Any] | None = None):
        """Choose AI provider for this grow space entry."""
        if user_input is not None:
            provider = user_input[CONF_AI_PROVIDER]
            self._data[CONF_AI_PROVIDER] = provider
            if provider == PROVIDER_NONE:
                return self._finish_entry()
            return await self.async_step_ai_credentials()

        options = [
            selector.SelectOptionDict(value=PROVIDER_NONE, label="None"),
            *[
                selector.SelectOptionDict(value=provider.key, label=provider.display_name)
                for provider in PROVIDERS.values()
            ],
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_AI_PROVIDER, default=PROVIDER_NONE): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
                )
            }
        )
        return self.async_show_form(step_id="ai_provider", data_schema=schema, errors={})

    async def async_step_ai_credentials(self, user_input: dict[str, Any] | None = None):
        """Collect provider credentials and discover models."""
        errors: dict[str, str] = {}
        provider = self._data[CONF_AI_PROVIDER]

        if user_input is not None:
            provider_config: dict[str, Any] = {}
            if provider in (PROVIDER_GEMINI, PROVIDER_OPENAI):
                provider_config[CONF_API_KEY] = user_input.get(CONF_API_KEY, "")
            if provider == PROVIDER_OLLAMA:
                provider_config[CONF_BASE_URL] = user_input.get(CONF_BASE_URL, "")

            manual_model = user_input.get(CONF_MODEL)

            try:
                validate_provider_config(provider, provider_config)
                self._models = await discover_models(self.hass, provider, provider_config)
            except ProviderValidationError as err:
                errors["base"] = str(err)
            except ProviderDiscoveryError as err:
                if manual_model:
                    self._data.update(provider_config)
                    self._data[CONF_AI_MODEL] = str(manual_model)
                    return self._finish_entry()
                errors["base"] = f"model_discovery_failed:{err}"

            if not errors:
                self._data.update(provider_config)
                return await self.async_step_ai_model_select()

        fields: dict[Any, Any] = {}
        if provider in (PROVIDER_GEMINI, PROVIDER_OPENAI):
            fields[vol.Required(CONF_API_KEY)] = selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            )
        if provider == PROVIDER_OLLAMA:
            fields[vol.Required(CONF_BASE_URL)] = str

        # Manual fallback when discovery fails.
        if errors.get("base", "").startswith("model_discovery_failed"):
            fields[vol.Optional(CONF_MODEL)] = str

        return self.async_show_form(
            step_id="ai_credentials",
            data_schema=vol.Schema(fields),
            errors=errors,
        )

    async def async_step_ai_model_select(self, user_input: dict[str, Any] | None = None):
        """Select a model from discovered provider models."""
        if user_input is not None:
            self._data[CONF_AI_MODEL] = user_input[CONF_AI_MODEL]
            return self._finish_entry()

        options = [selector.SelectOptionDict(value=model, label=model) for model in self._models]
        schema = vol.Schema(
            {
                vol.Required(CONF_AI_MODEL): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
                )
            }
        )
        return self.async_show_form(step_id="ai_model_select", data_schema=schema, errors={})

    def _finish_entry(self):
        grow_space = GrowSpace.new(
            name=self._data[CONF_GROW_SPACE_NAME],
            grow_type=self._data[CONF_GROW_TYPE],
            descriptor=self._data.get(CONF_GROW_SIZE, ""),
        )
        grow_space.sensor_mappings.update(self._data.get(CONF_SENSOR_MAPPINGS, {}))
        grow_space.control_mappings.update(self._data.get(CONF_CONTROL_MAPPINGS, {}))
        grow_space.targets.update(self._data.get(CONF_TARGETS, {}))
        grow_space.schedules.update(self._data.get(CONF_SCHEDULES, {}))

        data = grow_space.to_dict()
        data[CONF_GROW_SIZE] = self._data.get(CONF_GROW_SIZE, "")
        data[CONF_AI_PROVIDER] = self._data.get(CONF_AI_PROVIDER, PROVIDER_NONE)
        data[CONF_AI_MODEL] = self._data.get(CONF_AI_MODEL, "")
        data[CONF_TUYA_ENABLED] = self._data.get(CONF_TUYA_ENABLED, False)
        data[CONF_TUYA_ACCESS_ID] = self._data.get(CONF_TUYA_ACCESS_ID, "")
        data[CONF_TUYA_ACCESS_SECRET] = self._data.get(CONF_TUYA_ACCESS_SECRET, "")
        data[CONF_TUYA_REGION] = self._data.get(CONF_TUYA_REGION, "us")
        data[CONF_TUYA_UID] = self._data.get(CONF_TUYA_UID, "")
        data[CONF_TUYA_DEVICE_IDS] = self._data.get(CONF_TUYA_DEVICE_IDS, [])
        data[CONF_TUYA_SCAN_INTERVAL] = self._data.get(CONF_TUYA_SCAN_INTERVAL, 60)
        if CONF_API_KEY in self._data:
            data[CONF_API_KEY] = self._data[CONF_API_KEY]
        if CONF_BASE_URL in self._data:
            data[CONF_BASE_URL] = self._data[CONF_BASE_URL]

        return self.async_create_entry(title=grow_space.name, data=data)

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return TendrilGrowOptionsFlow(config_entry)


class TendrilGrowOptionsFlow(config_entries.OptionsFlow):
    """Handle TendrilGrow options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            current = dict(self._entry.data)
            current.update(getattr(self._entry, "options", {}))
            submitted_secret = str(user_input.get(CONF_TUYA_ACCESS_SECRET, "")).strip()
            resolved_secret = submitted_secret or str(current.get(CONF_TUYA_ACCESS_SECRET, "")).strip()
            sensor_mappings = {
                role: value for role, value in user_input.items() if role in SENSOR_ROLES and value
            }
            control_mappings = {
                role: value for role, value in user_input.items() if role in CONTROL_ROLES and value
            }
            return self.async_create_entry(
                title="",
                data={
                    CONF_GROW_TYPE: user_input.get(CONF_GROW_TYPE, "rdwc"),
                    CONF_GROW_SIZE: user_input.get(CONF_GROW_SIZE, ""),
                    CONF_SENSOR_MAPPINGS: sensor_mappings,
                    CONF_CONTROL_MAPPINGS: control_mappings,
                    CONF_TUYA_ENABLED: bool(user_input.get(CONF_TUYA_ENABLED, False)),
                    CONF_TUYA_ACCESS_ID: str(user_input.get(CONF_TUYA_ACCESS_ID, "")).strip(),
                    CONF_TUYA_ACCESS_SECRET: resolved_secret,
                    CONF_TUYA_REGION: str(user_input.get(CONF_TUYA_REGION, "us")),
                    CONF_TUYA_UID: str(user_input.get(CONF_TUYA_UID, "")).strip(),
                    CONF_TUYA_DEVICE_IDS: _parse_tuya_device_ids(
                        str(user_input.get(CONF_TUYA_DEVICE_IDS, ""))
                    ),
                    CONF_TUYA_SCAN_INTERVAL: int(user_input.get(CONF_TUYA_SCAN_INTERVAL, 60)),
                },
            )

        current = dict(self._entry.data)
        current.update(getattr(self._entry, "options", {}))
        fields: dict[Any, Any] = {
            vol.Required(CONF_GROW_TYPE, default=current.get(CONF_GROW_TYPE, "rdwc")): str,
            vol.Optional(CONF_GROW_SIZE, default=current.get(CONF_GROW_SIZE, "")): str,
        }

        sensor_mappings = _normalize_sensor_mappings(current.get(CONF_SENSOR_MAPPINGS, {}))
        for role in SENSOR_ROLES_CONFIGURABLE:
            _optional_entity_field(fields, role, sensor_mappings)

        control_mappings = current.get(CONF_CONTROL_MAPPINGS, {})
        for role in CONTROL_ROLES:
            _optional_entity_field(fields, role, control_mappings)

        tuya_enabled = bool(current.get(CONF_TUYA_ENABLED, False))
        tuya_device_ids = current.get(CONF_TUYA_DEVICE_IDS, [])
        fields[vol.Optional(CONF_TUYA_ENABLED, default=tuya_enabled)] = bool
        fields[vol.Optional(CONF_TUYA_ACCESS_ID, default=current.get(CONF_TUYA_ACCESS_ID, ""))] = str
        fields[vol.Optional(CONF_TUYA_ACCESS_SECRET)] = str
        fields[vol.Optional(CONF_TUYA_REGION, default=current.get(CONF_TUYA_REGION, "us"))] = vol.In(
            TUYA_REGIONS
        )
        fields[vol.Optional(CONF_TUYA_UID, default=current.get(CONF_TUYA_UID, ""))] = str
        fields[vol.Optional(CONF_TUYA_DEVICE_IDS, default=",".join(tuya_device_ids))] = str
        fields[vol.Optional(CONF_TUYA_SCAN_INTERVAL, default=current.get(CONF_TUYA_SCAN_INTERVAL, 60))] = (
            vol.All(vol.Coerce(int), vol.Range(min=30, max=3600))
        )

        return self.async_show_form(step_id="init", data_schema=vol.Schema(fields), errors={})
