#!/usr/bin/env python3
"""Generate the TendrilGrow Lovelace dashboard from the live grow spaces.

For every TendrilGrow config entry (grow space / "hub") this builds an Executive
overview view plus one per-space tab, then pushes the result to the live
storage-mode dashboard. Adding a hub and re-running this makes a new tab appear
and refreshes the overview automatically.

How it discovers entities:
- Role-mapped sensors and the camera come from each entry's diagnostics
  (``runtime.effective_sensor_mappings``), so mapped Tuya/air sensors are used.
- Role-mapped controls (lights, fans, inline fans) come from each entry's
  diagnostics (``runtime.effective_control_mappings``) or entry config mappings.
- Pumps (RDWC, Air, Chiller) are discovered from integration proxy switches or
  tent-associated power devices in the registry.
- Hardware controller schedule sensors and ambient lung-room sensors are
  discovered from tent-associated controller devices.
- Integration helper entities (AI health, reservoir flush, stage projection,
  cultivation-intelligence suite, and cultivation-context helpers) come from
  the entity registry, matched by their ``<entry_id>_<suffix>`` unique ids.
- Grow space to-do task lists (``todo.<slug>_grow_tasks``) are bound directly to
  interactive task cards.

Security:
- Reads ``HA_URL`` and ``HA_TOKEN`` from the environment or a local ``.env``.
- The token is used only for API auth; it is NEVER printed or logged.
- Dry-run by default (writes the proposed YAML to a temp file). A live backup is
  written before any change, and the save only runs when ``--apply`` is passed.

Usage::

    ./.venv/bin/python scripts/generate_dashboard.py             # dry-run
    ./.venv/bin/python scripts/generate_dashboard.py --apply     # push to live
    ./.venv/bin/python scripts/generate_dashboard.py --url-path tendrial-grow --apply
"""

from __future__ import annotations

import asyncio
import os
import ssl
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp
import yaml

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "tendrilgrow"
DEFAULT_URL_PATH = "tendrial-grow"
DEFAULT_TITLE = "Tendrial Grow"

# Reservoir/air telemetry roles. pH and EC are promoted ahead of this list;
# integration VPD is inserted after them and before the remaining roles.
SENSOR_ROLE_ORDER = (
    "ph",
    "ec",
    "cf",
    "tds",
    "orp",
    "water_temperature",
    "temperature",
    "humidity",
    "light_ppfd",
)
ROLE_LABELS = {
    "ph": "pH",
    "ec": "EC",
    "cf": "CF",
    "tds": "TDS",
    "orp": "ORP",
    "water_temperature": "Water temperature",
    "temperature": "Temperature",
    "humidity": "Humidity",
    "light_ppfd": "PPFD",
}

