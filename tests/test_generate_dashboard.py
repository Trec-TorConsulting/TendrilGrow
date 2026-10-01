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
        "Controls",
        "Lifecycle",
        "AI",
        "Reservoir",
        "Operations",
        "Trends",
        "Advisor",
        "Plan",
    ]
    assert _card_types(view) <= GEN.CARD_TYPES
    assert _section(view, "Watch", space) is not None
    assert _section(view, "Trends", space) is not None
    assert _section(view, "Advisor", space) is not None
    assert "column_span" not in _section(view, "Watch", space)

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


def test_controls_section_features_and_pumps():
    space = _space("3x3 Mothers Tent", "3x3_mothers_tent", "tent")
    space["controls"] = {
        "lights": "light.tent_light",
        "fans": "fan.tent_circulation",
        "inline_fans": "fan.tent_duct",
    }
    space["controller_extras"] = {
        "plan_light_schedule": "sensor.tent_light_sched",
        "plan_circulator_fan_schedule": "sensor.tent_fan_sched",
        "plan_duct_fan_schedule": "sensor.tent_duct_sched",
    }
    view = GEN.build_space_view(space)
    controls = _section(view, "Controls", space)
    tiles = _tile_entities(controls)
    assert "light.tent_light" in tiles
    assert "fan.tent_circulation" in tiles
    assert "fan.tent_duct" in tiles
    assert space["reg"]["rdwc_pump"] in tiles
    assert space["reg"]["chiller_pump"] in tiles
    assert space["reg"]["air_pump"] in tiles

    light_card = next(
        c for c in controls["cards"] if c.get("entity") == "light.tent_light"
    )
    assert light_card["features"] == [{"type": "light-brightness"}]
    fan_card = next(
        c for c in controls["cards"] if c.get("entity") == "fan.tent_circulation"
    )
    assert fan_card["features"] == [{"type": "fan-speed"}]
    duct_card = next(c for c in controls["cards"] if c.get("entity") == "fan.tent_duct")
    assert duct_card["features"] == [{"type": "fan-speed"}]

    sched_card = next(c for c in controls["cards"] if c["type"] == "entities")
    sched_entities = [row["entity"] for row in sched_card["entities"]]
    assert "sensor.tent_light_sched" in sched_entities
    assert "sensor.tent_fan_sched" in sched_entities
    assert "sensor.tent_duct_sched" in sched_entities


def test_trends_section_history_graphs():
    space = _space("3x3 Mothers Tent", "3x3_mothers_tent", "tent")
    space["sensors"]["temperature"] = "sensor.tent_temp"
    space["sensors"]["humidity"] = "sensor.tent_humidity"
    space["sensors"]["orp"] = "sensor.tent_orp"
    view = GEN.build_space_view(space)
    trends = _section(view, "Trends", space)
    graphs = [c for c in trends["cards"] if c["type"] == "history-graph"]
    assert len(graphs) == 2
    assert graphs[0]["title"] == "Canopy Climate History (24h)"
    assert "sensor.tent_temp" in graphs[0]["entities"]
    assert "sensor.tent_humidity" in graphs[0]["entities"]
    assert graphs[1]["title"] == "Hydroponic Reservoir History (24h)"
    assert space["sensors"]["ph"] in graphs[1]["entities"]
    assert "sensor.tent_orp" in graphs[1]["entities"]


def test_plan_section_includes_grow_tasks_when_present():
    space = _space("3x3 Mothers Tent", "3x3_mothers_tent", "tent")
    space["grow_tasks"] = "todo.tent_grow_tasks"
    view = GEN.build_space_view(space)
    plan = _section(view, "Plan", space)
    todo = next(c for c in plan["cards"] if c["type"] == "todo-list")
    assert todo["entity"] == "todo.tent_grow_tasks"
    assert todo["title"] == "Grow Tasks"


