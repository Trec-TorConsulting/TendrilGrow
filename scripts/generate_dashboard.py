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

# Reservoir/air telemetry roles, in the order they should appear on cards.
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
# Compact subset used on the executive overview snapshot/trend cards.
SNAPSHOT_ROLES = ("ph", "ec", "cf", "tds", "orp", "water_temperature", "humidity")

# Cultivation-context helper entities, by unique-id suffix, in display order.
CTX_ORDER = (
    "ctx_strain",
    "ctx_stage",
    "ctx_week_in_stage",
    "ctx_site_count",
    "ctx_reservoir_volume_gal",
    "ctx_target_ph",
    "ctx_target_ec",
    "ctx_feed_interval_days",
    "ctx_lights_on_hours",
    "ctx_runoff_target_pct",
    "ctx_nutrient_line",
    "ctx_base_nutrients",
    "ctx_additives",
)
AI_ORDER = (
    "ai_health_score",
    "ai_health_summary",
    "ai_health_last_check",
    "ai_health_critical_alert",
    "run_ai_health_check",
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


def _entities_card(title: str, rows: list, **extra: Any) -> dict:
    card = {"type": "entities", "title": title, "state_color": True, "entities": rows}
    card.update(extra)
    return card


def classify(entry_id: str, title: str, registry: list, eff_sensors: dict) -> dict:
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


def _telemetry_rows(space: dict) -> list[str]:
    rows = [space["sensors"][r] for r in SENSOR_ROLE_ORDER if r in space["sensors"]]
    if space["reg"].get("vpd"):
        rows.append(space["reg"]["vpd"])
    if space["last_updated"]:
        rows.append(space["last_updated"])
    return rows


def _flush_card(space: dict) -> dict | None:
    reg = space["reg"]
    if "flush_now" not in reg:
        return None
    rows: list[Any] = [
        {"entity": reg["flush_now"], "name": "Flush now", "icon": "mdi:water-sync"}
    ]
    if reg.get("flush_interval_days"):
        rows.append({"entity": reg["flush_interval_days"], "name": "Flush interval"})
    rows.append({"type": "divider"})
    for suffix, name in (
        ("flush_due", "Flush due?"),
        ("days_since_flush", "Days since flush"),
        ("days_until_flush", "Days until next"),
        ("next_flush_due", "Next due"),
        ("last_flush", "Last flush"),
    ):
        if reg.get(suffix):
            rows.append({"entity": reg[suffix], "name": name})
    return _entities_card("Reservoir Flush", rows, show_header_toggle=False)


def _ai_cards(space: dict) -> list[dict]:
    reg = space["reg"]
    score = reg.get("ai_health_score")
    if not score:
        return []
    rows = [reg[s] for s in AI_ORDER if reg.get(s)]
    cards = [_entities_card("AI Health", rows)]
    cards.append(
        {
            "type": "markdown",
            "title": "AI Health Report",
            "content": f"{{{{ state_attr('{score}','report') }}}}",
        }
    )
    cards.append(
        {
            "type": "markdown",
            "title": "AI Feeding Schedule",
            "content": f"{{{{ state_attr('{score}','feeding_schedule_md') }}}}",
        }
    )
    return cards


def _timeline_card(space: dict) -> dict | None:
    reg = space["reg"]
    proj = reg.get("stage_projection")
    stage = reg.get("ctx_stage")
    week = reg.get("ctx_week_in_stage")
    if not proj:
        return None
    lines = []
    if stage and week:
        lines.append(
            f"**Stage:** {{{{ states('{stage}') }}}} (week {{{{ states('{week}') }}}})"
        )
    lines.append(f"**Days left in stage:** {{{{ states('{proj}') }}}} d")
    for label, attr in (
        ("Projected stage end", "projected_stage_end"),
        ("Projected harvest", "projected_harvest_date"),
        ("Projected ready", "projected_ready_date"),
    ):
        lines.append(f"**{label}:** {{{{ state_attr('{proj}','{attr}') }}}}")
    return {"type": "markdown", "title": "Grow Timeline", "content": "\n\n".join(lines)}


def _cultivation_card(space: dict) -> dict | None:
    reg = space["reg"]
    rows = [reg[s] for s in CTX_ORDER if reg.get(s)]
    if not rows:
        return None
    return {"type": "entities", "title": "Cultivation Plan", "entities": rows}


def build_space_view(space: dict) -> dict:
    cards: list[dict] = []
    camera = _camera_card(space)
    if camera:
        cards.append(camera)
    telemetry = _telemetry_rows(space)
    if telemetry:
        cards.append(_entities_card(f"{space['title']} Telemetry", telemetry))
    for builder in (_flush_card, _timeline_card):
        card = builder(space)
        if card:
            cards.append(card)
    cards.extend(_ai_cards(space))
    cultivation = _cultivation_card(space)
    if cultivation:
        cards.append(cultivation)
    return {
        "path": f"zone-{space['slug']}",
        "title": space["title"],
        "icon": "mdi:sprout",
        "cards": cards,
    }


def _grid(cards: list[dict]) -> dict:
    return {"type": "grid", "columns": 2, "square": False, "cards": cards}


def build_overview(spaces: list[dict]) -> dict:
    cards: list[dict] = []

    cameras = [c for c in (_camera_card(s) for s in spaces) if c]
    if cameras:
        cards.append(_grid(cameras))

    cards.append(
        {
            "type": "markdown",
            "content": (
                "## Operations Command Board\n\n"
                "Live reservoir chemistry, freshness, AI health, and lifecycle "
                "across all active grow spaces."
            ),
        }
    )

    freshness = []
    for space in spaces:
        reg = space["reg"]
        if "flush_now" not in reg:
            continue
        rows: list[Any] = [
            {"entity": reg["flush_now"], "name": "Flush now", "icon": "mdi:water-sync"}
        ]
        for suffix, name in (
            ("flush_due", "Flush due?"),
            ("days_since_flush", "Days since flush"),
            ("days_until_flush", "Days until next"),
        ):
            if reg.get(suffix):
                rows.append({"entity": reg[suffix], "name": name})
        freshness.append(
            _entities_card(
                f"{space['title']} Freshness", rows, show_header_toggle=False
            )
        )
    if freshness:
        cards.append(_grid(freshness))

    snapshots = []
    for space in spaces:
        rows = [space["sensors"][r] for r in SNAPSHOT_ROLES if r in space["sensors"]]
        if space["last_updated"]:
            rows.append(space["last_updated"])
        if rows:
            snapshots.append(_entities_card(f"{space['title']} Snapshot", rows))
    if snapshots:
        cards.append(_grid(snapshots))

    trend = []
    for space in spaces:
        for role in ("water_temperature", "ph"):
            if role in space["sensors"]:
                trend.append(space["sensors"][role])
    if trend:
        cards.append(
            {
                "type": "history-graph",
                "title": "Water Temperature and pH Trend (24h)",
                "hours_to_show": 24,
                "entities": trend,
            }
        )

    gauges = []
    for space in spaces:
        score = space["reg"].get("ai_health_score")
        if score:
            gauges.append(
                {
                    "type": "gauge",
                    "entity": score,
                    "name": f"{space['title']} AI Health",
                    "min": 0,
                    "max": 100,
                    "severity": {"red": 0, "yellow": 50, "green": 75},
                }
            )
    if gauges:
        cards.append(_grid(gauges))

    return {
        "path": "overview",
        "title": "Executive",
        "icon": "mdi:view-dashboard",
        "cards": cards,
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
                spaces.append(classify(entry_id, title, registry, eff))

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
