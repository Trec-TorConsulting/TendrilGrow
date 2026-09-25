"""AI health-check runtime helpers for TendrilGrow."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_AI_MODEL,
    CONF_AI_NOTIFY_SERVICE,
    CONF_AI_PROVIDER,
    CONF_AI_RESULT_RETENTION_DAYS,
    CONF_AI_SEVERE_THRESHOLD,
    CONF_API_KEY,
    CONF_BASE_URL,
    CONTROL_ROLE_AIR_PUMP,
    CONTROL_ROLE_CHILLER_PUMP,
    CONTROL_ROLE_FANS,
    CONTROL_ROLE_INLINE_FANS,
    CONTROL_ROLE_LIGHTS,
    CONTROL_ROLE_RDWC_PUMP,
    DEFAULT_AI_RESULT_RETENTION_DAYS,
    DEFAULT_AI_SEVERE_THRESHOLD,
    DEFAULT_OBJECTIVE,
    DOMAIN,
    GROW_CONTEXT_LABELS,
    PROVIDER_NONE,
    SENSOR_ROLE_CAMERA,
    SENSOR_ROLE_HUMIDITY,
    SENSOR_ROLE_LIGHT,
    SENSOR_ROLE_TEMPERATURE,
    STAGE_OBJECTIVES,
    STAGE_TARGETS,
)
from ..insights import compute_dew_point_c, compute_dli, days_in_stage, weeks_in_stage
from ..models.grow import GrowSpace
from .providers import ProviderExecutionError, generate_vision_health_report

LOGGER = logging.getLogger(__name__)

METRIC_ROLE_LABELS: dict[str, str] = {
    "temperature": "Air Temperature",
    "humidity": "Air Humidity",
    "water_temperature": "Water/Reservoir Temperature",
    "ph": "pH",
    "ec": "EC",
    "cf": "CF",
    "orp": "ORP",
    "tds": "TDS",
    "light_ppfd": "Light PPFD",
    "rdwc_pump_power": "RDWC pump power",
    "chiller_pump_power": "Chiller pump power",
    "air_pump_power": "Air pump power",
    "dli_mol_m2_d": "Derived DLI",
    "dew_point": "Derived dew point",
    "vpd_kpa": "Derived air VPD",
}


def _coerce_metric_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# Keywords that identify GH Flora series in operator-provided context text.
_GH_FLORA_KEYWORDS = (
    "flora",
    "general hydro",
    "gh flora",
    "floramicro",
    "floragro",
    "florabloom",
)


# Current-stage Flora rates (ml/gal). A deliberate light feed, under GH's
# published Medium and Aggressive charts. Not a GH Light/Medium/Aggressive row.
_FLORA_RATES_ML_PER_GAL: dict[str, str] = {
    "clone": "CalMag+ 2.5, Micro 1.25, Gro 1.25, Bloom 1.25, Hydroguard 2",
    "seedling": "CalMag+ 2.5, Micro 1.25, Gro 1.25, Bloom 1.25, Hydroguard 2",
    "mother": "CalMag+ 2.5, Micro 2.5, Gro 2.5, Bloom 2.5, Hydroguard 2",
    "vegetative": "CalMag+ 2.5, Micro 2.5, Gro 2.5, Bloom 2.5, Hydroguard 2",
    "early_flower": "CalMag+ 2.5, Micro 2.5, Gro 1.25, Bloom 3.75, Hydroguard 2",
    "mid_flower": "CalMag+ 2.5, Micro 2.5, Gro 1.25, Bloom 3.75, Hydroguard 2",
    "late_flower": "CalMag+ 2.5, Micro 1.25, Gro 0, Bloom 3.75, Hydroguard 2",
}

_POST_HARVEST_STAGES = frozenset({"harvest", "dry", "cure", "ready"})
_HYDRO_TYPES = frozenset({"rdwc", "dwc"})
_EC_TREND_NOISE = 0.05


def _build_nutrient_reference(
    nutrient_line: str, base_nutrients: str, stage: str
) -> str:
    """Return the current-stage Flora mix when that line is detected.

    The rates are a light feed chosen for this integration. GH's published
    late-growth medium column is FloraMicro 6.0, FloraGro 5.6, FloraBloom
    4.2 ml/gal at about EC 1.4-1.7. Botanicare Cal-Mag Plus is labeled
    5 ml (1 tsp) per gallon. Hydroguard is labeled 2 ml/gal.
    """
    combined = f"{nutrient_line} {base_nutrients}".lower()
    if not any(kw in combined for kw in _GH_FLORA_KEYWORDS):
        return ""
    if stage == "flush":
        return (
            "\nNutrient line is General Hydroponics Flora, but the current "
            "stage is flush. Ignore Flora rates. The only step is plain water. "
            "Do not add Hydroguard to a plain-water change.\n"
        )
    rates = _FLORA_RATES_ML_PER_GAL.get(stage)
    if not rates:
        return (
            "\nNutrient line is General Hydroponics Flora. This stage has no "
            "reservoir recipe. Do not invent ml/gal rates.\n"
        )
    return (
        "\nNutrient reference for this stage only. These ml/gal rates are a "
        "deliberate light feed, under General Hydroponics' published charts. "
        "They are not the GH Light, Medium, or Aggressive schedule. GH's "
        "published late-growth medium column is FloraMicro 6.0, FloraGro 5.6, "
        "FloraBloom 4.2 ml/gal, with a stated EC of about 1.4-1.7 mS/cm. GH "
        "bloom medium weeks go to about EC 2.0-2.4. Do not use those rates "
        "and do not scale this mix up toward a GH chart.\n"
        f"  Current stage '{stage}' ml/gal: {rates}\n"
        "  Print only this stage. The operator additives field is the extra "
        "product list. Print the product names the operator used. If they "
        "listed CalMag+, print CalMag+. Do not rename CalMag+ to CALiMAGic, "
        "and do not add both. If they listed CALiMAGic, use that bottle in "
        "this Cal-Mag slot. Do not add Armor Si, RapidStart, Floralicious "
        "Plus, or Liquid KoolBloom unless that product is listed.\n"
        "  CalMag+ at 2.5 ml/gal is half of Botanicare Cal-Mag Plus's label "
        "rate of 5 ml (1 tsp) per gallon. Add it after water and before "
        "FloraMicro. Do not stack another 5 ml/gal on top. On RO, distilled, "
        "or rain water, if new growth shows a calcium deficiency, raise "
        "CalMag+ toward 5 ml/gal before raising any Flora part, and still "
        "stay at or below the active EC high. On hard tap, well, or spring "
        "water, do not add the full Cal-Mag rate by default.\n"
        "  Hydroguard (Botanicare) at 2 ml/gal is the label rate. Add it after "
        "the base nutrients and before pH on a nutrient fill. Never combine "
        "it with H2O2, HOCl, or other oxidizers. Do not drop CalMag+ or "
        "Hydroguard off a nutrient fill.\n"
        "  Listed extras only: Armor Si 2 ml/gal through late flower, first "
        "in the water; RapidStart 1 ml/gal from seedling through veg; "
        "Floralicious Plus 1 ml/gal from veg through mid flower; Liquid "
        "KoolBloom 2.5 ml/gal in late flower only.\n"
        "  If this mix would measure above the active EC high, lower the "
        "Flora ml/gal rates. Pale plants may step vegetative Flora from 2.5 "
        "toward 3.5 ml/gal of each part, still under the active EC high. "
        "Dark leaves or burnt tips: lower the Flora rates and keep Hydroguard "
        "at 2 ml/gal.\n"
        "  Mixing order: Armor Si only if listed, then CalMag+ or CALiMAGic, "
        "then FloraMicro, then FloraGro, then FloraBloom, then RapidStart, "
        "Floralicious, or KoolBloom when listed, then Hydroguard, then pH "
        "last. Do not print an estimated EC. EC is known only after the "
        "operator measures the mixed reservoir.\n"
        "  Do not treat current EC as underfeeding when it is inside the "
        "active EC band.\n"
    )


def _water_source_guidance(water_type: str) -> str:
    """Brief makeup-water grounding for dosing when water_type is set."""
    if not water_type:
        return ""
    if water_type in {"ro", "distilled", "rain"}:
        return (
            f" Makeup water type is '{water_type}' (near-zero mineral "
            "baseline). Prioritize Cal-Mag / calcium-magnesium "
            "supplementation and do not assume municipal mineral content."
        )
    if water_type in {"tap", "well", "spring"}:
        return (
            f" Makeup water type is '{water_type}'. Account for baseline "
            "minerals and possible chlorine/chloramine; prefer resting or "
            "carbon-filtering before mix when chlorine is a concern, and "
            "reduce Cal-Mag if source water is already hard."
        )
    if water_type in {"filtered", "bottled", "mixed"}:
        return (
            f" Makeup water type is '{water_type}'. Treat mineral content as "
            "intermediate/unknown unless source EC or hardness is provided; "
            "ask for clarification rather than assuming full RO or hard tap."
        )
    return f" Makeup water type is '{water_type}'."


_LIVE_KEYWORDS = (
    "hydroguard",
    "great white",
    "southern ag",
    "beneficial",
    "bacillus",
    "inoculant",
    "mycorrhiza",
    "microbe",
    "microbes",
    "rooters",
    "cannazym",
    "bacteria",
)
_STERILE_KEYWORDS = (
    "h2o2",
    "hydrogen peroxide",
    "uc roots",
    "hypochlorous",
    "hocl",
    "bleach",
    "sterile",
    "sterilant",
    "physan",
    "zerotol",
    "chlorine dioxide",
)


def classify_reservoir_biology(
    grow_type: str, additives: str, extra_text: str = ""
) -> str:
    """Classify reservoir strategy: live, sterile, mixed, or unknown.

    Live if biological additives (Hydroguard, etc.) are listed, or if the grow
    type is RDWC/DWC and no sterilant is listed. Sterile if oxidizers are
    listed without biologicals.
    """
    blob = f"{additives} {extra_text}".lower()
    grow = grow_type.strip().lower()
    live = any(key in blob for key in _LIVE_KEYWORDS)
    sterile = any(key in blob for key in _STERILE_KEYWORDS)
    if live and sterile:
        return "mixed"
    if live:
        return "live"
    if sterile:
        return "sterile"
    if grow in _HYDRO_TYPES:
        return "live"
    return "unknown"


def _reservoir_biology_guidance(mode: str) -> str:
    """Ground ORP/temp/DO advice. Numbers from named trusted sources."""
    shared_temp = (
        "Reservoir water temperature for DWC/RDWC: target 65-68 F (18-20 C). "
        "65 F is in-range, not an upper limit. Prefer this cooler band for "
        "flower quality over pushing warmer water for growth rate. "
        "USGS Benson-Krause DO saturation is ~9.5 mg/L at 18 C and ~9.1 mg/L "
        "at 20 C. University of Missouri Extension: measure DO separately "
        "(optimum >6 ppm); ORP is NOT dissolved oxygen. "
        "Flag water temperature as a concern only at or above 72 F / 22 C "
        "(University of Kentucky / Colorado State root-disease guidance) and "
        "as high-risk at or above 77 F / 25 C (Sutton et al., Pythium). "
        "Do not write an Issue for 65-68 F water.\n"
    )
    vpd_ec = (
        "Air VPD is computed from air temperature and humidity. It is not "
        "leaf VPD. No leaf-temperature sensor is present. Vegetative air VPD "
        "of 0.70-1.20 kPa is acceptable. Do not flag air VPD as an Issue when "
        "it is inside the active band, or within 0.1 kPa of that band. The "
        "built-in late-flower and flush VPD of 1.3-1.6 kPa is a drier "
        "mold-avoidance range, not a proven terpene target. Warm air with "
        "low humidity is a flower-quality problem even when air VPD sits in "
        "that range.\n"
        "EC: the active EC band in this prompt is the only band. Do not "
        "diagnose underfeeding when current EC is inside it. In recirculating "
        "water, rising EC means the reservoir is concentrating because the "
        "plants are taking up more water than nutrients. Top off with "
        "lower-EC water. Do not add nutrients because EC rose. Falling EC "
        "means nutrient uptake is ahead of water uptake.\n"
    )
    if mode == "live":
        return (
            "Reservoir biology: LIVE (beneficial bacteria / Hydroguard "
            "detected, or RDWC/DWC without a sterilant). Botanicare "
            "Hydroguard is Bacillus amyloliquefaciens at 2 ml/gal; it is "
            "incompatible with H2O2/HOCl/oxidizers.\n"
            "ORP (Apera Instruments hydroponics guide): sterile disinfection "
            "with H2O2/ozone/chlorine is 650-850 mV — do NOT apply that "
            "target to a live system. Balanced microbial activity is "
            "300-500 mV; anaerobic risk is <200 mV. "
            "ORP of ~200-300 mV on a live RDWC is acceptable/watch, NOT "
            "critically low, NOT poor dissolved oxygen, and NOT by itself "
            "a root-disease alarm. Only flag ORP <200 mV, or ORP plus "
            "actual visual root-rot symptoms.\n"
            f"{shared_temp}{vpd_ec}"
        )
    if mode == "sterile":
        return (
            "Reservoir biology: STERILE (oxidizer such as H2O2/HOCl "
            "listed). Apera Instruments: disinfection ORP 650-850 mV. "
            "Do not recommend Hydroguard or other biologicals while an "
            "oxidizer is in the reservoir.\n"
            f"{shared_temp}{vpd_ec}"
        )
    if mode == "mixed":
        return (
            "Reservoir biology: MIXED signals (biologicals and an oxidizer "
            "are both listed). These strategies cancel each other — oxidizers "
            "kill Bacillus. Ask the operator which strategy they intend; do "
            "not apply sterile ORP >650 mV as a live-system failure.\n"
            f"{shared_temp}{vpd_ec}"
        )
    return (
        "Reservoir biology: not specified. Do not assume sterile ORP "
        "targets (650-850 mV) unless additives include an oxidizer.\n"
        f"{shared_temp}{vpd_ec}"
    )


@dataclass(slots=True)
class AIHealthResult:
    """Single AI health-check result for one grow entry."""

    checked_at: datetime
    score: int | None
    severity: str
    summary: str
    issues: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    feeding_schedule: list[str] = field(default_factory=list)
    confidence: int | None = None
    confidence_rationale: str = ""
    provider: str = ""
    model: str = ""
    reason: str = ""
    raw_response: str = ""
    telemetry: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checked_at"] = self.checked_at.isoformat()
        return payload

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> AIHealthResult:
        checked_at = datetime.now(UTC)
        raw_checked_at = value.get("checked_at")
        if isinstance(raw_checked_at, str):
            try:
                checked_at = datetime.fromisoformat(raw_checked_at)
                if checked_at.tzinfo is None:
                    checked_at = checked_at.replace(tzinfo=UTC)
            except ValueError:
                checked_at = datetime.now(UTC)

        return cls(
            checked_at=checked_at,
            score=value.get("score"),
            severity=str(value.get("severity", "unknown")),
            summary=str(value.get("summary", "")),
            issues=list(value.get("issues", []) or []),
            recommended_actions=list(value.get("recommended_actions", []) or []),
            observations=list(value.get("observations", []) or []),
            feeding_schedule=list(value.get("feeding_schedule", []) or []),
            confidence=value.get("confidence"),
            confidence_rationale=str(value.get("confidence_rationale", "")),
            provider=str(value.get("provider", "")),
            model=str(value.get("model", "")),
            reason=str(value.get("reason", "")),
            raw_response=str(value.get("raw_response", "")),
            telemetry=_telemetry_from_storage(value.get("telemetry")),
        )


@dataclass(slots=True)
class AIHealthState:
    """In-memory and persisted state for one grow entry."""

    latest: AIHealthResult | None = None
    history: list[AIHealthResult] = field(default_factory=list)
    last_error: str = ""
    running: bool = False


def ai_dispatcher_signal(entry_id: str) -> str:
    """Dispatcher signal for AI health updates."""
    return f"{DOMAIN}_ai_health_update_{entry_id}"


async def load_history(store: Store[dict[str, Any]]) -> list[AIHealthResult]:
    """Load persisted history from HA storage."""
    payload = await store.async_load() or {}
    rows = payload.get("results", [])
    if not isinstance(rows, list):
        return []
    return [AIHealthResult.from_dict(row) for row in rows if isinstance(row, dict)]


async def persist_history(
    store: Store[dict[str, Any]], history: list[AIHealthResult]
) -> None:
    """Persist health-check history."""
    await store.async_save({"results": [item.to_dict() for item in history]})


def _entry_merged_config(entry: ConfigEntry) -> dict[str, Any]:
    merged = dict(entry.data)
    merged.update(entry.options)
    return merged


_EQUIPMENT_LABELS: dict[str, str] = {
    CONTROL_ROLE_LIGHTS: "Lights",
    CONTROL_ROLE_FANS: "Circulation fans",
    CONTROL_ROLE_INLINE_FANS: "Exhaust fan",
    CONTROL_ROLE_RDWC_PUMP: "RDWC circulation pump",
    CONTROL_ROLE_CHILLER_PUMP: "Chiller pump",
    CONTROL_ROLE_AIR_PUMP: "Air pump",
}


def _telemetry_from_storage(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): str(item) for key, item in value.items() if item not in (None, "")
    }


def _metric_display(payload: Any) -> str:
    if isinstance(payload, tuple):
        value = payload[0]
        unit = payload[1] if len(payload) > 1 else ""
        return f"{value} {unit}".strip()
    return str(payload)


def _leading_number(value: Any) -> float | None:
    if isinstance(value, tuple):
        value = value[0]
    text = str(value if value is not None else "").strip()
    token: list[str] = []
    started = False
    for char in text:
        if char.isdigit() or (char == "." and started) or (char == "-" and not started):
            token.append(char)
            started = True
        elif started:
            break
    if not token or token in (["-"], ["."], ["-."]):
        return None
    return _coerce_metric_float("".join(token))


def _bound_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"unknown", "unavailable", "none"}:
        return None
    return _coerce_metric_float(text)


def _active_range(
    context: dict[str, Any],
    low_key: str,
    high_key: str,
    stage: str,
    stage_field: str,
) -> tuple[str, str]:
    """Operator low/high wins. The built-in stage row is only the fallback."""
    low = _bound_float(context.get(low_key))
    high = _bound_float(context.get(high_key))
    if low is not None and high is not None and high >= low:
        return f"{low:g}-{high:g}", "operator band"
    raw = STAGE_TARGETS.get(stage, {}).get(stage_field)
    if raw:
        return str(raw), "built-in stage default"
    return "not set", "none"


def _fahrenheit(unit: str | None) -> bool:
    normalized = (unit or "").strip().lower().replace("\u00b0", "")
    return normalized in {"f", "fahrenheit"}


def _derived_snapshot(
    metrics: dict[str, Any], context: dict[str, Any]
) -> dict[str, str]:
    derived: dict[str, str] = {}
    air_temp = metrics.get(SENSOR_ROLE_TEMPERATURE)
    air_hum = metrics.get(SENSOR_ROLE_HUMIDITY)
    if isinstance(air_temp, tuple) and isinstance(air_hum, tuple):
        temp_value = _coerce_metric_float(air_temp[0])
        humidity = _coerce_metric_float(air_hum[0])
        vpd = GrowSpace.compute_vpd_kpa(temp_value, air_temp[1], humidity)
        if vpd is not None:
            derived["vpd_kpa"] = f"{round(vpd, 2)} kPa"
        dew_c = compute_dew_point_c(
            GrowSpace.to_celsius(temp_value, air_temp[1]), humidity
        )
        if dew_c is not None:
            if _fahrenheit(str(air_temp[1])):
                derived["dew_point"] = (
                    f"{round(dew_c * 9.0 / 5.0 + 32.0, 1)} {air_temp[1]}"
                )
            else:
                derived["dew_point"] = f"{round(dew_c, 1)} {air_temp[1] or 'C'}"
    light = metrics.get(SENSOR_ROLE_LIGHT)
    ppfd = _leading_number(light) if light is not None else None
    hours = _bound_float(context.get("lights_on_hours"))
    dli = compute_dli(ppfd, hours)
    if dli is not None:
        derived["dli_mol_m2_d"] = f"{dli:.1f} mol/m^2/day"
    return derived


def _snapshot_telemetry(
    metrics: dict[str, Any], context: dict[str, Any]
) -> dict[str, str]:
    snapshot = {
        role: _metric_display(payload)
        for role, payload in metrics.items()
        if _metric_display(payload)
    }
    snapshot.update(_derived_snapshot(metrics, context))
    return snapshot


def _metric_lines(metrics: dict[str, Any], context: dict[str, Any]) -> str:
    entries: list[str] = []
    for role, payload in sorted(metrics.items()):
        value, unit = payload if isinstance(payload, tuple) else (payload, "")
        label = METRIC_ROLE_LABELS.get(role, role)
        unit_suffix = f" {unit}" if unit else ""
        entries.append(f"- {label}: {value}{unit_suffix}")
    derived = _derived_snapshot(metrics, context)
    if "vpd_kpa" in derived:
        entries.append(
            "- Derived VPD (air temperature + air humidity, not leaf VPD): "
            f"{derived['vpd_kpa']}"
        )
    if "dew_point" in derived:
        entries.append(
            "- Derived dew point (from air temperature and humidity): "
            f"{derived['dew_point']}"
        )
    if "dli_mol_m2_d" in derived:
        entries.append(
            "- Derived DLI (current PPFD x lights-on hours; estimate, not an "
            f"integrated light measurement): {derived['dli_mol_m2_d']}"
        )
    if not entries:
        return "- no telemetry available"
    lines = "\n".join(entries)
    if "ec" in metrics and ("tds" in metrics or "cf" in metrics):
        lines += (
            "\nEC is the dosing authority. CF and TDS ppm depend on the meter "
            "scale (500 vs 700) and are not a second diagnosis when EC is present."
        )
    return lines


def _parse_clock(value: Any) -> time | None:
    raw = str(value or "").strip()
    parts = raw.split(":")
    if len(parts) < 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) > 2 and parts[2] else 0
    except ValueError:
        return None
    if hour > 23 or minute > 59 or second > 59 or min(hour, minute, second) < 0:
        return None
    return time(hour, minute, second)


def _lights_are_on(now_t: time, on: time, off: time) -> bool:
    now_minutes = now_t.hour * 60 + now_t.minute
    on_minutes = on.hour * 60 + on.minute
    off_minutes = off.hour * 60 + off.minute
    if off_minutes == on_minutes:
        return False
    if off_minutes < on_minutes:
        return now_minutes >= on_minutes or now_minutes < off_minutes
    return on_minutes <= now_minutes < off_minutes


def _schedule_block(context: dict[str, Any], now: datetime | None) -> str:
    on_time = _parse_clock(context.get("lights_on_time"))
    off_time = _parse_clock(context.get("lights_off_time"))
    if on_time is None or off_time is None or now is None:
        return ""
    now_t = time(now.hour, now.minute, now.second)
    phase = "lights-on" if _lights_are_on(now_t, on_time, off_time) else "lights-off"
    return (
        f"Local time at check: {now_t.strftime('%H:%M')}. "
        f"Scheduled lights-on {on_time.strftime('%H:%M')} to lights-off "
        f"{off_time.strftime('%H:%M')}. This reading is in the scheduled "
        f"{phase} period.\n"
    )


def _equipment_block(equipment: dict[str, str] | None) -> str:
    if not equipment:
        return "Equipment state: not provided.\n"
    lines = "\n".join(f"- {name}: {state}" for name, state in sorted(equipment.items()))
    return (
        "Equipment state (switch state at check time):\n"
        f"{lines}\n"
        "If the air pump or the RDWC circulation pump is off, that is a "
        "root-zone problem. If the lights switch disagrees with the light "
        "schedule, trust the switch for whether the lights are on now and say "
        "that they disagree.\n"
    )


def _collect_equipment_states(
    hass: HomeAssistant, grow_space: GrowSpace
) -> dict[str, str]:
    states: dict[str, str] = {}
    for role, entity_id in grow_space.control_mappings.items():
        if not entity_id:
            continue
        label = _EQUIPMENT_LABELS.get(role, role)
        state = hass.states.get(entity_id)
        states[label] = "unavailable" if state is None else str(state.state)
    return states


def _ec_trend_line(
    metrics: dict[str, Any], prior_telemetry: dict[str, str] | None
) -> str:
    if not prior_telemetry:
        return "EC trend: no previous snapshot. Do not invent a rise or fall.\n"
    previous = _leading_number(prior_telemetry.get("ec"))
    current_payload = metrics.get("ec")
    if current_payload is None or previous is None:
        return "EC trend: no comparable EC pair. Do not invent a rise or fall.\n"
    current = _leading_number(current_payload)
    if current is None:
        return "EC trend: no comparable EC pair. Do not invent a rise or fall.\n"
    previous_display = str(prior_telemetry.get("ec"))
    current_display = _metric_display(current_payload)
    delta = current - previous
    if abs(delta) < _EC_TREND_NOISE:
        detail = (
            f"EC is steady ({previous_display} to {current_display}). "
            "A change under 0.05 mS/cm is treated as meter noise."
        )
    elif delta > 0:
        detail = (
            f"EC has risen from {previous_display} to {current_display}. "
            "In recirculating water the reservoir is concentrating: the plants "
            "are taking up more water than nutrients. Top off with lower-EC "
            "water. Do not add nutrients because EC rose."
        )
    else:
        detail = (
            f"EC has fallen from {previous_display} to {current_display}. "
            "Nutrient uptake is ahead of water uptake. Raise the mix only if "
            "the plant is pale and EC is under the active band."
        )
    return f"EC trend: {detail}\n"


def _prior_block(
    prior_telemetry: dict[str, str] | None, prior_checked_at: str | None
) -> str:
    if not prior_telemetry:
        return "Previous telemetry snapshot: none.\n"
    lines = "\n".join(
        f"- {METRIC_ROLE_LABELS.get(key, key)}: {value}"
        for key, value in sorted(prior_telemetry.items())
    )
    when = f" from {prior_checked_at}" if prior_checked_at else ""
    return f"Previous telemetry snapshot{when}:\n{lines}\n"


def _dosing_line(grow_type: str, volume: str, site_count: str, stage: str) -> str:
    hydro = grow_type.strip().lower() in _HYDRO_TYPES
    sites = (
        f" The system has {site_count} plant sites sharing one reservoir."
        if site_count
        else ""
    )
    if volume and hydro:
        line = (
            f"Total system volume provided: {volume} gallons.{sites} "
            "This is the TOTAL circulating water volume (all buckets + control "
            "reservoir + connecting lines), not a single bucket. Compute TOTAL "
            f"milliliters as the ml/gal rate times {volume} and label them "
            f"'TOTAL for {volume} gal system'. Dose a fresh fill for this same "
            "volume. If the volume looks too small for the site count, ask the "
            "operator to confirm it."
        )
    elif volume:
        line = (
            f"Volume provided: {volume} gallons.{sites} Dose for that volume. "
            f"Grow type is '{grow_type or 'unspecified'}'. Do not describe this "
            "grow as a recirculating RDWC system."
        )
    elif hydro:
        line = (
            "Reservoir volume not provided. Give per-gallon rates and say that "
            "total milliliters need the full system volume (all buckets + "
            "reservoir + lines)."
        )
    else:
        line = (
            "Volume not provided. Give per-gallon rates only. Do not invent a "
            "system volume."
        )
    if stage == "flush":
        line += (
            " Current stage is flush. The only feed step is plain water for "
            "the stated volume. Do not add nutrients or Hydroguard. Do not "
            "claim this improves cannabinoids, terpenes, or smoothness."
        )
    return line


def _build_prompt(
    grow_space: GrowSpace,
    metrics: dict[str, Any],
    context: dict[str, Any],
    *,
    retention_days: int,
    equipment: dict[str, str] | None = None,
    prior_telemetry: dict[str, str] | None = None,
    prior_checked_at: str | None = None,
    now: datetime | None = None,
) -> str:
    _enrich_stage_clock(context)
    metric_lines = _metric_lines(metrics, context)
    context_lines = "\n".join(
        f"- {key}: {value}" for key, value in sorted(context.items())
    )
    stage = str(context.get("growth_stage", "")).strip().lower()
    objective = STAGE_OBJECTIVES.get(stage, DEFAULT_OBJECTIVE)
    nutrient_line = str(context.get("nutrient_line", ""))
    base_nutrients = str(context.get("base_nutrients", ""))
    nutrient_ref = _build_nutrient_reference(nutrient_line, base_nutrients, stage)
    reservoir_volume = str(context.get("reservoir_volume_gal", "")).strip()
    site_count = str(context.get("site_count_plants", "")).strip()
    target_ec = str(context.get("target_ec_ms_cm", "")).strip()
    target_ph = str(context.get("target_ph", "")).strip()
    water_type = str(context.get("water_type", "")).strip().lower()
    additives = str(context.get("additives", ""))
    ph_band, ph_source = _active_range(
        context, "target_ph_low", "target_ph_high", stage, "ph"
    )
    ec_band, ec_source = _active_range(
        context, "target_ec_low", "target_ec_high", stage, "ec_ms_cm"
    )
    vpd_band, vpd_source = _active_range(
        context, "target_vpd_low_kpa", "target_vpd_high_kpa", stage, "vpd_kpa"
    )
    grow_type = str(grow_space.grow_type or "")
    dosing_line = _dosing_line(grow_type, reservoir_volume, site_count, stage)
    if target_ec:
        dosing_line += (
            f" Fresh-mix EC must measure at or below {target_ec} mS/cm and "
            "inside the active EC band. If those disagree, the active EC band "
            "wins. Do not print an estimated EC."
        )
    if target_ph:
        dosing_line += (
            f" Fresh-mix pH aim is {target_ph}, adjusted after nutrients are "
            "mixed, and it must land inside the active pH band."
        )
    biology_guidance = _reservoir_biology_guidance(
        classify_reservoir_biology(
            grow_type, additives, f"{nutrient_line} {base_nutrients}"
        )
    )
    vpd_note = ""
    if stage in {"late_flower", "flush"} and vpd_source == "built-in stage default":
        vpd_note = (
            " The built-in VPD high end is a mold-avoidance range, not a "
            "terpene target. Do not treat 1.6 kPa as the quality goal."
        )
    legacy = ""
    if grow_space.schedules:
        legacy += (
            "Configured schedules: "
            f"{json.dumps(grow_space.schedules, sort_keys=True)}\n"
        )
    if grow_space.targets:
        legacy += (
            "Legacy configured targets (active bands above win if they differ): "
            f"{json.dumps(grow_space.targets, sort_keys=True)}\n"
        )
    data_block = (
        f"Stored results are kept for {retention_days} days. This prompt "
        "includes only the previous telemetry snapshot, not the full history.\n"
        f"Grow Space: {grow_space.name}\n"
        f"Grow Type: {grow_type or 'n/a'}\n"
        f"Descriptor: {grow_space.descriptor or 'n/a'}\n"
        f"{legacy}"
        f"{_schedule_block(context, now)}"
        f"{_equipment_block(equipment)}"
        "Cultivation context (operator-provided):\n"
        f"{context_lines if context_lines else '- none provided'}\n"
        "Current telemetry metrics:\n"
        f"{metric_lines}\n"
        f"{_ec_trend_line(metrics, prior_telemetry)}"
        f"{_prior_block(prior_telemetry, prior_checked_at)}"
    )
    header = (
        "You are a cannabis cultivation agronomist.\n"
        "Report only what the image, the telemetry, or the operator context "
        "supports. Label each claim as seen in the image, measured by a "
        "sensor, set by the operator, or recommended. If a number was not "
        "measured, say it is unknown. Do not invent products, EC, or citations.\n"
        "Mineral nutrient lines, including General Hydroponics Flora, are not "
        "organic flower. Do not call this crop organic.\n"
        "No CO2 sensor is available. Do not recommend a higher PPFD as if the "
        "room were CO2-enriched. If the canopy is bleached or tacoing, light "
        "is too high for this room.\n"
        f"Primary objective for the '{stage or 'unspecified'}' stage: "
        f"{objective}\n\n"
    )
    if stage in _POST_HARVEST_STAGES:
        return (
            f"{header}"
            "This stage is not on a reservoir. feeding_schedule must be an "
            "empty array. Do not discuss pH, EC, nutrients, ORP, or a feed mix.\n\n"
            "Return STRICT JSON only, no markdown, with keys:\n"
            "- score: integer 0-100 (health and quality of what is shown)\n"
            "- confidence: integer 0-100\n"
            "- confidence_rationale: one short sentence\n"
            "- severity: one of low, medium, high, critical\n"
            "- summary: one concise paragraph\n"
            "- observations: array of short visual findings from the image\n"
            "- issues: array of problems you can see or measure. Do not invent "
            "reservoir issues.\n"
            "- recommended_actions: array of short actions tied to a seen or "
            "measured fact\n"
            "- feeding_schedule: an empty array\n\n"
            "If the image is unusable or missing, set confidence low and say so.\n"
            "In dry and cure, use air humidity and dew point for mold risk when "
            "those measurements are present.\n\n"
            f"{data_block}"
        )

    active = (
        f"Active targets for '{stage or 'unspecified'}'. Score only against "
        "these. An operator band wins over the built-in stage default.\n"
        f"- pH {ph_band} ({ph_source})\n"
        f"- EC {ec_band} mS/cm ({ec_source})\n"
        f"- Air VPD {vpd_band} kPa ({vpd_source}).{vpd_note}\n"
    )
    return (
        f"{header}"
        f"{active}\n"
        "Return STRICT JSON only, no markdown, with keys:\n"
        "- score: integer 0-100 (plant health and quality trajectory). Do not "
        "lower the score for a value inside the active band.\n"
        "- confidence: integer 0-100\n"
        "- confidence_rationale: one short sentence naming the image and "
        "measurement limits\n"
        "- severity: one of low, medium, high, critical\n"
        "- summary: one concise paragraph\n"
        "- observations: array of short visual findings from the image only\n"
        "- issues: array of problems supported by the image or a measurement. "
        "Omit values inside the active band and the reservoir rules below. "
        "Never invent issues for 65-68 F water, live-system ORP of 200-300 mV, "
        "in-band EC, or air VPD within 0.1 kPa of the active band.\n"
        "- recommended_actions: array of short actions. Name the measurement "
        "each action responds to.\n"
        "- feeding_schedule: array with ONE string for the current stage, or "
        "an empty array when this stage has no feed. Format: "
        "'[PHASE] | ADD IN ORDER: [Product]: Xml (Xml/gal); [Product]: Xml "
        "(Xml/gal) | pH: X.X | NOTE: mix, then measure EC'. "
        "Use SEMICOLONS between products. Do not include an estimated EC. "
        "Mixing order: Armor Si only if the operator listed it, then CalMag+ "
        "or CALiMAGic, then FloraMicro, then FloraGro, then FloraBloom, then "
        "other listed extras, then Hydroguard, then pH last. Include TOTAL ml "
        "for the full system volume and the ml/gal rate. Include every "
        "additive the operator listed. A step that omits a listed additive, "
        "or adds a product they did not list, is wrong.\n\n"
        "Deficiency diagnosis rubric (use nutrient mobility):\n"
        "- Mobile nutrients (N, P, K, Mg, Zn): deficiencies appear on OLDER/lower "
        "leaves first.\n"
        "- Immobile nutrients (Ca, S, Fe, Mn, B, Cu): deficiencies appear "
        "on NEWER/upper leaves first.\n"
        "- Use symptom location plus the measured pH to separate deficiency "
        "from lockout. Do not call in-band EC underfeeding.\n\n"
        "Dosing rule:\n"
        f"- {dosing_line}"
        f"{_water_source_guidance(water_type)}"
        f"{nutrient_ref}\n"
        "Reservoir chemistry (use these numbers):\n"
        f"{biology_guidance}\n"
        "If the image is unusable or missing, set confidence low and say so. "
        "Do not fabricate.\n\n"
        f"{data_block}"
    )


def _extract_json_payload(text: str) -> dict[str, Any]:
    body = text.strip()
    if body.startswith("```"):
        body = body.strip("`")
        if body.startswith("json"):
            body = body[4:].strip()

    if body.startswith("{") and body.endswith("}"):
        return json.loads(body)

    start = body.find("{")
    end = body.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("json_not_found")
    return json.loads(body[start : end + 1])


def _coerce_result(
    raw_text: str, provider: str, model: str, reason: str
) -> AIHealthResult:
    checked_at = datetime.now(UTC)
    try:
        payload = _extract_json_payload(raw_text)
    except Exception:  # noqa: BLE001
        return AIHealthResult(
            checked_at=checked_at,
            score=None,
            severity="unknown",
            summary=raw_text.strip()[:280] or "No summary returned",
            issues=[],
            recommended_actions=[],
            observations=[],
            confidence=None,
            provider=provider,
            model=model,
            reason=reason,
            raw_response=raw_text,
        )

    raw_score = payload.get("score")
    score: int | None
    if raw_score is None:
        score = None
    else:
        try:
            score = max(0, min(100, int(raw_score)))
        except (TypeError, ValueError):
            score = None

    raw_confidence = payload.get("confidence")
    confidence: int | None
    if raw_confidence is None:
        confidence = None
    else:
        try:
            confidence = max(0, min(100, int(raw_confidence)))
        except (TypeError, ValueError):
            confidence = None

    severity = str(payload.get("severity", "unknown")).strip().lower() or "unknown"
    summary = str(payload.get("summary", "")).strip() or "No summary returned"
    confidence_rationale = str(payload.get("confidence_rationale", "")).strip()

    issues = [
        str(item).strip() for item in payload.get("issues", []) if str(item).strip()
    ]
    actions = [
        str(item).strip()
        for item in payload.get("recommended_actions", [])
        if str(item).strip()
    ]
    observations = [
        str(item).strip()
        for item in payload.get("observations", [])
        if str(item).strip()
    ]
    feeding_schedule = [
        str(item).strip()
        for item in payload.get("feeding_schedule", [])
        if str(item).strip()
    ]

    return AIHealthResult(
        checked_at=checked_at,
        score=score,
        severity=severity,
        summary=summary,
        issues=issues,
        recommended_actions=actions,
        observations=observations,
        feeding_schedule=feeding_schedule,
        confidence=confidence,
        confidence_rationale=confidence_rationale,
        provider=provider,
        model=model,
        reason=reason,
        raw_response=raw_text,
    )


def _collect_metric_state_values(
    hass: HomeAssistant, grow_space: GrowSpace
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for role, entity_id in grow_space.sensor_mappings.items():
        if not entity_id or role == SENSOR_ROLE_CAMERA:
            continue
        state = hass.states.get(entity_id)
        if state is None:
            continue
        unit = str(state.attributes.get("unit_of_measurement", "") or "")
        values[role] = (state.state, unit)
    return values


def _enrich_stage_clock(context: dict[str, Any]) -> None:
    """Overwrite week_in_stage from the stage-started date when present."""
    started = context.get("stage_started_on")
    if not started:
        return
    elapsed = days_in_stage(datetime.now(UTC), stage_started=started)
    context["days_in_stage"] = str(elapsed)
    context["week_in_stage"] = str(weeks_in_stage(elapsed))


def _collect_grow_context(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Read operator-provided cultivation context entities for this entry."""
    context: dict[str, Any] = {}
    try:
        from homeassistant.helpers import entity_registry as er

        registry = er.async_get(hass)
        registry_entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    except Exception:  # noqa: BLE001
        return context

    for reg_entry in registry_entries:
        unique_id = reg_entry.unique_id or ""
        for suffix, label in GROW_CONTEXT_LABELS.items():
            if not unique_id.endswith(suffix):
                continue
            state = hass.states.get(reg_entry.entity_id)
            if state is None:
                continue
            value = state.state
            if value in (None, "", "unknown", "unavailable"):
                continue
            context[label] = value
            break
    return context


