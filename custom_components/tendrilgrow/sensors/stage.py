"""Growth stage tracking and projection sensors for TendrilGrow."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_registry import async_get as get_entity_registry
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from ..const import (
    CTX_STAGE,
    CTX_STAGE_STARTED,
    CTX_WEEK_IN_STAGE,
    DAYS_SINCE_FLIP_SUFFIX,
    DOMAIN,
    STAGE_DURATIONS_DAYS,
    STAGE_PIPELINE,
)
from ..entity import assign_prefixed_entity_id, grow_device_info
from ..insights import compute_days_since_flip, days_in_stage, weeks_in_stage


def resolve_stage_clock(
    hass: HomeAssistant, entry_id: str
) -> tuple[str | None, str | None, str | None]:
    """Return (stage, stage_started, week_in_stage) from current entity states."""
    registry = get_entity_registry(hass)

    def _state(domain: str, suffix: str) -> str | None:
        entity_id = registry.async_get_entity_id(domain, DOMAIN, f"{entry_id}_{suffix}")
        if not entity_id:
            return None
        state = hass.states.get(entity_id)
        if state is None or state.state in (None, "", "unknown", "unavailable"):
            return None
        return state.state

    stage = _state("select", CTX_STAGE)
    started = _state("date", CTX_STAGE_STARTED)
    week = _state("sensor", CTX_WEEK_IN_STAGE) or _state("number", CTX_WEEK_IN_STAGE)
    return stage, started, week


def compute_stage_projection(
    stage: str | None,
    week_in_stage: object,
    now: datetime,
    *,
    stage_started: object | None = None,
) -> dict[str, object | None]:
    """Project remaining days and milestone dates from stage + start date.

    `days_in_stage` prefers the stage-started date. Week-in-stage × 7 remains
    as a fallback for unmigrated data. Indefinite (`mother`) and terminal
    (`ready`) stages return no remaining days or dates.
    """
    stage = (stage or "").strip().lower()
    result: dict[str, object | None] = {
        "stage": stage or None,
        "days_in_stage": None,
        "days_remaining": None,
        "projected_stage_end": None,
        "projected_harvest_date": None,
        "projected_ready_date": None,
        "pipeline_position": None,
        "weeks_in_stage": None,
        "stage_started": None,
    }
    days_in = days_in_stage(
        now, stage_started=stage_started, week_in_stage=week_in_stage
    )
    result["days_in_stage"] = days_in
    result["weeks_in_stage"] = weeks_in_stage(days_in)
    if stage_started:
        result["stage_started"] = str(stage_started)[:10]
    if stage in STAGE_PIPELINE:
        result["pipeline_position"] = STAGE_PIPELINE.index(stage) + 1

    duration = STAGE_DURATIONS_DAYS.get(stage)
    if duration is None:
        return result

    days_remaining = max(0, duration - days_in)
    result["days_remaining"] = days_remaining
    result["projected_stage_end"] = (
        (now + timedelta(days=days_remaining)).date().isoformat()
    )

    def _project_to(target: str) -> str | None:
        if stage not in STAGE_PIPELINE or target not in STAGE_PIPELINE:
            return None
        start = STAGE_PIPELINE.index(stage)
        end = STAGE_PIPELINE.index(target)
        if end < start:
            return None
        total = days_remaining
        for name in STAGE_PIPELINE[start + 1 : end + 1]:
            step = STAGE_DURATIONS_DAYS.get(name)
            if step:
                total += step
        return (now + timedelta(days=total)).date().isoformat()

    result["projected_harvest_date"] = _project_to("harvest")
    result["projected_ready_date"] = _project_to("ready")
    return result


class TendrilGrowWeekInStageSensor(SensorEntity):
    """Computed weeks in the current stage from the Stage Started date."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Week In Stage"
    _attr_icon = "mdi:calendar-week"
    _attr_native_unit_of_measurement = "wk"
    _attr_suggested_display_precision = 1
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{CTX_WEEK_IN_STAGE}"
        self._unsub_state: object | None = None
        self._unsub_timer: object | None = None
        assign_prefixed_entity_id(self, hass, entry, "sensor", "week_in_stage")

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    def _source_entity_ids(self) -> list[str]:
        registry = get_entity_registry(self.hass)
        started_id = registry.async_get_entity_id(
            "date", DOMAIN, f"{self._entry.entry_id}_{CTX_STAGE_STARTED}"
        )
        return [started_id] if started_id else []

    def _days(self) -> int | None:
        _stage, started, _week = resolve_stage_clock(self.hass, self._entry.entry_id)
        if started is None:
            return None
        return days_in_stage(dt_util.now(), stage_started=started)

    @property
    def native_value(self):
        elapsed = self._days()
        if elapsed is None:
            return None
        return weeks_in_stage(elapsed)

    @property
    def extra_state_attributes(self):
        _stage, started, _week = resolve_stage_clock(self.hass, self._entry.entry_id)
        elapsed = self._days()
        return {
            "stage_started": started,
            "days_in_stage": elapsed,
        }

    @callback
    def _subscribe(self) -> None:
        if self._unsub_state is not None:
            return
        source_ids = self._source_entity_ids()
        if source_ids:
            self._unsub_state = async_track_state_change_event(
                self.hass, source_ids, self._async_source_changed
            )

    @callback
    def _async_source_changed(self, _event) -> None:
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        @callback
        def _refresh(*_args) -> None:
            self._subscribe()
            self.async_write_ha_state()

        self._subscribe()
        self._unsub_timer = async_track_time_interval(
            self.hass, _refresh, timedelta(hours=1)
        )
        async_call_later(self.hass, 15, _refresh)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None


