"""Tests for Tuya status normalization."""

from __future__ import annotations

from custom_components.tendrilgrow.tuya_client import normalize_tuya_statuses


def test_normalize_scaled_values_from_shadow_properties() -> None:
    statuses = [
        {"code": "ph", "value": 575, "scale": 2},
        {"code": "ec", "value": 610, "scale": 0},
        {"code": "temp_current", "value": 196, "scale": 1},
        {"code": "orp", "value": 345, "scale": 0},
        {"code": "battery_percentage", "value": 87, "scale": 0},
    ]

    reading = normalize_tuya_statuses(statuses)

    assert reading["ph"] == 5.75
    assert reading["ec"] == 0.61
    assert reading["cf"] == 0.61
    assert reading["tds"] == 305.0
    assert reading["water_temp_c"] == 19.6
    assert reading["orp"] == 345.0
    assert reading["battery_pct"] == 87.0


def test_normalize_tds_only_derives_ec_and_cf() -> None:
    statuses = [
        {"code": "tds_in", "value": 452},
    ]

    reading = normalize_tuya_statuses(statuses)

    assert reading["tds"] == 452.0
    assert reading["ec"] == 0.904
    assert reading["cf"] == 0.904


def test_normalize_ec_only_derives_tds_and_cf() -> None:
    statuses = [
        {"code": "ec_value", "value": 1.24},
    ]

    reading = normalize_tuya_statuses(statuses)

    assert reading["ec"] == 1.24
    assert reading["cf"] == 1.24
    assert reading["tds"] == 620.0
