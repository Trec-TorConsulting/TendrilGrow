"""Constants for TendrilGrow."""

from __future__ import annotations

DOMAIN = "tendrilgrow"

CONF_GROW_SPACE_ID = "grow_space_id"
CONF_GROW_SPACE_NAME = "grow_space_name"
CONF_GROW_TYPE = "grow_type"
CONF_GROW_SIZE = "grow_size"
CONF_SITES = "sites"
CONF_SENSOR_MAPPINGS = "sensor_mappings"
CONF_CONTROL_MAPPINGS = "control_mappings"
CONF_TARGETS = "targets"
CONF_SCHEDULES = "schedules"

CONF_AI_PROVIDER = "ai_provider"
CONF_AI_MODEL = "ai_model"
CONF_API_KEY = "api_key"
CONF_BASE_URL = "base_url"

PROVIDER_NONE = "none"
PROVIDER_GEMINI = "gemini"
PROVIDER_OPENAI = "openai"
PROVIDER_OLLAMA = "ollama"

SENSOR_ROLE_TEMPERATURE = "temperature"
SENSOR_ROLE_HUMIDITY = "humidity"
SENSOR_ROLE_LIGHT = "light_ppfd"
SENSOR_ROLE_PH = "ph"
SENSOR_ROLE_EC = "ec_tds"
SENSOR_ROLE_CAMERA = "camera"

CONTROL_ROLE_LIGHTS = "lights"
CONTROL_ROLE_FANS = "fans"
CONTROL_ROLE_INLINE_FANS = "inline_fans"

SENSOR_ROLES: tuple[str, ...] = (
    SENSOR_ROLE_TEMPERATURE,
    SENSOR_ROLE_HUMIDITY,
    SENSOR_ROLE_LIGHT,
    SENSOR_ROLE_PH,
    SENSOR_ROLE_EC,
    SENSOR_ROLE_CAMERA,
)

CONTROL_ROLES: tuple[str, ...] = (
    CONTROL_ROLE_LIGHTS,
    CONTROL_ROLE_FANS,
    CONTROL_ROLE_INLINE_FANS,
)

SENSITIVE_KEYS: tuple[str, ...] = (
    CONF_API_KEY,
)
