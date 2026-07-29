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
CONF_AI_HEALTH_INTERVAL_HOURS = "ai_health_interval_hours"
CONF_AI_SEVERE_THRESHOLD = "ai_severe_threshold"
CONF_AI_NOTIFY_SERVICE = "ai_notify_service"
CONF_AI_RESULT_RETENTION_DAYS = "ai_result_retention_days"

CONF_TUYA_ENABLED = "tuya_enabled"
CONF_TUYA_ACCESS_ID = "tuya_access_id"
CONF_TUYA_ACCESS_SECRET = "tuya_access_secret"
CONF_TUYA_REGION = "tuya_region"
CONF_TUYA_UID = "tuya_uid"
CONF_TUYA_DEVICE_IDS = "tuya_device_ids"
CONF_TUYA_SCAN_INTERVAL = "tuya_scan_interval"

PROVIDER_NONE = "none"
PROVIDER_GEMINI = "gemini"
PROVIDER_OPENAI = "openai"
PROVIDER_OLLAMA = "ollama"

# temperature/humidity are AIR (canopy) roles used for VPD; water_temperature is
# the reservoir/water probe and is NOT used for canopy VPD.
SENSOR_ROLE_TEMPERATURE = "temperature"
SENSOR_ROLE_HUMIDITY = "humidity"
SENSOR_ROLE_WATER_TEMPERATURE = "water_temperature"
SENSOR_ROLE_LIGHT = "light_ppfd"
SENSOR_ROLE_PH = "ph"
SENSOR_ROLE_EC = "ec"
SENSOR_ROLE_CF = "cf"
SENSOR_ROLE_ORP = "orp"
SENSOR_ROLE_TDS = "tds"
# Backward-compatibility alias for early foundation entries.
SENSOR_ROLE_EC_TDS_LEGACY = "ec_tds"
SENSOR_ROLE_CAMERA = "camera"

CONTROL_ROLE_LIGHTS = "lights"
CONTROL_ROLE_FANS = "fans"
CONTROL_ROLE_INLINE_FANS = "inline_fans"
CONTROL_ROLE_RDWC_PUMP = "rdwc_pump"
CONTROL_ROLE_CHILLER_PUMP = "chiller_pump"
CONTROL_ROLE_AIR_PUMP = "air_pump"

# Power sensor roles for pump monitoring.
SENSOR_ROLE_RDWC_PUMP_POWER = "rdwc_pump_power"
SENSOR_ROLE_CHILLER_PUMP_POWER = "chiller_pump_power"
SENSOR_ROLE_AIR_PUMP_POWER = "air_pump_power"

SENSOR_ROLES: tuple[str, ...] = (
    SENSOR_ROLE_TEMPERATURE,
    SENSOR_ROLE_HUMIDITY,
    SENSOR_ROLE_LIGHT,
    SENSOR_ROLE_PH,
    SENSOR_ROLE_EC,
    SENSOR_ROLE_CF,
    SENSOR_ROLE_ORP,
    SENSOR_ROLE_TDS,
    SENSOR_ROLE_WATER_TEMPERATURE,
    SENSOR_ROLE_EC_TDS_LEGACY,
    SENSOR_ROLE_CAMERA,
    SENSOR_ROLE_RDWC_PUMP_POWER,
    SENSOR_ROLE_CHILLER_PUMP_POWER,
    SENSOR_ROLE_AIR_PUMP_POWER,
)

# Sensor roles shown in config and options forms.
SENSOR_ROLES_CONFIGURABLE: tuple[str, ...] = (
    SENSOR_ROLE_TEMPERATURE,
    SENSOR_ROLE_HUMIDITY,
    SENSOR_ROLE_LIGHT,
    SENSOR_ROLE_PH,
    SENSOR_ROLE_EC,
    SENSOR_ROLE_CF,
    SENSOR_ROLE_ORP,
    SENSOR_ROLE_TDS,
    SENSOR_ROLE_WATER_TEMPERATURE,
    SENSOR_ROLE_CAMERA,
    SENSOR_ROLE_RDWC_PUMP_POWER,
    SENSOR_ROLE_CHILLER_PUMP_POWER,
    SENSOR_ROLE_AIR_PUMP_POWER,
)

# Under Tuya, water metrics come from the cloud; the operator still maps canopy
# AIR temperature/humidity (for VPD) and the camera here.
SENSOR_ROLES_TUYA_OPTIONAL: tuple[str, ...] = (
    SENSOR_ROLE_TEMPERATURE,
    SENSOR_ROLE_HUMIDITY,
    SENSOR_ROLE_CAMERA,
)

DEFAULT_AI_HEALTH_INTERVAL_HOURS = 12
DEFAULT_AI_SEVERE_THRESHOLD = 20
DEFAULT_AI_RESULT_RETENTION_DAYS = 30

# Grow cultivation context (editable helper entities) used to enrich AI reports.
CTX_STAGE = "ctx_stage"
CTX_STRAIN = "ctx_strain"
CTX_WEEK_IN_STAGE = "ctx_week_in_stage"
CTX_RESERVOIR_VOLUME = "ctx_reservoir_volume_gal"
CTX_SITE_COUNT = "ctx_site_count"
CTX_TARGET_PH = "ctx_target_ph"
CTX_TARGET_EC = "ctx_target_ec"
CTX_FEED_INTERVAL_DAYS = "ctx_feed_interval_days"
CTX_LIGHTS_ON_HOURS = "ctx_lights_on_hours"
CTX_RUNOFF_TARGET_PCT = "ctx_runoff_target_pct"
CTX_NUTRIENT_LINE = "ctx_nutrient_line"
CTX_BASE_NUTRIENTS = "ctx_base_nutrients"
CTX_ADDITIVES = "ctx_additives"

