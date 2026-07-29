#!/usr/bin/env python3
"""Export a live Home Assistant Lovelace dashboard into this repo.

Connects to the running Home Assistant (``HA_URL`` / ``HA_TOKEN`` from the
environment or a local ``.env``) over the WebSocket API, lists the storage-mode
dashboards, and writes the chosen dashboard's raw configuration to
``dashboards/<url_path>.yaml`` so it can be tracked and templated in the repo.

Security:
- Reads ``HA_URL`` and ``HA_TOKEN`` from the environment or ``.env``.
- The token is used only for API auth; it is NEVER printed or logged.
- Makes only read-only WebSocket calls (dashboards list + lovelace config).

Usage::

    ./.venv/bin/python scripts/export_dashboard.py            # auto-pick TendrilGrow
    ./.venv/bin/python scripts/export_dashboard.py tendrilgrow  # explicit url_path
    ./.venv/bin/python scripts/export_dashboard.py --all       # export every dashboard
"""

from __future__ import annotations

import asyncio
import os
import ssl
import sys
from pathlib import Path
from typing import Any

import aiohttp
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "dashboards"


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


def _write_dashboard(url_path: str | None, title: str, config: dict[str, Any]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{_slug(url_path)}.yaml"
    header = (
        f"# Exported from the live Home Assistant dashboard '{title}'"
        f" (url_path: {url_path or 'default'}).\n"
        "# Entity ids are specific to the source install; adjust the grow-space\n"
        "# prefixes (e.g. tent_a_ / tent_b_) when reusing on another server.\n"
    )
    body = yaml.safe_dump(
        config, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    out.write_text(header + body, encoding="utf-8")
    return out


async def main() -> int:
    args = [a for a in sys.argv[1:]]
    export_all = "--all" in args
    explicit = next((a for a in args if not a.startswith("-")), None)

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
    print(f"Connecting to {url} (token never printed)")

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
            print(f"Found {len(dashboards)} storage-mode dashboard(s):")
            for d in dashboards:
                print(
                    f"  - title={d.get('title')!r} "
                    f"url_path={d.get('url_path')!r} mode={d.get('mode')}"
                )

            # Decide which dashboards to export.
            targets: list[dict[str, Any]] = []
            if export_all:
                targets = list(dashboards)
                # Include the default dashboard too.
                targets.append({"url_path": None, "title": "Overview (default)"})
            elif explicit:
                targets = [d for d in dashboards if d.get("url_path") == explicit] or [
                    {"url_path": explicit, "title": explicit}
                ]
            else:
                match = next(
                    (
                        d
                        for d in dashboards
                        if "tendril" in str(d.get("title", "")).lower()
                        or "tendril" in str(d.get("url_path", "")).lower()
                    ),
                    None,
                )
                if match is None:
                    print(
                        "\nNo dashboard title/url_path contains 'tendril'. "
                        "Re-run with an explicit url_path or --all."
                    )
                    return 1
                targets = [match]

            msg_id = 2
            written: list[Path] = []
            for d in targets:
                url_path = d.get("url_path")
                title = str(d.get("title") or url_path or "default")
                payload: dict[str, Any] = {"type": "lovelace/config"}
                if url_path:
                    payload["url_path"] = url_path
                res = await ws_call(ws, msg_id, payload)
                msg_id += 1
                if not res.get("success", False):
                    err = res.get("error", {})
                    print(f"  ! {title}: could not fetch config ({err})")
                    continue
                config = res.get("result", {}) or {}
                out = _write_dashboard(url_path, title, config)
                views = config.get("views", []) if isinstance(config, dict) else []
                written.append(out)
                print(f"  wrote {out.relative_to(ROOT)} ({len(views)} view/tab(s))")

    if not written:
        print("Nothing exported.")
        return 1
    print(
        f"\nExported {len(written)} dashboard file(s) to {OUT_DIR.relative_to(ROOT)}/"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