LIFECYCLE_SUFFIXES = (
    "ctx_stage",
    "ctx_stage_started",
    "ctx_week_in_stage",
    "stage_projection",
)
AI_TILE_SUFFIXES = (
    "ai_health_summary",
    "ai_health_last_check",
    "ai_health_critical_alert",
    "run_ai_health_check",
)
BAND_TILE_SUFFIXES = (
    ("metric_band_ph", "pH band"),
    ("metric_band_ec", "EC band"),
    ("metric_band_vpd", "VPD band"),
)
TARGET_BAND_SUFFIXES = (
    "ctx_target_ph_low",
    "ctx_target_ph_high",
    "ctx_target_ec_low",
    "ctx_target_ec_high",
    "ctx_target_vpd_low",
    "ctx_target_vpd_high",
)
FLUSH_SUFFIXES = (
    "flush_due",
    "days_until_flush",
    "days_since_flush",
    "next_flush_due",
    "last_flush",
    "flush_now",
    "flush_interval_days",
)
PUMP_ROLES = ("rdwc_pump", "chiller_pump", "air_pump")
PLAN_SUFFIXES = (
    "ctx_strain",
    "ctx_water_type",
    "ctx_site_count",
    "ctx_reservoir_volume_gal",
    "ctx_target_ph",
    "ctx_target_ec",
    "ctx_feed_interval_days",
    "ctx_lights_on_hours",
    "ctx_lights_on_time",
    "ctx_lights_off_time",
    "ctx_runoff_target_pct",
    "ctx_nutrient_line",
    "ctx_base_nutrients",
    "ctx_additives",
    "ctx_price_per_kwh",
)
SUFFIX_LABELS = {
    "ctx_stage": "Stage",
    "ctx_stage_started": "Stage started",
    "ctx_week_in_stage": "Week in stage",
    "stage_projection": "Days left in stage",
    "ai_health_summary": "Summary",
    "ai_health_last_check": "Last check",
    "ai_health_critical_alert": "Critical alert",
    "ai_weekly_journal": "Weekly journal",
    "run_ai_health_check": "Run AI health check",
    "flush_due": "Flush due",
    "days_until_flush": "Days until flush",
    "days_since_flush": "Days since flush",
    "next_flush_due": "Next flush due",
    "last_flush": "Last flush",
    "flush_now": "Flush now",
    "flush_interval_days": "Flush interval",
    "total_pump_power": "Total pump power",
    "rdwc_pump": "RDWC pump",
    "chiller_pump": "Chiller pump",
    "air_pump": "Air pump",
    "rdwc_pump_power": "RDWC pump power",
    "chiller_pump_power": "Chiller pump power",
    "air_pump_power": "Air pump power",
    "metric_band_summary": "Metrics out of range",
    "leaf_vpd": "Leaf VPD",
    "dew_point": "Dew point",
    "dew_point_margin": "Dew point margin",
    "mold_risk": "Mold risk",
    "photoperiod_hours": "Photoperiod",
    "daily_transpiration_rate": "Transpiration rate",
    "reservoir_drift_diagnosis": "Drift diagnosis",
    "water_safety_status": "Water safety",
    "flow_ok": "Water flow",
    "leak_detected": "Leak detected",
    "days_since_flip": "Days since flip",
}
INTELLIGENCE_TILE_SUFFIXES = (
    ("leaf_vpd", "Leaf VPD"),
    ("dew_point", "Dew point"),
    ("dew_point_margin", "Dew point margin"),
    ("daily_transpiration_rate", "Transpiration rate"),
    ("photoperiod_hours", "Photoperiod"),
    ("mold_risk", "Mold risk"),
    ("reservoir_drift_diagnosis", "Drift diagnosis"),
    ("water_safety_status", "Water safety"),
    ("flow_ok", "Water flow"),
    ("leak_detected", "Leak detected"),
)
CONTROLLER_SCHEDULE_ROLES = (
    ("plan_light_schedule", "Light Schedule", "mdi:weather-sunset"),
    ("plan_circulator_fan_schedule", "Circulation Fan Schedule", "mdi:fan-clock"),
    ("plan_duct_fan_schedule", "Duct Fan Schedule", "mdi:fan-auto"),
)
LUNG_ROOM_ROLES = (
    ("outside_temperature", "Outside Temperature"),
    ("outside_humidity", "Outside Humidity"),
    ("outside_vpd", "Outside VPD"),
)
PROJECTION_ATTRS = (
    ("Projected stage end", "projected_stage_end"),
    ("Projected harvest", "projected_harvest_date"),
    ("Projected ready", "projected_ready_date"),
)
CARD_TYPES = frozenset(
    {
        "heading",
        "tile",
        "gauge",
        "picture-entity",
        "entities",
        "markdown",
        "history-graph",
        "todo-list",
    }
)


