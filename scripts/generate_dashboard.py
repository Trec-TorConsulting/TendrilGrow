#!/usr/bin/env python3
"""Generate the TendrilGrow Lovelace dashboard from the live grow spaces.

For every TendrilGrow config entry (grow space / "hub") this builds an Executive
overview view plus one per-space tab, then pushes the result to the live
storage-mode dashboard. Adding a hub and re-running this makes a new tab appear
and refreshes the overview automatically.

How it discovers entities:
- Role-mapped sensors and the camera come from each entry's diagnostics
  (``runtime.effective_sensor_mappings``), so mapped Tuya/air sensors are used.
- Integration helper entities (AI health, reservoir flush, stage projection, and
  cultivation-context helpers) come from the entity registry, matched by their
  ``<entry_id>_<suffix>`` unique ids.

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
}
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
    eff_sensors: dict,
    states: dict[str, dict] | None = None,
) -> dict:
    """Bucket a grow space's entities into the parts each card needs."""
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
    return {
        "entry_id": entry_id,
        "title": title,
        "slug": _slug(title),
        "camera": eff_sensors.get("camera"),
        "sensors": {r: eff_sensors[r] for r in SENSOR_ROLE_ORDER if eff_sensors.get(r)},
        "reg": reg,
        "last_updated": last_updated,
    }


def _camera_card(space: dict) -> dict | None:
    if not space["camera"]:
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


def _tile(entity_id: str, name: str) -> dict:
    return {"type": "tile", "entity": entity_id, "name": name}


def _suffix_tiles(reg: dict, suffixes: tuple[str, ...]) -> list[dict]:
    return [
        _tile(reg[suffix], SUFFIX_LABELS[suffix])
        for suffix in suffixes
        if reg.get(suffix)
    ]


def _section(
    heading: str,
    cards: list[dict],
    *,
    column_span: int | None = None,
    heading_style: str = "subtitle",
) -> dict | None:
    """A grid section. Omitted when it would contain only a heading."""
    if not cards:
        return None
    section: dict[str, Any] = {
        "type": "grid",
        "cards": [_heading(heading, style=heading_style), *cards],
    }
    if column_span is not None:
        section["column_span"] = column_span
    return section


def _score_gauge(entity_id: str, name: str) -> dict:
    return {
        "type": "gauge",
        "entity": entity_id,
        "name": name,
        "min": 0,
        "max": 100,
        "severity": {"red": 0, "yellow": 50, "green": 75},
    }


def _badge(entity_id: str) -> dict:
    return {
        "type": "entity",
        "entity": entity_id,
        "visibility": [{"condition": "state", "entity": entity_id, "state": "on"}],
    }


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


def _reservoir_tiles(space: dict) -> list[dict]:
    sensors = space["sensors"]
    reg = space["reg"]
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


def build_space_view(space: dict) -> dict:
    reg = space["reg"]
    sections: list[dict] = []

    camera = _camera_card(space)
    watch = _section("Watch", [camera] if camera else [], column_span=2)
    if watch:
        sections.append(watch)

    lifecycle = _suffix_tiles(reg, LIFECYCLE_SUFFIXES)
    if reg.get("stage_projection"):
        lifecycle.append(_projection_markdown(reg["stage_projection"]))
    life = _section(space["title"], lifecycle, heading_style="title")
    if life:
        sections.append(life)

    ai: list[dict] = []
    if reg.get("ai_health_score"):
        ai.append(_score_gauge(reg["ai_health_score"], f"{space['title']} AI Health"))
    ai.extend(_suffix_tiles(reg, AI_TILE_SUFFIXES))
    ai_section = _section("AI", ai)
    if ai_section:
        sections.append(ai_section)

    reservoir = _reservoir_tiles(space)
    bands = _target_band_card(reg)
    if bands:
        reservoir.append(bands)
    reservoir_section = _section("Reservoir", reservoir)
    if reservoir_section:
        sections.append(reservoir_section)

    operations = _section("Operations", _operations_cards(reg))
    if operations:
        sections.append(operations)

    advisor_cards = (
        _advisor_cards(reg["ai_health_score"]) if reg.get("ai_health_score") else []
    )
    advisor = _section("Advisor", advisor_cards, column_span=2)
    if advisor:
        sections.append(advisor)

    plan = _plan_card(reg)
    plan_section = _section("Plan", [plan] if plan else [])
    if plan_section:
        sections.append(plan_section)

    return {
        "path": f"zone-{space['slug']}",
        "title": space["title"],
        "icon": "mdi:sprout",
        "type": "sections",
        "max_columns": 2,
        "sections": sections,
    }


def _trend_entities(spaces: list[dict]) -> list[str]:
    trend: list[str] = []
    for space in spaces:
        for role in ("water_temperature", "ph"):
            entity_id = space["sensors"].get(role)
            if entity_id:
                trend.append(entity_id)
    return trend


def _status_cards(space: dict) -> list[dict]:
    reg = space["reg"]
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
    ):
        if reg.get(suffix):
            cards.append(_tile(reg[suffix], SUFFIX_LABELS[suffix]))
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
        for suffix in ("metric_band_summary", "flush_due"):
            entity_id = space["reg"].get(suffix)
            if entity_id:
                badges.append(_badge(entity_id))

    trend = _trend_entities(spaces)
    if trend:
        sections.append(
            {
                "type": "grid",
                "column_span": max(len(spaces), 1),
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
    runtime = body.get("data", {}).get("runtime", {})
    return runtime.get("effective_sensor_mappings", {}) or {}


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
                spaces.append(classify(entry_id, title, registry, eff, states))

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
                ws, 3, {"type": "lovelace/config", "url_path": url_path}
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
                4,
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
