"""Tests for metric band alerts."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.tendrilgrow.const import SENSOR_ROLE_PH
from custom_components.tendrilgrow.metric_bands import (
    METRIC_PH,
    MetricBandRuntimeState,
    async_evaluate_metric_bands,
)


@pytest.mark.asyncio
async def test_ph_above_band_sets_out_of_range() -> None:
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    entry = SimpleNamespace(entry_id="e1", title="Tent", data={}, options={})
    grow_space = SimpleNamespace(sensor_mappings={SENSOR_ROLE_PH: "sensor.ph"})
    runtime = SimpleNamespace(
        grow_space=grow_space,
        metric_band_state=MetricBandRuntimeState(),
    )
    hass.states.get = MagicMock(return_value=SimpleNamespace(state="6.5"))

    with (
        patch(
            "custom_components.tendrilgrow.metric_bands.current_stage",
            return_value="vegetative",
        ),
        patch(
            "custom_components.tendrilgrow.metric_bands.read_band_bounds",
            return_value=(5.6, 6.0),
        ),
        patch(
            "custom_components.tendrilgrow.metric_bands.stage_has_reservoir_band",
            return_value=True,
        ),
    ):
        await async_evaluate_metric_bands(hass, entry, runtime)

    assert runtime.metric_band_state.out_of_range[METRIC_PH] is True
    hass.services.async_call.assert_called()


@pytest.mark.asyncio
async def test_dry_stage_has_no_ph_band() -> None:
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    entry = SimpleNamespace(entry_id="e1", title="Tent", data={}, options={})
    grow_space = SimpleNamespace(sensor_mappings={SENSOR_ROLE_PH: "sensor.ph"})
    runtime = SimpleNamespace(
        grow_space=grow_space,
        metric_band_state=MetricBandRuntimeState(),
    )

    with (
        patch(
            "custom_components.tendrilgrow.metric_bands.current_stage",
            return_value="dry",
        ),
        patch(
            "custom_components.tendrilgrow.metric_bands.stage_has_reservoir_band",
            return_value=False,
        ),
    ):
        await async_evaluate_metric_bands(hass, entry, runtime)

    assert runtime.metric_band_state.has_band[METRIC_PH] is False
    assert runtime.metric_band_state.out_of_range[METRIC_PH] is False
    hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_cooldown_blocks_repeat_notify() -> None:
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    entry = SimpleNamespace(entry_id="e1", title="Tent", data={}, options={})
    grow_space = SimpleNamespace(sensor_mappings={SENSOR_ROLE_PH: "sensor.ph"})
    state = MetricBandRuntimeState()
    state.out_of_range[METRIC_PH] = True
    state.has_band[METRIC_PH] = True
    state.source_available[METRIC_PH] = True
    state.last_notify_at[METRIC_PH] = datetime.now(UTC)
    runtime = SimpleNamespace(grow_space=grow_space, metric_band_state=state)
    hass.states.get = MagicMock(return_value=SimpleNamespace(state="6.5"))

    with (
        patch(
            "custom_components.tendrilgrow.metric_bands.current_stage",
            return_value="vegetative",
        ),
        patch(
            "custom_components.tendrilgrow.metric_bands.read_band_bounds",
            return_value=(5.6, 6.0),
        ),
        patch(
            "custom_components.tendrilgrow.metric_bands.stage_has_reservoir_band",
            return_value=True,
        ),
    ):
        await async_evaluate_metric_bands(hass, entry, runtime)

    hass.services.async_call.assert_not_called()


def test_operator_band_overrides_stage_table() -> None:
    """read_band_bounds uses operator numbers when both are set."""
    from custom_components.tendrilgrow.const import (
        CTX_TARGET_PH_HIGH,
        CTX_TARGET_PH_LOW,
    )
    from custom_components.tendrilgrow.grow_targets import read_band_bounds

    hass = MagicMock()
    entry = SimpleNamespace(entry_id="e1", data={}, options={})

    def _entity_id(domain, _d, unique):
        if unique.endswith(CTX_TARGET_PH_LOW):
            return "number.ph_low"
        if unique.endswith(CTX_TARGET_PH_HIGH):
            return "number.ph_high"
        return None

    registry = MagicMock()
    registry.async_get_entity_id = MagicMock(side_effect=_entity_id)
    hass.states.get = MagicMock(
        side_effect=lambda eid: {
            "number.ph_low": SimpleNamespace(state="5.0"),
            "number.ph_high": SimpleNamespace(state="5.5"),
        }.get(eid)
    )

    from homeassistant.helpers import entity_registry as er

    original = er.async_get
    er.async_get = MagicMock(return_value=registry)  # type: ignore[method-assign]
    try:
        low, high = read_band_bounds(hass, entry, "vegetative", "ph")
    finally:
        er.async_get = original  # type: ignore[method-assign]

    assert (low, high) == (5.0, 5.5)