async def run_ai_health_check(
    hass: HomeAssistant,
    entry: ConfigEntry,
    grow_space: GrowSpace,
    state: AIHealthState,
    store: Store[dict[str, Any]],
    *,
    reason: str,
) -> AIHealthResult:
    """Execute one AI health check and persist/update runtime state."""
    cfg = _entry_merged_config(entry)
    provider = str(cfg.get(CONF_AI_PROVIDER, PROVIDER_NONE)).strip().lower()
    model = str(cfg.get(CONF_AI_MODEL, "")).strip()
    retention_days = int(
        cfg.get(CONF_AI_RESULT_RETENTION_DAYS, DEFAULT_AI_RESULT_RETENTION_DAYS) or 30
    )
    threshold = int(
        cfg.get(CONF_AI_SEVERE_THRESHOLD, DEFAULT_AI_SEVERE_THRESHOLD) or 20
    )

    if provider == PROVIDER_NONE or not model:
        raise ProviderExecutionError("ai_provider_not_configured")

    camera_entity_id = str(
        grow_space.sensor_mappings.get(SENSOR_ROLE_CAMERA, "")
    ).strip()
    if not camera_entity_id:
        raise ProviderExecutionError("camera_entity_not_configured")

    metrics = _collect_metric_state_values(hass, grow_space)
    context = _collect_grow_context(hass, entry)
    prior_telemetry = None
    prior_checked_at = None
    if state.latest is not None and state.latest.telemetry:
        prior_telemetry = dict(state.latest.telemetry)
        prior_checked_at = state.latest.checked_at.isoformat()
    prompt = _build_prompt(
        grow_space,
        metrics,
        context,
        retention_days=retention_days,
        equipment=_collect_equipment_states(hass, grow_space),
        prior_telemetry=prior_telemetry,
        prior_checked_at=prior_checked_at,
        now=dt_util.now(),
    )

    state.running = True
    async_dispatcher_send(hass, ai_dispatcher_signal(entry.entry_id))
    try:
        image_bytes, mime_type = await _async_get_camera_snapshot(
            hass, camera_entity_id
        )
        raw_text = await generate_vision_health_report(
            hass,
            provider,
            model,
            {
                CONF_API_KEY: cfg.get(CONF_API_KEY, ""),
                CONF_BASE_URL: cfg.get(CONF_BASE_URL, ""),
            },
            prompt=prompt,
            image_bytes=image_bytes,
            mime_type=mime_type,
        )
        result = _coerce_result(raw_text, provider, model, reason)
        result.telemetry = _snapshot_telemetry(metrics, context)

        state.latest = result
        state.history.append(result)
        cutoff = datetime.now(UTC) - timedelta(days=max(1, retention_days))
        state.history = [item for item in state.history if item.checked_at >= cutoff]
        await persist_history(store, state.history)
        state.last_error = ""

        score = result.score if result.score is not None else 999
        notify_service = str(cfg.get(CONF_AI_NOTIFY_SERVICE, "")).strip()
        if score <= threshold:
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": f"TendrilGrow critical health risk: {grow_space.name}",
                    "message": f"Score {result.score}. {result.summary}",
                },
                blocking=False,
            )
            if notify_service and "." in notify_service:
                domain, service = notify_service.split(".", 1)
                await hass.services.async_call(
                    domain,
                    service,
                    {
                        "title": f"TendrilGrow critical health risk: {grow_space.name}",
                        "message": f"Score {result.score}. {result.summary}",
                        "data": {
                            "actions": [
                                {
                                    "action": f"TENDRILGROW_RUN_CHECK:{entry.entry_id}",
                                    "title": "Run check",
                                }
                            ]
                        },
                    },
                    blocking=False,
                )

        return result
    finally:
        state.running = False
        async_dispatcher_send(hass, ai_dispatcher_signal(entry.entry_id))