def test_dry_run_returns_before_lovelace_save():
    source = (ROOT / "scripts" / "generate_dashboard.py").read_text(encoding="utf-8")
    main = source.split("async def main", 1)[1]
    dry_run = main.index("if not apply:")
    save = main.index("lovelace/config/save")
    assert dry_run < save
    assert "return 0" in main[dry_run:save]
    assert '"url_path": url_path' in main[save - 200 : save + 200]


def test_digital_twin_space_view_generation():
    space = _space("3x3 Mothers Tent", "3x3_mothers_tent", "tent")
    space["controls"] = {
        "lights": "light.tent_light",
        "fans": "fan.tent_fan",
        "inline_fans": "fan.tent_duct",
    }
    space["controller_schedules"] = {
        "plan_light_schedule": "sensor.tent_light_sched",
    }
    view = GEN.build_digital_twin_space_view(space)

    assert view["type"] == "sections"
    assert view["path"] == "zone-3x3_mothers_tent"
    assert view["title"] == "3x3 Mothers Tent"

    first_section = view["sections"][0]
    twin_card = first_section["cards"][0]
    assert twin_card["type"] == "custom:tendrilgrow-twin-card"
    assert twin_card["name"] == "3x3 Mothers Tent"
    assert twin_card["camera"] == "camera.tent"
    assert twin_card["light"] == "light.tent_light"
    assert twin_card["fan"] == "fan.tent_fan"
    assert twin_card["duct_fan"] == "fan.tent_duct"
    assert twin_card["ph"] == "sensor.tent_ph"
    assert twin_card["ec"] == "sensor.tent_ec"
    assert twin_card["target_ph_low"] == "number.tent_ph_low"

    trends_section = next(
        s
        for s in view["sections"]
        if any(
            c.get("type") == "custom:tendrilgrow-trends-card"
            for c in s.get("cards", [])
        )
    )
    trends_card = next(
        c
        for c in trends_section["cards"]
        if c.get("type") == "custom:tendrilgrow-trends-card"
    )
    assert trends_card["hours_to_show"] == 24
    assert len(trends_card["spaces"]) == 1
    assert trends_card["spaces"][0]["name"] == "3x3 Mothers Tent"

    all_cards = [c for s in view["sections"] for c in s.get("cards", [])]
    schedules_card = next(
        c for c in all_cards if c.get("type") == "custom:tendrilgrow-schedules-card"
    )
    assert schedules_card["title"] == "Controller Schedules & Ambient"
    assert len(schedules_card["schedules"]) == 1

    plan_card = next(
        c for c in all_cards if c.get("type") == "custom:tendrilgrow-plan-card"
    )
    assert plan_card["stage_projection"] == "sensor.tent_projection"

    advisor_card = next(
        c for c in all_cards if c.get("type") == "custom:tendrilgrow-advisor-card"
    )
    assert advisor_card["summary"] == "sensor.tent_summary"
    assert advisor_card["run_ai_health_check"] == "button.tent_run"


def test_digital_twin_overview_generation():
    first = _space("Tent A", "tent_a", "a")
    second = _space("Tent B", "tent_b", "b")
    view = GEN.build_digital_twin_overview([first, second])

    assert view["type"] == "sections"
    assert view["path"] == "overview"
    assert view["title"] == "Executive"

    overview_card = view["sections"][0]["cards"][1]
    assert overview_card["type"] == "custom:tendrilgrow-overview-card"
    assert len(overview_card["spaces"]) == 2
    assert overview_card["spaces"][0]["name"] == "Tent A"
    assert overview_card["spaces"][0]["path"] == "/tendrial-grow/zone-tent_a"
    assert overview_card["spaces"][1]["name"] == "Tent B"

    assert len(view["sections"]) == 2
    trends_card = view["sections"][1]["cards"][1]
    assert trends_card["type"] == "custom:tendrilgrow-trends-card"
    assert trends_card["hours_to_show"] == 24
    assert len(trends_card["spaces"]) == 2