def load_env() -> dict[str, str]:
    """Load config from ``.env`` then let real env vars take precedence."""
    env: dict[str, str] = {}
    dotenv = ROOT / ".env"
    if dotenv.is_file():
        for raw in dotenv.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("HA_URL", "HA_TOKEN", "HA_INSECURE"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env


def build_ssl(insecure: bool) -> ssl.SSLContext | None:
    if not insecure:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def ws_call(ws, msg_id: int, payload: dict) -> dict:
    await ws.send_json({"id": msg_id, **payload})
    while True:
        msg = await ws.receive_json()
        if msg.get("id") == msg_id and msg.get("type") == "result":
            return msg


def _slug(text: str) -> str:
    out = "".join(c if c.isalnum() else "_" for c in text.lower())
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


def classify(
    entry_id: str,
    title: str,
    registry: list,
    eff_info: dict,
    states: dict[str, dict] | None = None,
    devices: dict[str, dict] | None = None,
) -> dict:
    """Bucket a grow space's entities into the parts each card needs."""
    if "sensors" in eff_info:
        eff_sensors = eff_info.get("sensors", {})
        eff_controls = eff_info.get("controls", {})
    else:
        eff_sensors = eff_info
        eff_controls = {}

    reg: dict[str, str] = {}
    last_updated: str | None = None
    for ent in registry:
        if ent.get("config_entry_id") != entry_id:
            continue
        uid = str(ent.get("unique_id", ""))
        entity_id = ent.get("entity_id")
        if not uid.startswith(entry_id + "_"):
            continue
        suffix = uid[len(entry_id) + 1 :]
        reg[suffix] = entity_id
        if suffix.endswith("_last_updated"):
            last_updated = entity_id
    if last_updated and states is not None:
        state = (states.get(last_updated) or {}).get("state")
        if state in (None, "unavailable", "unknown"):
            last_updated = None

    controls: dict[str, str] = {}
    for role in ("lights", "fans", "inline_fans"):
        if eff_controls.get(role):
            controls[role] = eff_controls[role]

    pumps: dict[str, str] = {}
    for role in PUMP_ROLES:
        if reg.get(role):
            pumps[role] = reg[role]

    slug = _slug(title)
    kw = (
        "3x3"
        if "3x3" in slug
        else ("4x4" if "4x4" in slug else ("clone" if "clone" in slug else slug))
    )
    if devices:
        power_dev_ids = [
            d_id
            for d_id, d in devices.items()
            if kw in (d.get("name_by_user") or d.get("name") or "").lower()
            and "power" in (d.get("name_by_user") or d.get("name") or "").lower()
        ]
        if power_dev_ids:
            for ent in registry:
                if ent.get("device_id") in power_dev_ids:
                    e_id = ent["entity_id"]
                    orig = (ent.get("name") or ent.get("original_name") or "").lower()
                    st_name = (
                        (
                            states.get(e_id, {})
                            .get("attributes", {})
                            .get("friendly_name")
                            or ""
                        ).lower()
                        if states
                        else ""
                    )
                    label = orig or st_name
                    if "rdwc" in label and "rdwc_pump" not in pumps:
                        pumps["rdwc_pump"] = e_id
                    elif "air" in label and "air_pump" not in pumps:
                        pumps["air_pump"] = e_id
                    elif "chiller" in label and "chiller_pump" not in pumps:
                        pumps["chiller_pump"] = e_id

    controller_extras: dict[str, str] = {}
    if devices:
        ctrl_dev_ids = [
            d_id
            for d_id, d in devices.items()
            if kw in (d.get("name_by_user") or d.get("name") or "").lower()
            and "controller" in (d.get("name_by_user") or d.get("name") or "").lower()
        ]
        if ctrl_dev_ids:
            for ent in registry:
                if ent.get("device_id") in ctrl_dev_ids:
                    e_id = ent["entity_id"]
                    for role, _, _ in CONTROLLER_SCHEDULE_ROLES:
                        if role in e_id:
                            controller_extras[role] = e_id
                    for role, _ in LUNG_ROOM_ROLES:
                        if role in e_id:
                            controller_extras[role] = e_id
                    if "connected" in e_id and ent.get("domain") == "binary_sensor":
                        controller_extras["connected"] = e_id

    todo_id = f"todo.{slug}_grow_tasks"
    grow_tasks = todo_id if (states and todo_id in states) else None

    return {
        "entry_id": entry_id,
        "title": title,
        "slug": slug,
        "camera": eff_sensors.get("camera"),
        "sensors": {r: eff_sensors[r] for r in SENSOR_ROLE_ORDER if eff_sensors.get(r)},
        "controls": controls,
        "pumps": pumps,
        "controller_extras": controller_extras,
        "grow_tasks": grow_tasks,
        "reg": reg,
        "last_updated": last_updated,
    }


def _camera_card(space: dict) -> dict | None:
    if not space.get("camera"):
        return None
    return {
        "type": "picture-entity",
        "entity": space["camera"],
        "name": f"{space['title']} Snapshot",
        "camera_view": "auto",
        "show_state": False,
        "tap_action": {"action": "more-info"},
    }


def _heading(text: str, *, style: str = "subtitle") -> dict:
    return {"type": "heading", "heading": text, "heading_style": style}


def _tile(
    entity_id: str,
    name: str,
    *,
    features: list | None = None,
    icon: str | None = None,
) -> dict:
    t: dict[str, Any] = {"type": "tile", "entity": entity_id, "name": name}
    if features:
        t["features"] = features
    if icon:
        t["icon"] = icon
    return t


def _suffix_tiles(reg: dict, suffixes: tuple[str, ...]) -> list[dict]:
    return [
        _tile(reg[suffix], SUFFIX_LABELS.get(suffix, suffix))
        for suffix in suffixes
        if reg.get(suffix)
    ]


def _section(
    heading: str,
    cards: list[dict],
    *,
    heading_style: str = "subtitle",
) -> dict | None:
    """A grid section. Omitted when it would contain only a heading."""
    if not cards:
        return None
    return {
        "type": "grid",
        "cards": [_heading(heading, style=heading_style), *cards],
    }


def _score_gauge(entity_id: str, name: str) -> dict:
    return {
        "type": "gauge",
        "entity": entity_id,
        "name": name,
        "min": 0,
        "max": 100,
        "severity": {"red": 0, "yellow": 50, "green": 75},
    }


def _badge(entity_id: str, *, when_state: str = "on") -> dict:
    return {
        "type": "entity",
        "entity": entity_id,
        "visibility": [
            {"condition": "state", "entity": entity_id, "state": when_state}
        ],
    }


def _stage_badge(entity_id: str) -> dict:
    return {"type": "entity", "entity": entity_id}


def _attr_template(entity_id: str, attr: str) -> str:
    return f"{{{{ state_attr('{entity_id}','{attr}') }}}}"


def _hidden_legacy_targets(reg: dict) -> set[str]:
    hidden: set[str] = set()
    if reg.get("ctx_target_ph_low") and reg.get("ctx_target_ph_high"):
        hidden.add("ctx_target_ph")
    if reg.get("ctx_target_ec_low") and reg.get("ctx_target_ec_high"):
        hidden.add("ctx_target_ec")
    return hidden


def _pump_suffixes() -> tuple[str, ...]:
    switches = PUMP_ROLES
    power = tuple(f"{role}_power" for role in PUMP_ROLES)
    return ("total_pump_power", *switches, *power)


def _controls_cards(space: dict) -> list[dict]:
    controls = space.get("controls") or {}
    pumps = space.get("pumps") or {}
    reg = space.get("reg") or {}
    scheds = space.get("controller_extras") or {}

    cards: list[dict] = []
    if controls.get("lights"):
        cards.append(
            _tile(
                controls["lights"],
                "Grow Light",
                features=[{"type": "light-brightness"}],
            )
        )
    if controls.get("fans"):
        cards.append(
            _tile(
                controls["fans"],
                "Circulation Fan",
                features=[{"type": "fan-speed"}],
            )
        )
    if controls.get("inline_fans"):
        cards.append(
            _tile(
                controls["inline_fans"],
                "Inline Duct Fan",
                features=[{"type": "fan-speed"}],
            )
        )

    rdwc = pumps.get("rdwc_pump") or reg.get("rdwc_pump")
    if rdwc:
        cards.append(_tile(rdwc, "RDWC Pump", icon="mdi:pump"))

    air = pumps.get("air_pump") or reg.get("air_pump")
    if air:
        cards.append(_tile(air, "Air Pump", icon="mdi:air-filter"))

    chiller = pumps.get("chiller_pump") or reg.get("chiller_pump")
    if chiller:
        cards.append(_tile(chiller, "Water Chiller Pump", icon="mdi:snowflake"))

    schedule_rows = [
        {"entity": scheds[role], "name": label, "icon": icon}
        for role, label, icon in CONTROLLER_SCHEDULE_ROLES
        if scheds.get(role)
    ]
    if schedule_rows:
        cards.append(
            {
                "type": "entities",
                "title": "Controller Schedule Status",
                "entities": schedule_rows,
            }
        )

    return cards


def _lung_room_card(space: dict) -> dict | None:
    extras = space.get("controller_extras") or {}
    rows = [
        {"entity": extras[role], "name": label}
        for role, label in LUNG_ROOM_ROLES
        if extras.get(role)
    ]
    if not rows:
        return None
    return {
        "type": "entities",
        "title": "Lung Room (Ambient)",
        "entities": rows,
    }


def _reservoir_tiles(space: dict) -> list[dict]:
    sensors = space.get("sensors") or {}
    reg = space.get("reg") or {}
    tiles: list[dict] = []
    if sensors.get("ph"):
        tiles.append(_tile(sensors["ph"], ROLE_LABELS["ph"]))
    if sensors.get("ec"):
        tiles.append(_tile(sensors["ec"], ROLE_LABELS["ec"]))
    if reg.get("vpd"):
        tiles.append(_tile(reg["vpd"], "VPD"))
    for role in SENSOR_ROLE_ORDER:
        if role in ("ph", "ec"):
            continue
        entity_id = sensors.get(role)
        if entity_id:
            tiles.append(_tile(entity_id, ROLE_LABELS[role]))
    for suffix, label in INTELLIGENCE_TILE_SUFFIXES:
        if reg.get(suffix):
            tiles.append(_tile(reg[suffix], label))
    for suffix, label in BAND_TILE_SUFFIXES:
        if reg.get(suffix):
            tiles.append(_tile(reg[suffix], label))
    return tiles


def _target_band_card(reg: dict) -> dict | None:
    rows = [reg[suffix] for suffix in TARGET_BAND_SUFFIXES if reg.get(suffix)]
    if not rows:
        return None
    return {
        "type": "entities",
        "title": "Target bands",
        "state_color": True,
        "entities": rows,
    }


def _projection_markdown(entity_id: str) -> dict:
    lines = [
        f"**{label}:** {_attr_template(entity_id, attr)}"
        for label, attr in PROJECTION_ATTRS
    ]
    return {"type": "markdown", "title": "Projections", "content": "\n\n".join(lines)}


def _advisor_cards(score: str) -> list[dict]:
    return [
        {
            "type": "markdown",
            "title": "AI Health Report",
            "content": _attr_template(score, "report"),
        },
        {
            "type": "markdown",
            "title": "AI Feeding Schedule",
            "content": _attr_template(score, "feeding_schedule_md"),
        },
    ]


def _plan_card(reg: dict) -> dict | None:
    hidden = _hidden_legacy_targets(reg)
    rows = [
        reg[suffix]
        for suffix in PLAN_SUFFIXES
        if suffix not in hidden and reg.get(suffix)
    ]
    if not rows:
        return None
    return {
        "type": "entities",
        "title": "Cultivation Plan",
        "state_color": True,
        "entities": rows,
    }


def _operations_cards(reg: dict) -> list[dict]:
    return _suffix_tiles(reg, (*FLUSH_SUFFIXES, *_pump_suffixes()))


def _trends_cards(space: dict) -> list[dict]:
    sensors = space.get("sensors") or {}
    reg = space.get("reg") or {}
    cards: list[dict] = []

    climate_entities = [
        eid
        for eid in (
            sensors.get("temperature"),
            sensors.get("humidity"),
            reg.get("vpd"),
            reg.get("leaf_vpd"),
        )
        if eid
    ]
    if climate_entities:
        cards.append(
            {
                "type": "history-graph",
                "title": "Canopy Climate History (24h)",
                "hours_to_show": 24,
                "entities": climate_entities,
            }
        )

    reservoir_entities = [
        eid
        for eid in (
            sensors.get("ph"),
            sensors.get("ec"),
            sensors.get("water_temperature"),
            sensors.get("orp"),
        )
        if eid
    ]
    if reservoir_entities:
        cards.append(
            {
                "type": "history-graph",
                "title": "Hydroponic Reservoir History (24h)",
                "hours_to_show": 24,
                "entities": reservoir_entities,
            }
        )

    return cards


def _space_badges(space: dict) -> list[dict]:
    reg = space.get("reg") or {}
    extras = space.get("controller_extras") or {}
    badges: list[dict] = []
    for suffix in (
        "ai_health_critical_alert",
        "mold_risk",
        "leak_detected",
        "flush_due",
        "metric_band_summary",
    ):
        if reg.get(suffix):
            badges.append(_badge(reg[suffix]))
    if reg.get("ctx_stage"):
        badges.append(_stage_badge(reg["ctx_stage"]))
    if extras.get("connected"):
        badges.append(_badge(extras["connected"], when_state="off"))
    return badges


def build_space_view(space: dict) -> dict:
    reg = space.get("reg") or {}
    sections: list[dict] = []

    camera = _camera_card(space)
    watch = _section("Watch", [camera] if camera else [])
    if watch:
        sections.append(watch)

    controls_cards = _controls_cards(space)
    controls = _section("Controls", controls_cards)
    if controls:
        sections.append(controls)

    lifecycle = _suffix_tiles(reg, LIFECYCLE_SUFFIXES)
    if reg.get("days_since_flip"):
        lifecycle.append(_tile(reg["days_since_flip"], "Days since flip"))
    if reg.get("stage_projection"):
        lifecycle.append(_projection_markdown(reg["stage_projection"]))
    life = _section(space["title"], lifecycle, heading_style="title")
    if life:
        sections.append(life)

    ai: list[dict] = []
    if reg.get("ai_health_score"):
        ai.append(_score_gauge(reg["ai_health_score"], f"{space['title']} AI Health"))
    ai.extend(_suffix_tiles(reg, AI_TILE_SUFFIXES))
    if reg.get("ai_weekly_journal"):
        ai.append(_tile(reg["ai_weekly_journal"], "Weekly journal"))
    ai_section = _section("AI", ai)
    if ai_section:
        sections.append(ai_section)

    reservoir = _reservoir_tiles(space)
    bands = _target_band_card(reg)
    if bands:
        reservoir.append(bands)
    lung_room = _lung_room_card(space)
    if lung_room:
        reservoir.append(lung_room)
    reservoir_section = _section("Reservoir", reservoir)
    if reservoir_section:
        sections.append(reservoir_section)

    operations = _section("Operations", _operations_cards(reg))
    if operations:
        sections.append(operations)

    trends = _section("Trends", _trends_cards(space))
    if trends:
        sections.append(trends)

    advisor_cards = (
        _advisor_cards(reg["ai_health_score"]) if reg.get("ai_health_score") else []
    )
    advisor = _section("Advisor", advisor_cards)
    if advisor:
        sections.append(advisor)

    plan_cards = []
    plan_card = _plan_card(reg)
    if plan_card:
        plan_cards.append(plan_card)
    if space.get("grow_tasks"):
        plan_cards.append(
            {
                "type": "todo-list",
                "entity": space["grow_tasks"],
                "title": "Grow Tasks",
            }
        )
    plan_section = _section("Plan", plan_cards)
    if plan_section:
        sections.append(plan_section)

    view: dict[str, Any] = {
        "path": f"zone-{space['slug']}",
        "title": space["title"],
        "icon": "mdi:sprout",
        "type": "sections",
        "max_columns": 2,
        "sections": sections,
    }
    badges = _space_badges(space)
    if badges:
        view["badges"] = badges
    return view


def _trend_entities(spaces: list[dict]) -> list[str]:
    trend: list[str] = []
    for space in spaces:
        sensors = space.get("sensors") or {}
        for role in ("water_temperature", "ph"):
            entity_id = sensors.get(role)
            if entity_id:
                trend.append(entity_id)
    return trend


def _status_cards(space: dict) -> list[dict]:
    reg = space.get("reg") or {}
    cards: list[dict] = []
    camera = _camera_card(space)
    if camera:
        cards.append(camera)
    if reg.get("ai_health_score"):
        cards.append(
            _score_gauge(reg["ai_health_score"], f"{space['title']} AI Health")
        )
    for suffix in (
        "ai_health_summary",
        "metric_band_summary",
        "flush_due",
        "days_until_flush",
        "mold_risk",
        "water_safety_status",
    ):
        if reg.get(suffix):
            cards.append(_tile(reg[suffix], SUFFIX_LABELS.get(suffix, suffix)))
    return cards


def build_overview(spaces: list[dict]) -> dict:
    sections: list[dict] = []
    badges: list[dict] = []
    for space in spaces:
        sections.append(
            {
                "type": "grid",
                "cards": [
                    _heading(space["title"], style="title"),
                    *_status_cards(space),
                ],
            }
        )
        reg = space.get("reg") or {}
        for suffix in (
            "metric_band_summary",
            "flush_due",
            "mold_risk",
            "ai_health_critical_alert",
        ):
            entity_id = reg.get(suffix)
            if entity_id:
                badges.append(_badge(entity_id))

    trend = _trend_entities(spaces)
    if trend:
        sections.append(
            {
                "type": "grid",
                "cards": [
                    _heading("Trend"),
                    {
                        "type": "history-graph",
                        "title": "Water Temperature and pH Trend (24h)",
                        "hours_to_show": 24,
                        "entities": trend,
                    },
                ],
            }
        )

    view: dict[str, Any] = {
        "path": "overview",
        "title": "Executive",
        "icon": "mdi:view-dashboard",
        "type": "sections",
        "max_columns": max(len(spaces), 1),
        "sections": sections,
    }
    if badges:
        view["badges"] = badges
    return view


def build_digital_twin_space_view(space: dict) -> dict:
    """Build a modern Digital Twin HUD view for one grow space."""
    slug = space.get("slug") or "space"
    title = space.get("title") or "Grow Space"
    reg = space.get("reg") or {}
    sensors = space.get("sensors") or {}
    controls = space.get("controls") or {}
    pumps = space.get("pumps") or {}

    twin_card: dict[str, Any] = {
        "type": "custom:tendrilgrow-twin-card",
        "name": title,
    }
    if space.get("camera"):
        twin_card["camera"] = space["camera"]
    if controls.get("lights"):
        twin_card["light"] = controls["lights"]
    if controls.get("fans"):
        twin_card["fan"] = controls["fans"]
    if controls.get("inline_fans"):
        twin_card["duct_fan"] = controls["inline_fans"]

    for pump_key in ("rdwc_pump", "air_pump", "chiller_pump"):
        pump_entity = pumps.get(pump_key) or reg.get(pump_key)
        if pump_entity:
            twin_card[pump_key] = pump_entity

    for sensor_key in (
        "temperature",
        "humidity",
        "ph",
        "ec",
        "water_temperature",
        "tds",
        "orp",
    ):
        if sensors.get(sensor_key):
            twin_card[sensor_key] = sensors[sensor_key]

    for reg_key in ("vpd", "leaf_vpd", "dew_point"):
        if reg.get(reg_key):
            twin_card[reg_key] = reg[reg_key]

    if reg.get("ctx_stage"):
        twin_card["stage"] = reg["ctx_stage"]
    if reg.get("ctx_stage_started"):
        twin_card["stage_started"] = reg["ctx_stage_started"]
    if reg.get("ctx_week_in_stage"):
        twin_card["week"] = reg["ctx_week_in_stage"]
    if reg.get("stage_projection"):
        twin_card["projection"] = reg["stage_projection"]
    if reg.get("ai_health_score"):
        twin_card["ai_health_score"] = reg["ai_health_score"]
    if reg.get("ai_health_summary"):
        twin_card["ai_health_summary"] = reg["ai_health_summary"]
    if reg.get("run_ai_health_check"):
        twin_card["run_ai_health_check"] = reg["run_ai_health_check"]

    for alert_key in (
        "mold_risk",
        "flush_due",
        "metrics_out_of_range",
        "ai_critical_alert",
    ):
        if reg.get(alert_key):
            twin_card[alert_key] = reg[alert_key]

    for band_key in (
        "target_ph_low",
        "target_ph_high",
        "target_ec_low",
        "target_ec_high",
        "target_vpd_low",
        "target_vpd_high",
    ):
        ctx_key = f"ctx_{band_key}"
        if reg.get(ctx_key):
            twin_card[band_key] = reg[ctx_key]

    sections: list[dict[str, Any]] = [
        {
            "type": "grid",
            "cards": [twin_card],
        }
    ]

    controls_cards: list[dict[str, Any]] = []
    scheds = space.get("controller_schedules") or {}
    schedule_rows = [
        {"entity": scheds[role], "name": label, "icon": icon}
        for role, label, icon in CONTROLLER_SCHEDULE_ROLES
        if scheds.get(role)
    ]
    if schedule_rows:
        controls_cards.append(
            {
                "type": "entities",
                "title": "Controller Schedule Status",
                "entities": schedule_rows,
            }
        )
    lung = _lung_room_card(space)
    if lung:
        controls_cards.append(lung)
    if controls_cards:
        sections.append(
            {
                "type": "grid",
                "cards": [
                    _heading("Controller Schedules & Ambient", style="subtitle"),
                    *controls_cards,
                ],
            }
        )

    plan_cards: list[dict[str, Any]] = []
    if reg.get("stage_projection"):
        plan_cards.append(_projection_markdown(reg["stage_projection"]))
    todo = reg.get("todo") or space.get("grow_tasks") or f"todo.{slug}_grow_tasks"
    plan_cards.append({"type": "todo-list", "entity": todo, "title": "Grow Tasks"})
    sections.append(
        {
            "type": "grid",
            "cards": [
                _heading("Cultivation Plan & Tasks", style="subtitle"),
                *plan_cards,
            ],
        }
    )

    trend_cards = _trends_cards(space)
    if trend_cards:
        sections.append(
            {
                "type": "grid",
                "cards": [
                    _heading("24h Telemetry Trends", style="subtitle"),
                    *trend_cards,
                ],
            }
        )

    if reg.get("ai_health_score"):
        advisor = _advisor_cards(reg["ai_health_score"])
        sections.append(
            {
                "type": "grid",
                "cards": [
                    _heading("AI Cultivation Intelligence", style="subtitle"),
                    *advisor,
                ],
            }
        )

    return {
        "path": f"zone-{slug}",
        "title": title,
        "icon": "mdi:sprout",
        "type": "sections",
        "max_columns": 2,
        "sections": sections,
        "badges": _space_badges(space),
    }


def build_digital_twin_overview(spaces: list[dict]) -> dict:
    """Build the modern executive overview card comparing all spaces."""
    overview_spaces = []
    canopy_trends: list[str] = []
    hydro_trends: list[str] = []

    for s in spaces:
        reg = s.get("reg") or {}
        sensors = s.get("sensors") or {}
        controls = s.get("controls") or {}
        item: dict[str, Any] = {
            "name": s.get("title") or "Grow Space",
            "path": f"/tendrial-grow/zone-{s.get('slug')}",
        }
        if s.get("camera"):
            item["camera"] = s["camera"]
        if sensors.get("temperature"):
            item["temperature"] = sensors["temperature"]
            canopy_trends.append(sensors["temperature"])
        if sensors.get("humidity"):
            item["humidity"] = sensors["humidity"]
            canopy_trends.append(sensors["humidity"])
        if reg.get("vpd"):
            item["vpd"] = reg["vpd"]
            canopy_trends.append(reg["vpd"])
        if reg.get("leaf_vpd"):
            item["leaf_vpd"] = reg["leaf_vpd"]
        if sensors.get("ph"):
            item["ph"] = sensors["ph"]
            hydro_trends.append(sensors["ph"])
        if sensors.get("ec"):
            item["ec"] = sensors["ec"]
            hydro_trends.append(sensors["ec"])
        if sensors.get("water_temperature"):
            item["water_temperature"] = sensors["water_temperature"]
            hydro_trends.append(sensors["water_temperature"])
        if reg.get("ai_health_score"):
            item["ai_health_score"] = reg["ai_health_score"]
        if reg.get("ctx_stage"):
            item["stage"] = reg["ctx_stage"]
        if controls.get("lights"):
            item["light"] = controls["lights"]
        if controls.get("fans"):
            item["fan"] = controls["fans"]
        if controls.get("inline_fans"):
            item["duct_fan"] = controls["inline_fans"]
        if reg.get("mold_risk"):
            item["mold_risk"] = reg["mold_risk"]
        if reg.get("flush_due"):
            item["flush_due"] = reg["flush_due"]
        if reg.get("metric_band_summary"):
            item["metrics_out_of_range"] = reg["metric_band_summary"]
        if reg.get("ai_health_critical_alert"):
            item["ai_critical_alert"] = reg["ai_health_critical_alert"]
        overview_spaces.append(item)

    cards = [
        _heading("All Grow Spaces", style="title"),
        {
            "type": "custom:tendrilgrow-overview-card",
            "title": "Cultivation Network Overview",
            "spaces": overview_spaces,
        },
    ]

    sections: list[dict[str, Any]] = [
        {
            "type": "grid",
            "cards": cards,
        }
    ]

    trend_cards = []
    if canopy_trends:
        trend_cards.append(
            {
                "type": "history-graph",
                "title": "Canopy Climate History (24h)",
                "hours_to_show": 24,
                "entities": canopy_trends,
            }
        )
    if hydro_trends:
        trend_cards.append(
            {
                "type": "history-graph",
                "title": "Hydroponic Reservoir History (24h)",
                "hours_to_show": 24,
                "entities": hydro_trends,
            }
        )

    if trend_cards:
        sections.append(
            {
                "type": "grid",
                "cards": [
                    _heading("24-Hour Telemetry Trends", style="subtitle"),
                    *trend_cards,
                ],
            }
        )

    badges = []
    for s in spaces:
        badges.extend(_space_badges(s))

    return {
        "path": "overview",
        "title": "Executive",
        "icon": "mdi:view-dashboard",
        "type": "sections",
        "max_columns": 2,
        "sections": sections,
        "badges": badges,
    }


async def fetch_diagnostics(session, url, token, entry_id, ssl_ctx) -> dict:
    endpoint = f"{url}/api/diagnostics/config_entry/{entry_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with session.get(endpoint, headers=headers, ssl=ssl_ctx) as resp:
            if resp.status != 200:
                return {}
            body = await resp.json()
    except (aiohttp.ClientError, ValueError):
        return {}
    data = body.get("data", {})
    runtime = data.get("runtime", {})
    return {
        "sensors": runtime.get("effective_sensor_mappings", {}) or {},
        "controls": runtime.get("effective_control_mappings", {})
        or data.get("options", {}).get("control_mappings", {})
        or data.get("data", {}).get("control_mappings", {})
        or {},
    }


async def main() -> int:
    args = sys.argv[1:]
    apply = ("--apply" in args) or ("-y" in args)
    url_path = DEFAULT_URL_PATH
    if "--url-path" in args:
        url_path = args[args.index("--url-path") + 1]

    env = load_env()
    url = (env.get("HA_URL") or "").rstrip("/")
    token = env.get("HA_TOKEN") or ""
    insecure = env.get("HA_INSECURE", "0") in ("1", "true", "True")
    if not url or not token:
        print("Missing HA_URL or HA_TOKEN. Copy .env.example to .env and fill it in.")
        return 1

    ws_url = (
        url.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"
    )
    ssl_ctx = build_ssl(insecure)
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"Connecting to {url} (token never printed) [{mode}]")

    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {token}"}
        states: dict[str, dict] = {}
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with session.get(
                f"{url}/api/states", headers=headers, ssl=ssl_ctx, timeout=timeout
            ) as resp:
                if resp.status == 200:
                    states = {s["entity_id"]: s for s in await resp.json()}
        except (aiohttp.ClientError, ValueError):
            states = {}
        async with session.ws_connect(
            ws_url, ssl=ssl_ctx, timeout=aiohttp.ClientTimeout(total=30)
        ) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            if (await ws.receive_json()).get("type") != "auth_ok":
                print("WebSocket auth failed (valid token / admin user?)")
                return 1

            entries = (await ws_call(ws, 1, {"type": "config_entries/get"})).get(
                "result", []
            )
            registry = (
                await ws_call(ws, 2, {"type": "config/entity_registry/list"})
            ).get("result", [])

            devices_res = await ws_call(ws, 3, {"type": "config/device_registry/list"})
            devices = (
                {d["id"]: d for d in devices_res.get("result", [])}
                if devices_res.get("success", True)
                else {}
            )

            grow_entries = [e for e in entries if e.get("domain") == DOMAIN]
            grow_entries.sort(key=lambda e: str(e.get("title", "")))
            if not grow_entries:
                print("No TendrilGrow config entries found.")
                return 1

            spaces = []
            for entry in grow_entries:
                entry_id = entry["entry_id"]
                eff = await fetch_diagnostics(session, url, token, entry_id, ssl_ctx)
                title = str(entry.get("title") or entry_id)
                spaces.append(classify(entry_id, title, registry, eff, states, devices))

            twin_mode = ("--digital-twin" in args) or ("--twin" in args)
            if twin_mode:
                config = {
                    "title": DEFAULT_TITLE,
                    "views": [build_digital_twin_overview(spaces)]
                    + [build_digital_twin_space_view(s) for s in spaces],
                }
            else:
                config = {
                    "title": DEFAULT_TITLE,
                    "views": [build_overview(spaces)]
                    + [build_space_view(s) for s in spaces],
                }

            proposed = Path(tempfile.gettempdir()) / "tendrilgrow_generated.yaml"
            proposed.write_text(
                yaml.safe_dump(
                    config,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )
            print(f"\nGenerated {len(spaces)} grow space(s):")
            for space in spaces:
                print(f"  - {space['title']} (tab zone-{space['slug']})")
            print(f"proposed config -> {proposed}")

            if not apply:
                print("\nDRY RUN (no changes saved). Re-run with --apply to push.")
                return 0

            current = await ws_call(
                ws, 4, {"type": "lovelace/config", "url_path": url_path}
            )
            if current.get("success"):
                backup = (
                    Path(tempfile.gettempdir())
                    / f"tendrilgrow-dash-backup-{_slug(url_path)}-"
                    f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.yaml"
                )
                backup.write_text(
                    yaml.safe_dump(current.get("result", {}), allow_unicode=True),
                    encoding="utf-8",
                )
                print(f"backed up live -> {backup}")

            saved = await ws_call(
                ws,
                5,
                {
                    "type": "lovelace/config/save",
                    "url_path": url_path,
                    "config": config,
                },
            )
            if not saved.get("success", False):
                print(f"SAVE FAILED: {saved.get('error')}")
                return 1
            print(f"\nSaved generated dashboard to live '{url_path}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