# Reservoir full-flush tracking. Suffixes are appended to the entry id to form
# entity unique ids. Suffixes MUST NOT be a suffix of one another so the AI
# context collector's endswith() matching stays unambiguous (note that
# "next_flush_due" ends with "flush_due", so "flush_due" is intentionally kept
# out of GROW_CONTEXT_LABELS below).
DEFAULT_FLUSH_INTERVAL_DAYS = 7
CTX_FLUSH_INTERVAL_DAYS = "flush_interval_days"
FLUSH_NOW_SUFFIX = "flush_now"
FLUSH_LAST_SUFFIX = "last_flush"
FLUSH_DAYS_SINCE_SUFFIX = "days_since_flush"
FLUSH_DAYS_UNTIL_SUFFIX = "days_until_flush"
FLUSH_NEXT_DUE_SUFFIX = "next_flush_due"
FLUSH_DUE_SUFFIX = "flush_due"

STAGE_OPTIONS: tuple[str, ...] = (
    "seedling",
    "vegetative",
    "early_flower",
    "mid_flower",
    "late_flower",
    "flush",
)

# Per-stage target ranges used to calibrate AI scoring. Operator can tune these.
STAGE_TARGETS: dict[str, dict[str, str]] = {
    "seedling": {"ph": "5.8-6.2", "ec_ms_cm": "0.4-0.8", "vpd_kpa": "0.4-0.8"},
    "vegetative": {"ph": "5.6-6.0", "ec_ms_cm": "1.2-1.8", "vpd_kpa": "0.8-1.1"},
    "early_flower": {"ph": "5.8-6.1", "ec_ms_cm": "1.6-2.2", "vpd_kpa": "1.0-1.3"},
    "mid_flower": {"ph": "5.8-6.2", "ec_ms_cm": "1.8-2.4", "vpd_kpa": "1.2-1.5"},
    "late_flower": {"ph": "6.0-6.3", "ec_ms_cm": "1.4-2.0", "vpd_kpa": "1.3-1.6"},
    "flush": {"ph": "5.8-6.2", "ec_ms_cm": "0.0-0.4", "vpd_kpa": "1.3-1.6"},
}

# Maps grow-context unique-id suffixes to prompt labels.
GROW_CONTEXT_LABELS: dict[str, str] = {
    CTX_STAGE: "growth_stage",
    CTX_STRAIN: "strain_genetics",
    CTX_WEEK_IN_STAGE: "week_in_stage",
    CTX_RESERVOIR_VOLUME: "reservoir_volume_gal",
    CTX_SITE_COUNT: "site_count_plants",
    CTX_TARGET_PH: "target_ph",
    CTX_TARGET_EC: "target_ec_ms_cm",
    CTX_FEED_INTERVAL_DAYS: "feed_interval_days",
    CTX_LIGHTS_ON_HOURS: "lights_on_hours",
    CTX_RUNOFF_TARGET_PCT: "runoff_target_pct",
    CTX_NUTRIENT_LINE: "nutrient_line",
    CTX_BASE_NUTRIENTS: "base_nutrients",
    CTX_ADDITIVES: "additives",
    # Flush cadence context (collision-safe suffixes only; see note above).
    CTX_FLUSH_INTERVAL_DAYS: "flush_interval_days",
    FLUSH_DAYS_SINCE_SUFFIX: "days_since_last_flush",
}

CONTROL_ROLES: tuple[str, ...] = (
    CONTROL_ROLE_LIGHTS,
    CONTROL_ROLE_FANS,
    CONTROL_ROLE_INLINE_FANS,
    CONTROL_ROLE_RDWC_PUMP,
    CONTROL_ROLE_CHILLER_PUMP,
    CONTROL_ROLE_AIR_PUMP,
)

# Pump-specific control roles used for power monitoring and service routing.
PUMP_CONTROL_ROLES: tuple[str, ...] = (
    CONTROL_ROLE_RDWC_PUMP,
    CONTROL_ROLE_CHILLER_PUMP,
    CONTROL_ROLE_AIR_PUMP,
)

# Maps a pump control role to its optional power sensor role.
PUMP_POWER_ROLE_FOR: dict[str, str] = {
    CONTROL_ROLE_RDWC_PUMP: SENSOR_ROLE_RDWC_PUMP_POWER,
    CONTROL_ROLE_CHILLER_PUMP: SENSOR_ROLE_CHILLER_PUMP_POWER,
    CONTROL_ROLE_AIR_PUMP: SENSOR_ROLE_AIR_PUMP_POWER,
}

# Human-friendly labels for pump roles.
PUMP_LABELS: dict[str, str] = {
    CONTROL_ROLE_RDWC_PUMP: "RDWC Pump",
    CONTROL_ROLE_CHILLER_PUMP: "Chiller Pump",
    CONTROL_ROLE_AIR_PUMP: "Air Pump",
}

SENSITIVE_KEYS: tuple[str, ...] = (
    CONF_API_KEY,
    CONF_TUYA_ACCESS_SECRET,
)
