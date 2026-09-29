"""AI health diagnostic and recommendation sensors for TendrilGrow."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util

from ..ai.health_checks import ai_dispatcher_signal
from ..const import DOMAIN
from ..entity import grow_device_info
from ..feeding import compose_feeding_schedule_md
from ..insights import compose_weekly_journal

_STATE_MAX_LENGTH = 255


def _compose_report(latest) -> str:
    """Build a human-readable markdown report from an AI health result."""
    score = latest.score if latest.score is not None else "n/a"
    confidence = (
        f", confidence {latest.confidence}%" if latest.confidence is not None else ""
    )
    lines: list[str] = [
        f"**Score {score}/100** — severity: {latest.severity}{confidence}"
    ]

    if getattr(latest, "confidence_rationale", ""):
        lines += ["", f"_{latest.confidence_rationale}_"]
    if latest.summary:
        lines += ["", latest.summary]
    if latest.observations:
        lines += [
            "",
            "**Observations**",
            *[f"- {item}" for item in latest.observations],
        ]
    if latest.issues:
        lines += ["", "**Issues**", *[f"- {item}" for item in latest.issues]]
    if latest.recommended_actions:
        lines += [
            "",
            "**Recommended actions**",
            *[f"- {item}" for item in latest.recommended_actions],
        ]

    return "\n".join(lines)


def _compose_feeding_schedule_md(latest) -> str:
    """Build a markdown feeding schedule from an AI health result."""
    return compose_feeding_schedule_md(getattr(latest, "feeding_schedule", None))


class AIHealthBaseSensor(SensorEntity):
    """Base class for AI health entities driven by runtime state."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _unsub_dispatcher = None

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, suffix: str, name: str
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_name = name

    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    async def async_added_to_hass(self) -> None:
        """Subscribe to AI health state updates."""

        @callback
        def _async_handle_update() -> None:
            self.async_write_ha_state()

        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            ai_dispatcher_signal(self._entry.entry_id),
            _async_handle_update,
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_dispatcher is not None:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None

    @property
    def extra_state_attributes(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None:
            return None
        latest = runtime.ai_health_state.latest
        if latest is None:
            attrs = {"running": runtime.ai_health_state.running}
            if runtime.ai_health_state.last_error:
                attrs["last_error"] = runtime.ai_health_state.last_error
            return attrs

        attrs = {
            "severity": latest.severity,
            "confidence": latest.confidence,
            "confidence_rationale": latest.confidence_rationale,
            "summary": latest.summary,
            "report": _compose_report(latest),
            "observations": latest.observations,
            "issues": latest.issues,
            "recommended_actions": latest.recommended_actions,
            "feeding_schedule": latest.feeding_schedule,
            "feeding_schedule_md": _compose_feeding_schedule_md(latest),
            "provider": latest.provider,
            "model": latest.model,
            "reason": latest.reason,
            "history_count": len(runtime.ai_health_state.history),
            "running": runtime.ai_health_state.running,
        }
        if runtime.ai_health_state.last_error:
            attrs["last_error"] = runtime.ai_health_state.last_error
        return attrs


class AIHealthScoreSensor(AIHealthBaseSensor):
    """Numeric AI health score for one grow space."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:heart-pulse"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "ai_health_score", "AI Health Score")

    @property
    def native_value(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None or runtime.ai_health_state.latest is None:
            return None
        return runtime.ai_health_state.latest.score


class AIHealthSummarySensor(AIHealthBaseSensor):
    """AI-generated summary string for one grow space."""

    _attr_icon = "mdi:text-box-search"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "ai_health_summary", "AI Health Summary")

    @property
    def native_value(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None or runtime.ai_health_state.latest is None:
            return None
        summary = runtime.ai_health_state.latest.summary or None
        if summary and len(summary) > _STATE_MAX_LENGTH:
            return summary[: _STATE_MAX_LENGTH - 3].rstrip() + "..."
        return summary


class AIFeedingScheduleSensor(AIHealthBaseSensor):
    """AI-generated dynamic feeding schedule for one grow space."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "ai_feeding_schedule", "AI Feeding Schedule")

    @property
    def native_value(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None or runtime.ai_health_state.latest is None:
            return None
        steps = runtime.ai_health_state.latest.feeding_schedule
        if not steps:
            return "No schedule yet"
        return f"{len(steps)} step plan"


class AIHealthLastCheckSensor(AIHealthBaseSensor):
    """Timestamp of the latest AI health check."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "ai_health_last_check", "AI Last Health Check")

    @property
    def native_value(self):
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if runtime is None or runtime.ai_health_state.latest is None:
            return None
        return runtime.ai_health_state.latest.checked_at


class AIWeeklyJournalSensor(AIHealthBaseSensor):
    """A weekly recap composed from the recorded AI health checks."""

    _attr_icon = "mdi:notebook-outline"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "ai_weekly_journal", "AI Weekly Journal")

    def _journal(self) -> dict[str, str]:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        state = getattr(runtime, "ai_health_state", None)
        history = getattr(state, "history", None) or []
        return compose_weekly_journal(history, dt_util.now())

    @property
    def native_value(self):
        return self._journal()["headline"][:255]

    @property
    def extra_state_attributes(self):
        return {"journal_markdown": self._journal()["markdown"]}
