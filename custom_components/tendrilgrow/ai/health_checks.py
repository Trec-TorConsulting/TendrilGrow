"""AI health-check runtime helpers for TendrilGrow."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from ..const import (
    CONF_AI_MODEL,
    CONF_AI_NOTIFY_SERVICE,
    CONF_AI_PROVIDER,
    CONF_AI_RESULT_RETENTION_DAYS,
    CONF_AI_SEVERE_THRESHOLD,
    CONF_API_KEY,
    CONF_BASE_URL,
    DEFAULT_AI_RESULT_RETENTION_DAYS,
    DEFAULT_AI_SEVERE_THRESHOLD,
    DEFAULT_OBJECTIVE,
    DOMAIN,
    GROW_CONTEXT_LABELS,
    PROVIDER_NONE,
    SENSOR_ROLE_CAMERA,
    SENSOR_ROLE_HUMIDITY,
    SENSOR_ROLE_TEMPERATURE,
    STAGE_OBJECTIVES,
    STAGE_TARGETS,
)
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


def _build_nutrient_reference(nutrient_line: str, base_nutrients: str) -> str:
    """Return an EC-calibrated reference table when a known line is detected.

    Sources: GH official feed chart hub (generalhydroponics.com/pages/feedcharts)
    and GrowWeedEasy Flora Trio guide (featured in High Times, Ed Rosenthal).
    """
    combined = f"{nutrient_line} {base_nutrients}".lower()
    if any(kw in combined for kw in _GH_FLORA_KEYWORDS):
        return (
            "\nNutrient reference — GH Flora Series, recirculating DWC/RDWC "
            "(sources: GH official feed chart hub + GrowWeedEasy Flora Trio "
            "guide):\n"
            "EC-calibrated ml/gal for recirculating systems "
            "(NOT drain-to-waste max rates — those are 2-3x higher "
            "and yield 2.5-3.0 mS/cm, causing nutrient burn):\n"
            "  Seedling:   Micro 1.25 ml, Gro 1.25 ml, Bloom 1.25 ml"
            " -> est. 0.5-0.7 mS/cm\n"
            "  Veg:        Micro 2.5 ml,  Gro 2.5 ml,  Bloom 2.5 ml "
            " -> est. 1.0-1.2 mS/cm\n"
            "  Transition: Micro 5.0 ml,  Gro 5.0 ml,  Bloom 5.0 ml "
            " -> est. 1.6-2.0 mS/cm\n"
            "  Flowering:  Micro 5.0 ml,  Gro 2.5 ml,  Bloom 7.5 ml "
            " -> est. 1.4-1.8 mS/cm\n"
            "  CaliMagic:  5 ml/gal for RO/soft water; optional with tap\n"
            "  Hydroguard: 2 ml/gal preventative; 5 ml/gal if root rot\n"
            "Mixing order: CaliMagic -> Micro -> Gro -> Bloom; pH LAST.\n"
            "Hydro pH target: 5.5-6.5 (ideal 5.8-6.2).\n"
            "Interpolate rows to hit operator target EC exactly.\n"
        )
    return ""


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


def _build_prompt(
    grow_space: GrowSpace,
    metrics: dict[str, Any],
    context: dict[str, Any],
    *,
    retention_days: int,
) -> str:
    metric_entries: list[str] = []
    for role, payload in sorted(metrics.items()):
        value, unit = payload if isinstance(payload, tuple) else (payload, "")
        label = METRIC_ROLE_LABELS.get(role, role)
        unit_suffix = f" {unit}" if unit else ""
        metric_entries.append(f"- {label}: {value}{unit_suffix}")
    air_temp = metrics.get(SENSOR_ROLE_TEMPERATURE)
    air_hum = metrics.get(SENSOR_ROLE_HUMIDITY)
    if isinstance(air_temp, tuple) and isinstance(air_hum, tuple):
        vpd = GrowSpace.compute_vpd_kpa(
            _coerce_metric_float(air_temp[0]),
            air_temp[1],
            _coerce_metric_float(air_hum[0]),
        )
        if vpd is not None:
            metric_entries.append(
                f"- Derived VPD (air temperature + air humidity): {round(vpd, 2)} kPa"
            )
    metric_lines = "\n".join(metric_entries)
    context_lines = "\n".join(
        f"- {key}: {value}" for key, value in sorted(context.items())
    )
    schedules = grow_space.schedules or {}
    targets = grow_space.targets or {}

    stage = str(context.get("growth_stage", "")).strip().lower()
    objective = STAGE_OBJECTIVES.get(stage, DEFAULT_OBJECTIVE)
    stage_targets = STAGE_TARGETS.get(stage)
    if stage_targets:
        stage_target_line = (
            f"Calibration targets for current stage '{stage}': "
            f"pH {stage_targets['ph']}, EC {stage_targets['ec_ms_cm']} mS/cm, "
            f"VPD {stage_targets['vpd_kpa']} kPa."
        )
    else:
        stage_target_line = (
            "Calibration targets for current stage: not defined; "
            "infer from best practice."
        )

    full_target_table = "\n".join(
        f"- {name}: pH {vals['ph']}, EC {vals['ec_ms_cm']} mS/cm, "
        f"VPD {vals['vpd_kpa']} kPa"
        for name, vals in STAGE_TARGETS.items()
    )

    reservoir_volume = str(context.get("reservoir_volume_gal", "")).strip()
    site_count = str(context.get("site_count_plants", "")).strip()
    target_ec = str(context.get("target_ec_ms_cm", "")).strip()
    target_ph = str(context.get("target_ph", "")).strip()
    nutrient_line = str(context.get("nutrient_line", ""))
    base_nutrients = str(context.get("base_nutrients", ""))
    nutrient_ref = _build_nutrient_reference(nutrient_line, base_nutrients)
    water_type = str(context.get("water_type", "")).strip().lower()
    water_source_clause = _water_source_guidance(water_type)
    sites_clause = (
        f" The system has {site_count} plant sites/buckets sharing one "
        "circulating reservoir."
        if site_count
        else ""
    )
    ec_constraint = (
        f" OPERATOR TARGET EC IS {target_ec} mS/cm — you MUST calibrate "
        "per-gallon rates to achieve this post-mix EC, NOT manufacturer-maximum "
        "rates (which overshoot the target and cause nutrient burn). "
        "Back-calculate nutrient rates from this target EC; do NOT default to "
        "full-label rates unless the target EC explicitly requires it. "
        "Include your estimated post-mix EC alongside each recipe so the "
        "operator can verify it matches the target before mixing."
        if target_ec
        else ""
    )
    ph_constraint = (
        f" OPERATOR TARGET pH IS {target_ph} — adjust pH to this value after "
        "all nutrients are fully mixed."
        if target_ph
        else ""
    )
    dosing_line = (
        f"Total system volume provided: {reservoir_volume} gallons."
        f"{sites_clause} Treat this as the TOTAL circulating RDWC water "
        "volume (all buckets + control reservoir + connecting lines combined), "
        "NOT a single bucket. Compute TOTAL nutrient and additive amounts for "
        f"this full volume (per-gallon rate x {reservoir_volume} gallons) and "
        f"label them clearly as 'TOTAL for {reservoir_volume} gal system'."
        f"{ec_constraint}{ph_constraint} If you recommend a fresh reservoir "
        "fill, dose for this same total volume, not a smaller assumed fill. "
        "If this volume looks implausibly small for the stated site count, "
        "flag it and ask the operator to confirm the total system volume."
        if reservoir_volume
        else (
            "Reservoir volume not provided; give per-gallon rates and note "
            "total dosing needs the full system volume (all buckets + reservoir "
            "+ lines)."
        )
    )

    return (
        "You are a master cannabis cultivation agronomist.\n"
        "Analyze the attached grow image together with the telemetry and \n"
        "cultivation context.\n"
        f"Primary objective for the '{stage or 'unspecified'}' stage: "
        f"{objective}\n\n"
        "Return STRICT JSON only, no markdown, with keys:\n"
        "- score: integer 0-100 (overall plant health and quality trajectory)\n"
        "- confidence: integer 0-100 (your confidence given image and \n"
        "  telemetry quality)\n"
        "- confidence_rationale: one short sentence explaining the confidence \n"
        "  and score drivers\n"
        "- severity: one of low, medium, high, critical\n"
        "- summary: one concise paragraph\n"
        "- observations: array of short visual findings from the image\n"
        "- issues: array of short problem statements\n"
        "- recommended_actions: array of short, quality-first corrective actions\n"
        "- feeding_schedule: array of strings, one per phase/timing step. "
        "Format each entry as: "
        "'[PHASE] | ADD IN ORDER: [Product]: Xml (Xml/gal), ... "
        "| EST EC: X.X mS/cm | pH: X.X | [any key note]'. "
        "List every product in mixing application order "
        "(CalMag/CaMg first, then Micro, then Gro, then Bloom, "
        "then biologicals/additives like Hydroguard last). "
        "Include TOTAL ml for the full system volume AND ml/gal rate "
        "for each product. EC-calibrate to operator target, "
        "not manufacturer-max rates.\n\n"
        "Scoring calibration (score against these stage target ranges):\n"
        f"{full_target_table}\n"
        f"{stage_target_line}\n\n"
        "- Deficiency diagnosis rubric (use nutrient mobility to localize "
        "symptoms):\n"
        "- Mobile nutrients (N, P, K, Mg, Zn): deficiencies appear on "
        "OLDER/lower leaves first.\n"
        "- Immobile nutrients (Ca, S, Fe, Mn, B, Cu): deficiencies appear on "
        "NEWER/upper leaves first.\n"
        "- Use symptom location plus pH-driven lockout ranges to distinguish "
        "true deficiency from lockout.\n\n"
        "Dosing rule:\n"
        f"- {dosing_line}"
        f"{water_source_clause}"
        f"{nutrient_ref}\n\n"
        "Grounding rules:\n"
        "- If the image is unusable or missing, set confidence low and say so; "
        "do not fabricate.\n"
        "- Tie recommendations to the provided targets, feed schedule, "
        "strain, "
        "and nutrient context when relevant.\n"
        "- Prefer specific, actionable guidance (for example, raise pH to 5.9 "
        "or reduce EC to 1.4).\n\n"
        f"Grow Space: {grow_space.name}\n"
        f"Grow Type: {grow_space.grow_type}\n"
        f"Descriptor: {grow_space.descriptor or 'n/a'}\n"
        f"Configured Schedules: {json.dumps(schedules, sort_keys=True)}\n"
        f"Configured Targets: {json.dumps(targets, sort_keys=True)}\n"
        f"History Retention Window: {retention_days} days\n"
        "Cultivation context (operator-provided; includes strain, week-in-stage, "
        "reservoir volume, feed, nutrient plan, and makeup water type):\n"
        f"{context_lines if context_lines else '- none provided'}\n"
        "Current telemetry metrics:\n"
        f"{metric_lines if metric_lines else '- no telemetry available'}"
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
    prompt = _build_prompt(grow_space, metrics, context, retention_days=retention_days)

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
