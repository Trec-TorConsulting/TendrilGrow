"""Constants for TendrilGrow."""

from __future__ import annotations

DOMAIN = "tendrilgrow"

CONF_GROW_SPACE_ID = "grow_space_id"
CONF_GROW_SPACE_NAME = "grow_space_name"
CONF_GROW_TYPE = "grow_type"
CONF_GROW_SIZE = "grow_size"

# Preset grow-type/method options offered in the config flow. custom_value is
# enabled, so operators may also type any other method (e.g. "Clone King").
GROW_TYPE_OPTIONS: tuple[str, ...] = (
    "rdwc",
    "dwc",
    "aeroponic",
    "soil",
    "coco",
    "other",
)
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
CONF_TIMELAPSE_ENABLED = "timelapse_enabled"
CONF_TIMELAPSE_INTERVAL_HOURS = "timelapse_interval_hours"
CONF_TIMELAPSE_RETENTION_FRAMES = "timelapse_retention_frames"
CONF_TIMELAPSE_DIR = "timelapse_dir"

CONF_TUYA_ENABLED = "tuya_enabled"
CONF_TUYA_ACCESS_ID = "tuya_access_id"
CONF_TUYA_ACCESS_SECRET = "tuya_access_secret"
CONF_TUYA_REGION = "tuya_region"
CONF_TUYA_UID = "tuya_uid"
CONF_TUYA_DEVICE_IDS = "tuya_device_ids"
CONF_TUYA_SCAN_INTERVAL = "tuya_scan_interval"
# Default 600s (~10 min) stays within Tuya Trial IoT Core API quotas.
DEFAULT_TUYA_SCAN_INTERVAL = 600

# Local LAN water-monitor companions (preferred over cloud polling).
CONF_WATER_MONITOR_DEVICE_ID = "water_monitor_device_id"
LOCALTUYA_DOMAIN = "localtuya"
TUYA_LOCAL_DOMAIN = "tuya_local"
LOCAL_WATER_DOMAINS: tuple[str, ...] = (LOCALTUYA_DOMAIN, TUYA_LOCAL_DOMAIN)

WATER_SOURCE_LOCALTUYA = "localtuya"
WATER_SOURCE_TUYA_LOCAL = "tuya_local"
WATER_SOURCE_CLOUD = "cloud"
WATER_SOURCE_NONE = "none"

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

# When cloud Tuya is the effective water source (no local device bound), water
# roles are auto-mapped from cloud sensors; the operator still maps canopy AIR
# temperature/humidity (for VPD) and the camera here.
SENSOR_ROLES_TUYA_OPTIONAL: tuple[str, ...] = (
    SENSOR_ROLE_TEMPERATURE,
    SENSOR_ROLE_HUMIDITY,
    SENSOR_ROLE_CAMERA,
)

# Water-quality roles auto-mapped from a bound LocalTuya / Tuya Local device.
# Excludes canopy air temperature/humidity (those stay operator-mapped for VPD).
SENSOR_ROLES_LOCAL_WATER_AUTOMAP: tuple[str, ...] = (
    SENSOR_ROLE_PH,
    SENSOR_ROLE_EC,
    SENSOR_ROLE_CF,
    SENSOR_ROLE_ORP,
    SENSOR_ROLE_TDS,
    SENSOR_ROLE_WATER_TEMPERATURE,
)

DEFAULT_AI_HEALTH_INTERVAL_HOURS = 12
DEFAULT_AI_SEVERE_THRESHOLD = 20
DEFAULT_AI_RESULT_RETENTION_DAYS = 30
DEFAULT_TIMELAPSE_ENABLED = False
DEFAULT_TIMELAPSE_INTERVAL_HOURS = 24
DEFAULT_TIMELAPSE_RETENTION_FRAMES = 120

# Grow cultivation context (editable helper entities) used to enrich AI reports.
CTX_STAGE = "ctx_stage"
CTX_STRAIN = "ctx_strain"
CTX_STAGE_STARTED = "ctx_stage_started"
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
CTX_PRICE_PER_KWH = "ctx_price_per_kwh"
CTX_WATER_TYPE = "ctx_water_type"

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

# Default growth stage, pinned by name so option ordering can change freely.
DEFAULT_STAGE = "vegetative"
STAGE_OPTIONS: tuple[str, ...] = (
    "seedling",
    "mother",
    "clone",
    "vegetative",
    "early_flower",
    "mid_flower",
    "late_flower",
    "flush",
    "harvest",
    "dry",
    "cure",
    "ready",
)

# Makeup / source water for reservoir fills and flushes.
DEFAULT_WATER_TYPE = "tap"
WATER_TYPE_OPTIONS: tuple[str, ...] = (
    "tap",
    "ro",
    "filtered",
    "bottled",
    "rain",
    "well",
    "distilled",
    "spring",
    "mixed",
)

