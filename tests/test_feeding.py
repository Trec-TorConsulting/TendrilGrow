"""Tests for feeding-schedule markdown formatting and mix order."""

from __future__ import annotations

from custom_components.tendrilgrow.feeding import compose_feeding_schedule_md
from custom_components.tendrilgrow.sensor import _compose_feeding_schedule_md


def test_empty_schedule() -> None:
    text = compose_feeding_schedule_md([])
    assert "No feeding schedule" in text


def test_reorders_hydroguard_last_and_spaces_products() -> None:
    raw = (
        "Current Veg Mix | ADD IN ORDER: Hydroguard: 26 ml (2 ml/gal), "
        "FloraBloom: 32.5 ml (2.5 ml/gal), FloraGro: 32.5 ml (2.5 ml/gal), "
        "FloraMicro: 32.5 ml (2.5 ml/gal), CaliMagic: 65 ml (5 ml/gal) | "
        "EST EC: 1.1 mS/cm | pH: 5.9 | Mix thoroughly"
    )
    text = compose_feeding_schedule_md([raw])

    assert "### 1. Current Veg Mix" in text
    assert "**Add in this order:**" in text
    names = [
        line.split(". ", 1)[1]
        for line in text.splitlines()
        if line[:1].isdigit() and ". " in line
    ]
    joined = "\n".join(names)
    assert joined.index("CaliMagic") < joined.index("FloraMicro")
    assert joined.index("FloraMicro") < joined.index("FloraGro")
    assert joined.index("FloraGro") < joined.index("FloraBloom")
    assert joined.index("FloraBloom") < joined.index("Hydroguard")
    assert "- **Est. EC:** 1.1 mS/cm" in text
    assert "- **pH:** 5.9" in text
    # HA markdown cards need blank lines; products must not share one pipe line.
    assert "ADD IN ORDER:" not in text
    assert "\n\n" in text


def test_semicolon_separated_products() -> None:
    raw = (
        "Fresh Fill | ADD IN ORDER: CALiMAGic: 65 ml (5 ml/gal); "
        "FloraMicro: 47 ml (3.6 ml/gal); Hydroguard: 26 ml (2 ml/gal) | "
        "EST EC: 1.0 mS/cm | pH: 5.8 | NOTE: pH last"
    )
    text = compose_feeding_schedule_md([raw])
    assert "CALiMAGic" in text
    assert "Hydroguard" in text
    assert text.index("CALiMAGic") < text.index("Hydroguard")
    assert "- **Note:** pH last" in text


def test_sensor_wrapper_uses_latest_schedule() -> None:
    latest = type("R", (), {"feeding_schedule": ["Veg | ADD IN ORDER: Micro: 1 ml"]})()
    text = _compose_feeding_schedule_md(latest)
    assert "### 1. Veg" in text
