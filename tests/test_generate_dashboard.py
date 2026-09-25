"""Layout tests for the generated Lovelace cockpit."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_generator():
    path = ROOT / "scripts" / "generate_dashboard.py"
    spec = importlib.util.spec_from_file_location("generate_dashboard", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GEN = _load_generator()


def _space(title: str, slug: str, prefix: str) -> dict:
    return {
        "entry_id": prefix,
        "title": title,
        "slug": slug,
        "camera": f"camera.{prefix}",
        "sensors": {
            "ph": f"sensor.{prefix}_ph",
            "ec": f"sensor.{prefix}_ec",
            "cf": f"sensor.{prefix}_cf",
            "water_temperature": f"sensor.{prefix}_water_temp",
        },
        "reg": {
            "vpd": f"sensor.{prefix}_vpd",
            "ctx_stage": f"select.{prefix}_stage",
            "ctx_stage_started": f"date.{prefix}_started",
            "ctx_week_in_stage": f"sensor.{prefix}_week",
            "stage_projection": f"sensor.{prefix}_projection",
            "ai_health_score": f"sensor.{prefix}_score",
            "ai_health_summary": f"sensor.{prefix}_summary",
            "ai_health_last_check": f"sensor.{prefix}_last_check",
            "ai_health_critical_alert": f"binary_sensor.{prefix}_critical",
            "run_ai_health_check": f"button.{prefix}_run",
            "metric_band_ph": f"binary_sensor.{prefix}_band_ph",
            "metric_band_ec": f"binary_sensor.{prefix}_band_ec",
            "metric_band_vpd": f"binary_sensor.{prefix}_band_vpd",
            "metric_band_summary": f"binary_sensor.{prefix}_band_summary",
            "ctx_target_ph_low": f"number.{prefix}_ph_low",
            "ctx_target_ph_high": f"number.{prefix}_ph_high",
            "ctx_target_ec_low": f"number.{prefix}_ec_low",
            "ctx_target_ec_high": f"number.{prefix}_ec_high",
            "ctx_target_vpd_low": f"number.{prefix}_vpd_low",
            "ctx_target_vpd_high": f"number.{prefix}_vpd_high",
            "ctx_target_ph": f"number.{prefix}_target_ph",
            "ctx_target_ec": f"number.{prefix}_target_ec",
            "ctx_strain": f"text.{prefix}_strain",
            "ctx_water_type": f"select.{prefix}_water",
            "ctx_lights_on_time": f"time.{prefix}_lights_on",
            "flush_due": f"binary_sensor.{prefix}_flush_due",
            "days_until_flush": f"sensor.{prefix}_days_until",
            "days_since_flush": f"sensor.{prefix}_days_since",
            "next_flush_due": f"sensor.{prefix}_next_flush",
            "last_flush": f"sensor.{prefix}_last_flush",
            "flush_now": f"button.{prefix}_flush",
            "flush_interval_days": f"number.{prefix}_flush_interval",
            "total_pump_power": f"sensor.{prefix}_pump_power",
            "rdwc_pump": f"switch.{prefix}_rdwc",
            "chiller_pump": f"switch.{prefix}_chiller",
            "air_pump": f"switch.{prefix}_air",
            "rdwc_pump_power": f"sensor.{prefix}_rdwc_power",
        },
        "last_updated": None,
    }


def _heading(section: dict) -> str:
    for card in section["cards"]:
        if card["type"] == "heading":
            return card["heading"]
    raise AssertionError("section has no heading")


def _section_names(view: dict, space: dict) -> list[str]:
    names = []
    for section in view["sections"]:
        label = _heading(section)
        names.append("Lifecycle" if label == space["title"] else label)
    return names


def _section(view: dict, name: str, space: dict) -> dict:
    for section in view["sections"]:
        label = _heading(section)
        resolved = "Lifecycle" if label == space["title"] else label
        if resolved == name:
            return section
    raise AssertionError(name)


def _flatten(value) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    return str(value)


def _card_types(view: dict) -> set[str]:
    return {card["type"] for section in view["sections"] for card in section["cards"]}


def _tile_entities(section: dict) -> list[str]:
    return [card["entity"] for card in section["cards"] if card["type"] == "tile"]


def test_populated_zone_is_a_sections_cockpit():
    space = _space("3x3 Mothers Tent", "3x3_mothers_tent", "tent")
    view = GEN.build_space_view(space)

    assert view["type"] == "sections"
    assert view["path"] == "zone-3x3_mothers_tent"
    assert view["title"] == "3x3 Mothers Tent"
    assert view["icon"] == "mdi:sprout"
    assert view["max_columns"] == 2
    assert _section_names(view, space) == [
        "Watch",
        "Lifecycle",
        "AI",
        "Reservoir",
        "Operations",
        "Advisor",
        "Plan",
    ]
    assert _card_types(view) <= GEN.CARD_TYPES
    assert _section(view, "Watch", space)["column_span"] == 2
    assert _section(view, "Advisor", space)["column_span"] == 2

    lifecycle = _section(view, "Lifecycle", space)
    assert _heading(lifecycle) == space["title"]
    lifecycle_tiles = _tile_entities(lifecycle)
    for suffix in (
        "ctx_stage",
        "ctx_stage_started",
        "ctx_week_in_stage",
        "stage_projection",
    ):
        assert space["reg"][suffix] in lifecycle_tiles
    projection = next(card for card in lifecycle["cards"] if card["type"] == "markdown")
    for attr in (
        "projected_stage_end",
        "projected_harvest_date",
        "projected_ready_date",
    ):
        assert attr in projection["content"]
        assert space["reg"]["stage_projection"] in projection["content"]

    gauge = next(
        card for card in _section(view, "AI", space)["cards"] if card["type"] == "gauge"
    )
    assert gauge["entity"] == space["reg"]["ai_health_score"]
    assert gauge["min"] == 0
    assert gauge["max"] == 100
    assert gauge["severity"] == {"red": 0, "yellow": 50, "green": 75}
    ai_tiles = _tile_entities(_section(view, "AI", space))
    for suffix in (
        "ai_health_summary",
        "ai_health_last_check",
        "ai_health_critical_alert",
        "run_ai_health_check",
    ):
        assert space["reg"][suffix] in ai_tiles

    reservoir = _section(view, "Reservoir", space)
    tiles = _tile_entities(reservoir)
    ph = space["sensors"]["ph"]
    ec = space["sensors"]["ec"]
    vpd = space["reg"]["vpd"]
    cf = space["sensors"]["cf"]
    assert tiles.index(ph) < tiles.index(cf)
    assert tiles.index(ec) < tiles.index(cf)
    assert tiles.index(vpd) < tiles.index(cf)
    assert space["reg"]["metric_band_ph"] in tiles
    bands = next(
        card
        for card in reservoir["cards"]
        if card["type"] == "entities" and card["title"] == "Target bands"
    )
    assert space["reg"]["ctx_target_ph_low"] in bands["entities"]
    assert space["reg"]["ctx_target_ph_high"] in bands["entities"]
    assert space["reg"]["ctx_target_ph"] not in _flatten(view)

    operations = set(_tile_entities(_section(view, "Operations", space)))
    for suffix in ("flush_due", "flush_now", "total_pump_power", "rdwc_pump"):
        assert space["reg"][suffix] in operations

    advisor = " ".join(
        card["content"]
        for card in _section(view, "Advisor", space)["cards"]
        if card["type"] == "markdown"
    )
    assert "report" in advisor
    assert "feeding_schedule_md" in advisor
    assert space["reg"]["ai_health_score"] in advisor

    plan = next(
        card
        for card in _section(view, "Plan", space)["cards"]
        if card["type"] == "entities"
    )
    assert space["reg"]["ctx_strain"] in plan["entities"]
    assert space["reg"]["ctx_stage"] not in plan["entities"]
    assert space["reg"]["ctx_lights_on_time"] in plan["entities"]


def test_missing_camera_vpd_and_pumps_drop_their_cards():
    space = _space("Clone", "clone", "clone")
    space["camera"] = None
    space["reg"].pop("vpd")
    for suffix in list(space["reg"]):
        if "pump" in suffix:
            space["reg"].pop(suffix)

    view = GEN.build_space_view(space)
    types = _card_types(view)
    blob = _flatten(view)

    assert "picture-entity" not in types
    assert "sensor.clone_vpd" not in blob
    assert "switch.clone_rdwc" not in blob
    names = _section_names(view, space)
    assert "Lifecycle" in names
    assert "AI" in names
    assert view["type"] == "sections"


def test_operations_section_is_omitted_without_flush_or_pumps():
    space = _space("Clone", "clone", "clone")
    for suffix in list(space["reg"]):
        if "flush" in suffix or "pump" in suffix:
            space["reg"].pop(suffix)

    view = GEN.build_space_view(space)
    assert "Operations" not in _section_names(view, space)


def test_unavailable_mapped_ph_stays_on_the_reservoir():
    """Mapped sensor ids are placed even when the live state is unavailable."""
    space = _space("Clone", "clone", "clone")
    view = GEN.build_space_view(space)
    tiles = _tile_entities(_section(view, "Reservoir", space))
    assert space["sensors"]["ph"] in tiles


def test_legacy_target_stays_when_the_band_pair_is_missing():
    space = _space("Clone", "clone", "clone")
    space["reg"].pop("ctx_target_ph_low")
    space["reg"].pop("ctx_target_ph_high")
    view = GEN.build_space_view(space)
    assert space["reg"]["ctx_target_ph"] in _flatten(view)


def test_executive_summarizes_each_space():
    first = _space("Tent A", "tent_a", "a")
    second = _space("Tent B", "tent_b", "b")
    view = GEN.build_overview([first, second])

    assert view["type"] == "sections"
    assert view["path"] == "overview"
    assert view["title"] == "Executive"
    assert view["icon"] == "mdi:view-dashboard"
    assert view["max_columns"] == 2
    assert [_heading(section) for section in view["sections"]] == [
        "Tent A",
        "Tent B",
        "Trend",
    ]

    for space in (first, second):
        section = next(
            item for item in view["sections"] if _heading(item) == space["title"]
        )
        gauge = next(card for card in section["cards"] if card["type"] == "gauge")
        assert gauge["entity"] == space["reg"]["ai_health_score"]
        assert space["reg"]["flush_due"] in _tile_entities(section)
        for suffix in ("metric_band_summary", "flush_due"):
            entity_id = space["reg"][suffix]
            badge = next(item for item in view["badges"] if item["entity"] == entity_id)
            assert badge["visibility"] == [
                {"condition": "state", "entity": entity_id, "state": "on"}
            ]

    graph = next(
        card
        for section in view["sections"]
        for card in section["cards"]
        if card["type"] == "history-graph"
    )
    assert graph["hours_to_show"] == 24
    assert graph["entities"] == [
        first["sensors"]["water_temperature"],
        first["sensors"]["ph"],
        second["sensors"]["water_temperature"],
        second["sensors"]["ph"],
    ]
    assert _card_types(view) <= GEN.CARD_TYPES


def test_executive_omits_the_trend_without_water_temperature_or_ph():
    space = _space("Tent A", "tent_a", "a")
    space["sensors"] = {}
    view = GEN.build_overview([space])
    assert "history-graph" not in _card_types(view)
    assert [_heading(section) for section in view["sections"]] == ["Tent A"]


def test_dry_run_returns_before_lovelace_save():
    source = (ROOT / "scripts" / "generate_dashboard.py").read_text(encoding="utf-8")
    main = source.split("async def main", 1)[1]
    dry_run = main.index("if not apply:")
    save = main.index("lovelace/config/save")
    assert dry_run < save
    assert "return 0" in main[dry_run:save]
    assert '"url_path": url_path' in main[save - 200 : save + 200]
