#!/usr/bin/env python3
"""Import a repo dashboard YAML into the live Home Assistant Lovelace store.

Counterpart to ``export_dashboard.py``: reads ``dashboards/<url_path>.yaml`` from
this repo and pushes it to the matching storage-mode dashboard on the running
Home Assistant over the WebSocket API. This keeps the live dashboard in sync
after the repo copy has been edited (new cards, renamed entity ids, etc.).

Security:
- Reads ``HA_URL`` and ``HA_TOKEN`` from the environment or a local ``.env`` file.
- The token is used only for API auth; it is NEVER printed or logged.
- Dry-run by default. A live backup is written before any change, and the save
  only runs when ``--apply`` is passed.

Usage::

    ./.venv/bin/python scripts/import_dashboard.py                 # dry-run TendrilGrow
    ./.venv/bin/python scripts/import_dashboard.py --apply         # push TendrilGrow
    ./.venv/bin/python scripts/import_dashboard.py tendrial-grow --apply
    ./.venv/bin/python scripts/import_dashboard.py --all --apply   # every file

Exit code 0 = success (dry-run or applied); 1 = a hard failure.
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
IN_DIR = ROOT / "dashboards"


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


async def ws_call(
    ws: aiohttp.ClientWebSocketResponse, msg_id: int, payload: dict
) -> dict:
    await ws.send_json({"id": msg_id, **payload})
    while True:
        msg = await ws.receive_json()
        if msg.get("id") == msg_id and msg.get("type") == "result":
            return msg


def _slug(url_path: str | None) -> str:
    return (url_path or "default").replace("-", "_")


def _url_kw(url_path: str | None) -> dict[str, str]:
    return {"url_path": url_path} if url_path else {}


def _read_dashboard(url_path: str | None) -> tuple[Path, dict[str, Any]]:
    """Load the repo YAML for ``url_path`` (comments are ignored by the parser)."""
    path = IN_DIR / f"{_slug(url_path)}.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"{path} did not parse into a mapping")
    return path, config


def _count(config: dict[str, Any]) -> tuple[int, int]:
    """Return (views, total cards) for a quick before/after summary."""

    def cards(node: Any) -> int:
        total = 0
        if isinstance(node, dict):
            if node.get("type"):
                total += 1
            total += cards(node.get("cards"))
        elif isinstance(node, list):
            for item in node:
                total += cards(item)
        return total

    views = config.get("views", []) if isinstance(config, dict) else []
    return len(views), sum(cards(v.get("cards")) for v in views)


def _collect_entity_ids(node: Any, acc: set[str]) -> None:
    """Gather explicit entity ids from ``entity:``/``entities:`` (not templates)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "entity" and isinstance(value, str):
                acc.add(value)
            elif key == "entities" and isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        acc.add(item)
                    elif isinstance(item, dict) and isinstance(item.get("entity"), str):
                        acc.add(item["entity"])
            else:
                _collect_entity_ids(value, acc)
    elif isinstance(node, list):
        for item in node:
            _collect_entity_ids(item, acc)


def _backup(url_path: str | None, config: dict[str, Any]) -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"tendrilgrow-dash-backup-{_slug(url_path)}-{ts}.yaml"
    out = Path(tempfile.gettempdir()) / name
    out.write_text(
        yaml.safe_dump(
            config, default_flow_style=False, sort_keys=False, allow_unicode=True
        ),
        encoding="utf-8",
    )
    return out


def _resolve_targets(
    args: list[str], dashboards: list[dict[str, Any]]
) -> list[dict[str, Any]] | None:
    """Decide which (url_path, title) dashboards to push."""
    import_all = "--all" in args
    explicit = next((a for a in args if not a.startswith("-")), None)

    if import_all:
        targets: list[dict[str, Any]] = []
        for path in sorted(IN_DIR.glob("*.yaml")):
            stem = path.stem
            match = next(
                (d for d in dashboards if _slug(d.get("url_path")) == stem), None
            )
            if match is not None:
                targets.append(match)
            elif stem == "default":
                targets.append({"url_path": None, "title": "Overview (default)"})
            else:
                print(f"  ! {path.name}: no live dashboard for slug '{stem}' (skip)")
        return targets

    if explicit:
        match = next((d for d in dashboards if d.get("url_path") == explicit), None)
        return [match or {"url_path": explicit, "title": explicit}]

    # "tendri" matches both the correct "tendril*" and the live "Tendrial" typo.
    match = next(
        (
            d
            for d in dashboards
            if "tendri" in str(d.get("title", "")).lower()
            or "tendri" in str(d.get("url_path", "")).lower()
        ),
        None,
    )
    if match is None:
        print(
            "\nNo dashboard title/url_path contains 'tendri'. "
            "Re-run with an explicit url_path or --all."
        )
        return None
    return [match]


async def main() -> int:
    args = sys.argv[1:]
    apply = ("--apply" in args) or ("-y" in args)

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
        timeout = aiohttp.ClientTimeout(total=30)
        async with session.ws_connect(ws_url, ssl=ssl_ctx, timeout=timeout) as ws:
            await ws.receive_json()  # auth_required
            await ws.send_json({"type": "auth", "access_token": token})
            auth = await ws.receive_json()
            if auth.get("type") != "auth_ok":
                print("WebSocket auth failed (valid token / admin user?)")
                return 1

            res = await ws_call(ws, 1, {"type": "lovelace/dashboards/list"})
            dashboards = res.get("result", []) or []
            targets = _resolve_targets(args, dashboards)
            if targets is None:
                return 1

            states = await ws_call(ws, 2, {"type": "get_states"})
            known = {s.get("entity_id") for s in (states.get("result", []) or [])}

            msg_id = 3
            changed = 0
            for d in targets:
                url_path = d.get("url_path")
                title = str(d.get("title") or url_path or "default")
                try:
                    src, new_config = _read_dashboard(url_path)
                except (FileNotFoundError, ValueError) as err:
                    print(f"\n{title}: {err}")
                    continue

                res = await ws_call(
                    ws, msg_id, {"type": "lovelace/config", **_url_kw(url_path)}
                )
                msg_id += 1
                live_config = res.get("result", {}) if res.get("success") else {}

                nv, nc = _count(new_config)
                lv, lc = _count(live_config) if live_config else (0, 0)
                print(f"\n=== {title} (url_path={url_path!r}) ===")
                print(f"  source: {src.relative_to(ROOT)}")
                print(f"  live now : {lv} views / {lc} cards")
                print(f"  will push: {nv} views / {nc} cards")

                refs: set[str] = set()
                _collect_entity_ids(new_config, refs)
                missing = sorted(r for r in refs if r not in known)
                if missing:
                    print(f"  WARNING: {len(missing)} referenced id(s) not live:")
                    for m in missing:
                        print(f"    - {m}")

                if not apply:
                    continue

                backup = _backup(url_path, live_config) if live_config else None
                if backup:
                    print(f"  backed up live -> {backup}")
                save = await ws_call(
                    ws,
                    msg_id,
                    {
                        "type": "lovelace/config/save",
                        **_url_kw(url_path),
                        "config": new_config,
                    },
                )
                msg_id += 1
                if not save.get("success", False):
                    print(f"  SAVE FAILED: {save.get('error')}")
                    continue
                print("  saved to live Home Assistant.")
                changed += 1

    if not apply:
        print("\nDRY RUN — nothing saved. Re-run with --apply to push.")
    else:
        print(f"\nApplied {changed} dashboard(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