class TendrilGrowStageProjectionSensor(SensorEntity):
    """Projected days remaining and milestone dates for the current stage."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Stage Projection"
    _attr_icon = "mdi:calendar-clock"
    _attr_native_unit_of_measurement = UnitOfTime.DAYS

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_stage_projection"
        self._unsub_state: object | None = None
        self._unsub_timer: object | None = None

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    def _source_entity_ids(self) -> list[str]:
        registry = get_entity_registry(self.hass)
        stage_id = registry.async_get_entity_id(
            "select", DOMAIN, f"{self._entry.entry_id}_{CTX_STAGE}"
        )
        started_id = registry.async_get_entity_id(
            "date", DOMAIN, f"{self._entry.entry_id}_{CTX_STAGE_STARTED}"
        )
        week_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{self._entry.entry_id}_{CTX_WEEK_IN_STAGE}"
        )
        return [eid for eid in (stage_id, started_id, week_id) if eid]

    def _projection(self) -> dict[str, object | None]:
        stage, started, week = resolve_stage_clock(self.hass, self._entry.entry_id)
        return compute_stage_projection(
            stage, week, dt_util.now(), stage_started=started
        )

    @property
    def native_value(self):
        return self._projection().get("days_remaining")

    @property
    def extra_state_attributes(self):
        projection = self._projection()
        return {
            key: value for key, value in projection.items() if key != "days_remaining"
        }

    @callback
    def _subscribe(self) -> None:
        if self._unsub_state is not None:
            return
        source_ids = self._source_entity_ids()
        if source_ids:
            self._unsub_state = async_track_state_change_event(
                self.hass, source_ids, self._async_source_changed
            )

    @callback
    def _async_source_changed(self, _event) -> None:
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        @callback
        def _refresh(*_args) -> None:
            self._subscribe()
            self.async_write_ha_state()

        self._subscribe()
        self._unsub_timer = async_track_time_interval(
            self.hass, _refresh, timedelta(minutes=30)
        )
        # The sensor platform loads before select/date; retry once they exist.
        async_call_later(self.hass, 15, _refresh)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None


class TendrilGrowDaysSinceFlipSensor(SensorEntity):
    """Elapsed days since the 12/12 photoperiod flip (flowering transition)."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = "Days Since Flip"
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_icon = "mdi:flower"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{DAYS_SINCE_FLIP_SUFFIX}"
        self._attr_device_info = grow_device_info(entry)
        self._unsub_state = None
        self._unsub_timer = None

    def _source_entity_ids(self) -> list[str]:
        registry = get_entity_registry(self.hass)
        ids = []
        for domain, suffix in (
            ("select", CTX_STAGE),
            ("date", CTX_STAGE_STARTED),
        ):
            eid = registry.async_get_entity_id(
                domain, DOMAIN, f"{self._entry.entry_id}_{suffix}"
            )
            if eid:
                ids.append(eid)
        return ids

    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    @property
    def native_value(self):
        stage, started, _week = resolve_stage_clock(self.hass, self._entry.entry_id)
        return compute_days_since_flip(stage, started, dt_util.now())

    @property
    def extra_state_attributes(self):
        stage, started, _week = resolve_stage_clock(self.hass, self._entry.entry_id)
        return {
            "current_stage": stage,
            "stage_started": started,
            "in_flower": (stage or "").lower()
            in ("early_flower", "mid_flower", "late_flower", "flush"),
        }

    @callback
    def _subscribe(self) -> None:
        if self._unsub_state is not None:
            return
        source_ids = self._source_entity_ids()
        if source_ids:
            self._unsub_state = async_track_state_change_event(
                self.hass, source_ids, self._async_source_changed
            )

    @callback
    def _async_source_changed(self, _event) -> None:
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        @callback
        def _refresh(*_args) -> None:
            self._subscribe()
            self.async_write_ha_state()

        self._subscribe()
        self._unsub_timer = async_track_time_interval(
            self.hass, _refresh, timedelta(hours=1)
        )
        async_call_later(self.hass, 15, _refresh)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None