# Per-stage reservoir target ranges used to calibrate AI scoring. Operator can
# tune these. Post-harvest stages (harvest/dry/cure/ready) have no reservoir
# targets; the prompt falls back to best-practice guidance for them.
STAGE_TARGETS: dict[str, dict[str, str]] = {
    "clone": {"ph": "5.5-6.0", "ec_ms_cm": "0.0-0.4", "vpd_kpa": "0.4-0.8"},
    "seedling": {"ph": "5.8-6.2", "ec_ms_cm": "0.4-0.8", "vpd_kpa": "0.4-0.8"},
    "mother": {"ph": "5.8-6.2", "ec_ms_cm": "1.0-1.6", "vpd_kpa": "0.7-1.2"},
    "vegetative": {"ph": "5.6-6.0", "ec_ms_cm": "0.9-1.6", "vpd_kpa": "0.7-1.2"},
    "early_flower": {"ph": "5.8-6.1", "ec_ms_cm": "1.6-2.2", "vpd_kpa": "1.0-1.3"},
    "mid_flower": {"ph": "5.8-6.2", "ec_ms_cm": "1.8-2.4", "vpd_kpa": "1.2-1.5"},
    "late_flower": {"ph": "6.0-6.3", "ec_ms_cm": "1.4-2.0", "vpd_kpa": "1.3-1.6"},
    "flush": {"ph": "5.8-6.2", "ec_ms_cm": "0.0-0.4", "vpd_kpa": "1.3-1.6"},
}

# Quality-first objective for standard flowering-line stages; STAGE_OBJECTIVES
# overrides it for stages whose goal is not flower yield/quality.
DEFAULT_OBJECTIVE = (
    "Prioritize QUALITY (terpene and cannabinoid expression, plant structure, "
    "health) over raw yield for this flowering-line plant."
)
STAGE_OBJECTIVES: dict[str, str] = {
    "clone": (
        "These are unrooted cuttings in a propagation cloner. The goal is "
        "successful rooting: keep humidity very high (low VPD), nutrients "
        "minimal, and pH/media stable. Watch for wilting, damping-off, and rot. "
        "Do NOT assess flowering, yield, or heavy feeding."
    ),
    "mother": (
        "This is a mother/stock plant kept in permanent vegetative growth to "
        "supply cuttings; it will NEVER be flowered. Prioritize long-term "
        "health, a compact bushy structure with many healthy shoots for "
        "cloning, and steady moderate feeding. Avoid stretch, nutrient burn, "
        "and stress; do NOT recommend flowering or yield-maximizing actions."
    ),
    "harvest": (
        "The plant is at harvest. Assess ripeness (trichome color, pistil "
        "recession) and readiness to cut; do not assess reservoir chemistry."
    ),
    "dry": (
        "Buds are drying, not on a reservoir. Assess the drying environment "
        "(target 60-70 F, 55-65% RH, dark, gentle airflow) and watch for mold "
        "or over-drying; aim for a slow 7-14 day dry. Ignore pH/EC."
    ),
    "cure": (
        "Buds are curing in sealed jars. Assess jar humidity (target 55-65% "
        "RH), burping cadence, and mold/ammonia risk; ignore pH/EC/VPD."
    ),
    "ready": (
        "The harvest is cured and ready for storage/use. Assess storage quality "
        "(cool, dark, 55-65% RH) for long-term preservation; ignore pH/EC/VPD."
    ),
}

# Typical stage durations in days, confirmed against Leafly (2025). Operator-
# tunable later. None = indefinite (mother) or terminal (ready).
STAGE_DURATIONS_DAYS: dict[str, int | None] = {
    "clone": 10,
    "seedling": 14,
    "mother": None,
    "vegetative": 28,
    "early_flower": 21,
    "mid_flower": 14,
    "late_flower": 21,
    "flush": 10,
    "harvest": 1,
    "dry": 10,
    "cure": 21,
    "ready": None,
}

# Biological progression used to project timings, distinct from the select's
# display order. `mother` is intentionally off-pipeline (indefinite).
STAGE_PIPELINE: tuple[str, ...] = (
    "clone",
    "seedling",
    "vegetative",
    "early_flower",
    "mid_flower",
    "late_flower",
    "flush",
    "harvest",
    "dry",
    "cure",
    "ready",
)

# Maps grow-context unique-id suffixes to prompt labels.
GROW_CONTEXT_LABELS: dict[str, str] = {
    CTX_STAGE: "growth_stage",
    CTX_STRAIN: "strain_genetics",
    CTX_STAGE_STARTED: "stage_started_on",
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
    CTX_WATER_TYPE: "water_type",
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
