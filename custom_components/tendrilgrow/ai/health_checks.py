"""AI health-check runtime helpers for TendrilGrow."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
import json
import logging
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
    DOMAIN,
    GROW_CONTEXT_LABELS,
    PROVIDER_NONE,
    SENSOR_ROLE_CAMERA,
    STAGE_TARGETS,
)
from ..models.grow import GrowSpace
from .providers import ProviderExecutionError, generate_vision_health_report

LOGGER = logging.getLogger(__name__)


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
    def from_dict(cls, value: dict[str, Any]) -> "AIHealthResult":
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


async def persist_history(store: Store[dict[str, Any]], history: list[AIHealthResult]) -> None:
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
    metric_lines = "\n".join(f"- {key}: {value}" for key, value in sorted(metrics.items()))
    context_lines = "\n".join(f"- {key}: {value}" for key, value in sorted(context.items()))
    schedules = grow_space.schedules or {}
    targets = grow_space.targets or {}

    stage = str(context.get("growth_stage", "")).strip().lower()
    stage_targets = STAGE_TARGETS.get(stage)
    if stage_targets:
        stage_target_line = (
            f"Calibration targets for current stage '{stage}': "
            f"pH {stage_targets['ph']}, EC {stage_targets['ec_ms_cm']} mS/cm, "
            f"VPD {stage_targets['vpd_kpa']} kPa."
        )
    else:
        stage_target_line = "Calibration targets for current stage: not defined; infer from best practice."

    full_target_table = "\n".join(
        f"- {name}: pH {vals['ph']}, EC {vals['ec_ms_cm']} mS/cm, VPD {vals['vpd_kpa']} kPa"
        for name, vals in STAGE_TARGETS.items()
    )

    reservoir_volume = str(context.get("reservoir_volume_gal", "")).strip()
    site_count = str(context.get("site_count_plants", "")).strip()
    sites_clause = (
        f" The system has {site_count} plant sites/buckets sharing one circulating reservoir."
        if site_count
        else ""
    )
    dosing_line = (
        f"Total system volume provided: {reservoir_volume} gallons.{sites_clause} "
        "Treat this as the TOTAL circulating RDWC water volume (all buckets + control reservoir + connecting lines combined), "
        "NOT a single bucket. Compute TOTAL nutrient and additive amounts for this full volume "
        f"(per-gallon rate x {reservoir_volume} gallons) and label them clearly as 'TOTAL for {reservoir_volume} gal system'. "
        "If you recommend a fresh reservoir fill, dose for this same total volume, not a smaller assumed fill. "
        "If this volume looks implausibly small for the stated site count, flag it and ask the operator to confirm the total system volume."
        if reservoir_volume
        else "Reservoir volume not provided; give per-gallon rates and note total dosing needs the full system volume (all buckets + reservoir + lines)."
    )

    return (
        "You are a master cannabis cultivation agronomist specializing in premium flower quality.\n"
        "Analyze the attached grow image together with the telemetry and cultivation context.\n"
        "Prioritize QUALITY (terpene and cannabinoid expression, plant structure, health) over raw yield.\n\n"
        "Return STRICT JSON only, no markdown, with keys:\n"
        "- score: integer 0-100 (overall plant health and quality trajectory)\n"
        "- confidence: integer 0-100 (your confidence given image and telemetry quality)\n"
        "- confidence_rationale: one short sentence explaining the confidence and score drivers\n"
        "- severity: one of low, medium, high, critical\n"
        "- summary: one concise paragraph\n"
        "- observations: array of short visual findings from the image\n"
        "- issues: array of short problem statements\n"
        "- recommended_actions: array of short, quality-first corrective actions\n"
        "- feeding_schedule: array of short strings; a dynamic feeding plan tuned for highest-quality yield, "
        "each entry covering timing plus target EC, target pH, and TOTAL amounts of each nutrient/additive for the reservoir\n\n"
        "Scoring calibration (score against these stage target ranges):\n"
        f"{full_target_table}\n"
        f"{stage_target_line}\n\n"
        "Deficiency diagnosis rubric (use nutrient mobility to localize symptoms):\n"
        "- Mobile nutrients (N, P, K, Mg, Zn): deficiencies appear on OLDER/lower leaves first.\n"
        "- Immobile nutrients (Ca, S, Fe, Mn, B, Cu): deficiencies appear on NEWER/upper leaves first.\n"
        "- Use symptom location plus pH-driven lockout ranges to distinguish true deficiency from lockout.\n\n"
        "Dosing rule:\n"
        f"- {dosing_line}\n\n"
        "Grounding rules:\n"
        "- If the image is unusable or missing, set confidence low and say so; do not fabricate.\n"
        "- Tie recommendations to the provided targets, feed schedule, strain, and nutrient context when relevant.\n"
        "- Prefer specific, actionable guidance (for example, raise pH to 5.9 or reduce EC to 1.4).\n\n"
        f"Grow Space: {grow_space.name}\n"
        f"Grow Type: {grow_space.grow_type}\n"
        f"Descriptor: {grow_space.descriptor or 'n/a'}\n"
        f"Configured Schedules: {json.dumps(schedules, sort_keys=True)}\n"
        f"Configured Targets: {json.dumps(targets, sort_keys=True)}\n"
        f"History Retention Window: {retention_days} days\n"
        "Cultivation context (operator-provided; includes strain, week-in-stage, reservoir volume, feed and nutrient plan):\n"
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


def _coerce_result(raw_text: str, provider: str, model: str, reason: str) -> AIHealthResult:
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

    issues = [str(item).strip() for item in payload.get("issues", []) if str(item).strip()]
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


def _collect_metric_state_values(hass: HomeAssistant, grow_space: GrowSpace) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for role, entity_id in grow_space.sensor_mappings.items():
        if not entity_id or role == SENSOR_ROLE_CAMERA:
            continue
        state = hass.states.get(entity_id)
        if state is None:
            continue
        values[role] = state.state
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
    retention_days = int(cfg.get(CONF_AI_RESULT_RETENTION_DAYS, DEFAULT_AI_RESULT_RETENTION_DAYS) or 30)
    threshold = int(cfg.get(CONF_AI_SEVERE_THRESHOLD, DEFAULT_AI_SEVERE_THRESHOLD) or 20)

    if provider == PROVIDER_NONE or not model:
        raise ProviderExecutionError("ai_provider_not_configured")

    camera_entity_id = str(grow_space.sensor_mappings.get(SENSOR_ROLE_CAMERA, "")).strip()
    if not camera_entity_id:
        raise ProviderExecutionError("camera_entity_not_configured")

    metrics = _collect_metric_state_values(hass, grow_space)
    context = _collect_grow_context(hass, entry)
    prompt = _build_prompt(grow_space, metrics, context, retention_days=retention_days)

    state.running = True
    async_dispatcher_send(hass, ai_dispatcher_signal(entry.entry_id))
    try:
        image_bytes, mime_type = await _async_get_camera_snapshot(hass, camera_entity_id)
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
                    },
                    blocking=False,
                )

        return result
    finally:
        state.running = False
        async_dispatcher_send(hass, ai_dispatcher_signal(entry.entry_id))


def has_critical_alert(entry: ConfigEntry, state: AIHealthState) -> bool:
    """Return True when the latest score is at/under the configured critical threshold."""
    if state.latest is None or state.latest.score is None:
        return False
    cfg = _entry_merged_config(entry)
    threshold = int(cfg.get(CONF_AI_SEVERE_THRESHOLD, DEFAULT_AI_SEVERE_THRESHOLD) or 20)
    return state.latest.score <= threshold


async def _async_get_camera_snapshot(hass: HomeAssistant, camera_entity_id: str) -> tuple[bytes, str]:
    """Capture a camera snapshot; fall back to camera proxy if entity lookup races at startup."""
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
