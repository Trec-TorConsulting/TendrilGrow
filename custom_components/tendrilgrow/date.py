"""Date entities for TendrilGrow cultivation context."""

from __future__ import annotations

from datetime import date

from homeassistant.components.date import DateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get as get_entity_registry
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import CTX_STAGE, CTX_STAGE_STARTED, DOMAIN
from .entity import grow_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the stage-started date entity for one grow space."""
    async_add_entities([GrowStageStartedDate(hass, entry)])


class GrowStageStartedDate(DateEntity, RestoreEntity):
    """Editable date the current growth stage began.

    Week-in-stage is derived from this date. Changing the growth-stage select
    resets the date to today; the operator can then backdate it if needed.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Stage Started"
    _attr_icon = "mdi:calendar-start"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{CTX_STAGE_STARTED}"
        self._attr_native_value = dt_util.now().date()
        self._unsub_stage = None

    @property
    def device_info(self):
        return grow_device_info(self._entry)

    def _stage_entity_id(self) -> str | None:
        registry = get_entity_registry(self.hass)
        return registry.async_get_entity_id(
            "select", DOMAIN, f"{self._entry.entry_id}_{CTX_STAGE}"
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (
            None,
            "",
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            try:
                self._attr_native_value = date.fromisoformat(last.state)
            except ValueError:
                self._attr_native_value = dt_util.now().date()
        else:
            runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
            migrated = getattr(runtime, "migrated_stage_started", None)
            self._attr_native_value = migrated or dt_util.now().date()

        @callback
        def _subscribe(*_args) -> None:
            self._subscribe_stage()

        self._subscribe_stage()
        async_call_later(self.hass, 15, _subscribe)

    def _subscribe_stage(self) -> None:
        if self._unsub_stage is not None:
            return
        stage_id = self._stage_entity_id()
        if not stage_id:
            return
        self._unsub_stage = async_track_state_change_event(
            self.hass, [stage_id], self._async_stage_changed
        )

    @callback
    def _async_stage_changed(self, event) -> None:
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if old_state is None or new_state is None:
            return
        if old_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        if old_state.state == new_state.state:
            return
        self._attr_native_value = dt_util.now().date()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_stage is not None:
            self._unsub_stage()
            self._unsub_stage = None

    async def async_set_value(self, value: date) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