def has_critical_alert(entry: ConfigEntry, state: AIHealthState) -> bool:
    """Return True when latest score is at/under the configured critical threshold."""
    if state.latest is None or state.latest.score is None:
        return False
    cfg = _entry_merged_config(entry)
    threshold = int(
        cfg.get(CONF_AI_SEVERE_THRESHOLD, DEFAULT_AI_SEVERE_THRESHOLD) or 20
    )
    return state.latest.score <= threshold


async def _async_get_camera_snapshot(
    hass: HomeAssistant, camera_entity_id: str
) -> tuple[bytes, str]:
    """Capture a camera snapshot; fall back to proxy if lookup races at startup."""
    try:
        from homeassistant.components.camera import async_get_image

        image = await async_get_image(hass, camera_entity_id, timeout=20)
        return image.content, image.content_type or "image/jpeg"
    except Exception as first_err:  # noqa: BLE001
        state = hass.states.get(camera_entity_id)
        if state is None:
            raise first_err

        session = async_get_clientsession(hass)
        proxy_url = f"http://127.0.0.1:8123/api/camera_proxy/{camera_entity_id}"
        async with session.get(proxy_url) as resp:
            resp.raise_for_status()
            content = await resp.read()
            content_type = resp.headers.get("Content-Type", "image/jpeg")
        return content, content_type
