#!/usr/bin/env python3
"""Read-only live validation of a TendrilGrow deployment.

Validates OpenSpec change ``add-foundation`` task 6.4: confirm the grow-space
model, sensor/control role mappings, derived-VPD inputs, Tuya water metrics, and
AI health entities fit real data on a running Home Assistant (for example, two
RDWC Vivosun tents).

Security:
- Reads ``HA_URL`` and ``HA_TOKEN`` from the environment or a local ``.env`` file.
- The token is used only for API auth; it is NEVER printed or logged.
- Makes only read-only API calls (config entries, registries, diagnostics, states).

Usage::

    ./.venv/bin/python scripts/validate_live_ha.py

Exit code 0 = all checks passed (warnings allowed); 1 = a hard failure.
"""

from __future__ import annotations

import asyncio
import math
import os
import ssl
from pathlib import Path
from typing import Any

import aiohttp

DOMAIN = "tendrilgrow"

AI_SUFFIXES = {
    "ai_health_score": "AI health score",
    "ai_health_summary": "AI summary",
    "ai_feeding_schedule": "AI feeding schedule",
    "ai_health_last_check": "AI last check",
    "ai_health_critical_alert": "AI critical alert",
    "run_ai_health_check": "Run button",
}

CONTROL_ROLES = ("lights", "fans", "inline_fans")

# Planned pump/power roles (change: add-pump-power-control). Reported when mapped.
PUMP_ROLES = ("rdwc_pump", "chiller_pump", "air_pump")
PUMP_POWER_ROLES = ("rdwc_pump_power", "chiller_pump_power", "air_pump_power")

# Reservoir flush tracking entity suffixes (change: add-flush-tracking).
# Ordered longest-first so "next_flush_due" is matched before "flush_due".
FLUSH_REPORT = (
    ("last_flush", "last flush"),
    ("days_since_flush", "days since"),
    ("days_until_flush", "days until"),
    ("next_flush_due", "next due"),
    ("flush_due", "due"),
)

# Plausible ranges for sanity-checking live readings.
PLAUSIBLE: dict[str, tuple[float, float]] = {
    "ph": (3.5, 8.5),
    "ec": (0.0, 6.0),
    "tds": (0.0, 3000.0),
    "cf": (0.0, 60.0),
    "orp": (-500.0, 1000.0),
    # Wide enough to accept either Celsius or Fahrenheit readings.
    "temperature": (0.0, 120.0),
    "water_temperature": (0.0, 120.0),
    "humidity": (0.0, 100.0),
}

GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"


class Report:
    """Accumulates pass/warn/fail lines and counts."""

    def __init__(self) -> None:
        self.failures = 0
        self.warnings = 0

    def ok(self, msg: str) -> None:
        print(f"  {GREEN}PASS{RESET} {msg}")

    def warn(self, msg: str) -> None:
        self.warnings += 1
        print(f"  {YELLOW}WARN{RESET} {msg}")

    def fail(self, msg: str) -> None:
        self.failures += 1
        print(f"  {RED}FAIL{RESET} {msg}")


def load_env() -> dict[str, str]:
    """Load config from ``.env`` then let real env vars take precedence."""
    env: dict[str, str] = {}
    dotenv = Path(__file__).resolve().parents[1] / ".env"
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


def compute_vpd(temp_c: float | None, humidity: float | None) -> float | None:
    """Vapor pressure deficit (kPa), mirroring the integration's formula."""
    if temp_c is None or humidity is None or humidity <= 0 or humidity > 100:
        return None
    svp = 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    return round(svp * (1 - humidity / 100.0), 3)


def fahrenheit_to_celsius(value: float | None, unit: str | None) -> float | None:
    """Convert to Celsius when the unit is Fahrenheit; else pass through."""
    if value is None:
        return None
    if str(unit or "").strip().lower().replace("\u00b0", "") in ("f", "fahrenheit"):
        return (value - 32.0) * 5.0 / 9.0
    return value


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


async def fetch_states(session: aiohttp.ClientSession, url: str) -> dict[str, dict]:
    states: dict[str, dict[str, Any]] = {}
    timeout = aiohttp.ClientTimeout(total=30)
    async with session.get(f"{url}/api/states", timeout=timeout) as resp:
        for st in await resp.json():
            states[st["entity_id"]] = st
    return states


async def fetch_ws_data(
    session: aiohttp.ClientSession,
    ws_url: str,
    token: str,
    ssl_ctx: ssl.SSLContext | None,
    report: Report,
) -> tuple[list[dict], list[dict]]:
    """Return (config_entries, entity_registry) for the tendrilgrow domain."""
    timeout = aiohttp.ClientTimeout(total=20)
    async with session.ws_connect(ws_url, ssl=ssl_ctx, timeout=timeout) as ws:
        await ws.receive_json()  # auth_required
        await ws.send_json({"type": "auth", "access_token": token})
        auth = await ws.receive_json()
        if auth.get("type") != "auth_ok":
            report.fail("WebSocket auth failed (valid token / admin user?)")
            return [], []
        res = await ws_call(ws, 1, {"type": "config_entries/get"})
        entries = [e for e in res.get("result", []) if e.get("domain") == DOMAIN]
        res = await ws_call(ws, 2, {"type": "config/entity_registry/list"})
        registry = [e for e in res.get("result", []) if e.get("platform") == DOMAIN]
    return entries, registry


async def fetch_diagnostics(
    session: aiohttp.ClientSession, url: str, entry_id: str
) -> dict[str, Any]:
    """Fetch redacted config-entry diagnostics; return {} if unavailable."""
    endpoint = f"{url}/api/diagnostics/config_entry/{entry_id}"
    timeout = aiohttp.ClientTimeout(total=20)
    try:
        async with session.get(endpoint, timeout=timeout) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception:  # noqa: BLE001
        return {}
    return {}


def validate_space(
    r: Report,
    diag: dict[str, Any],
    ents: list[dict[str, Any]],
    states: dict[str, dict[str, Any]],
) -> None:
    # HA wraps the integration's diagnostics under a top-level "data" envelope
    # (alongside home_assistant/custom_components/etc.). Unwrap it first.
    payload = diag.get("data", diag) if diag else {}
    data = payload.get("data", {}) or {}
    options = payload.get("options", {}) or {}
    runtime = payload.get("runtime", {}) or {}
    mappings = (
        runtime.get("effective_sensor_mappings")
        or {**data.get("sensor_mappings", {}), **options.get("sensor_mappings", {})}
        or {}
    )
    controls = (
        runtime.get("effective_control_mappings")
        or {
            **data.get("control_mappings", {}),
            **options.get("control_mappings", {}),
        }
        or {}
    )

    if payload:
        r.ok(
            f"grow_type={data.get('grow_type')} "
            f"tuya_enabled={data.get('tuya_enabled')} "
            f"ai_provider={data.get('ai_provider')} "
            f"ai_model={data.get('ai_model') or 'n/a'}"
        )
    else:
        r.warn("Diagnostics unavailable; validating from registry/states only")

    def check_mapped(role: str) -> float | None:
        entity_id = mappings.get(role)
        if not entity_id:
            return None
        st = states.get(entity_id)
        if st is None:
            r.warn(f"role '{role}' -> {entity_id} (no state)")
            return None
        val = st.get("state")
        num = to_float(val)
        if num is not None and role in PLAUSIBLE:
            lo, hi = PLAUSIBLE[role]
            if lo <= num <= hi:
                r.ok(f"role '{role}' -> {entity_id} = {val} (plausible)")
            else:
                r.warn(f"role '{role}' -> {entity_id} = {val} (outside {lo}-{hi})")
        else:
            r.ok(f"role '{role}' -> {entity_id} = {val}")
        return num

    temp = check_mapped("temperature")
    hum = check_mapped("humidity")
    for role in ("water_temperature", "ph", "ec", "cf", "orp", "tds", "light_ppfd"):
        if mappings.get(role):
            check_mapped(role)

    temp_entity_id = mappings.get("temperature")
    temp_unit = ""
    if temp_entity_id and temp_entity_id in states:
        temp_unit = (
            states[temp_entity_id].get("attributes", {}).get("unit_of_measurement", "")
        )
    vpd = compute_vpd(fahrenheit_to_celsius(temp, temp_unit), hum)
    if vpd is not None:
        good = 0.4 <= vpd <= 2.0
        msg = f"Derived VPD = {vpd} kPa (air temp {temp} {temp_unit})".rstrip()
        (r.ok if good else r.warn)(msg if good else f"{msg} (unusual; check units)")
        if "water" in str(temp_entity_id or "").lower():
            r.warn(
                "VPD 'temperature' role maps a WATER-temp entity; map an AIR "
                "temperature probe to the temperature role for canopy VPD"
            )
    else:
        r.warn("VPD not computable (air temperature/humidity unmapped or invalid)")

    camera = mappings.get("camera")
    if camera:
        cam = states.get(camera)
        if cam is None:
            r.warn(f"camera -> {camera} (entity not found)")
        else:
            r.ok(f"camera -> {camera} ({cam.get('state')})")
    else:
        r.warn("No camera mapped: AI vision checks cannot run here")

    mapped_controls = [role for role in CONTROL_ROLES if controls.get(role)]
    if mapped_controls:
        r.ok(f"control roles mapped: {', '.join(mapped_controls)}")

    # Pump/power roles are a planned capability; report only when mapped.
    for role in PUMP_ROLES:
        entity_id = controls.get(role)
        if not entity_id:
            continue
        st = states.get(entity_id)
        state_val = st.get("state") if st else "no state"
        r.ok(f"pump '{role}' -> {entity_id} = {state_val}")

    # Report per-pump power sensors
    pump_power_mapped = []
    for role in PUMP_POWER_ROLES:
        entity_id = mappings.get(role)
        if not entity_id:
            continue
        pump_power_mapped.append((role, entity_id))
        st = states.get(entity_id)
        state_val = st.get("state") if st else "no state"
        unit = st.get("attributes", {}).get("unit_of_measurement", "") if st else ""
        r.ok(f"power '{role}' -> {entity_id} = {state_val} {unit}".rstrip())

    # Report total pump power sensor (derived from per-pump sensors)
    grow_name = data.get("name", "")
    total_power_entity = (
        f"sensor.{grow_name.lower().replace(' ', '_')}_total_pump_power"
    )
    if pump_power_mapped:
        total = states.get(total_power_entity)
        if total:
            val = total.get("state")
            unit = total.get("attributes", {}).get("unit_of_measurement", "")
            r.ok(f"total pump power -> {total_power_entity} = {val} {unit}".rstrip())
        else:
            r.warn(
                f"total pump power sensor {total_power_entity} not found "
                "(expected when pumps have power sensors mapped)"
            )

    # Reservoir flush tracking (add-flush-tracking): resolve entities from the
    # registry by unique-id suffix and report their current states.
    flush_by_suffix: dict[str, str] = {}
    for ent in ents:
        uid = str(ent.get("unique_id", ""))
        for suffix, _label in FLUSH_REPORT:
            if uid.endswith(f"_{suffix}"):
                flush_by_suffix[suffix] = ent.get("entity_id")
                break
    if flush_by_suffix:
        for suffix, label in FLUSH_REPORT:
            entity_id = flush_by_suffix.get(suffix)
            if not entity_id:
                continue
            st = states.get(entity_id)
            val = st.get("state") if st else "no state"
            r.ok(f"flush {label} -> {entity_id} = {val}")
    else:
        r.warn("flush tracking entities not found in registry for this space")

    # Lifecycle stage + projection (change: add-grow-lifecycle-stages).
    stage_id = next(
        (
            e.get("entity_id")
            for e in ents
            if str(e.get("unique_id", "")).endswith("_ctx_stage")
        ),
        None,
    )
    if stage_id:
        st = states.get(stage_id)
        r.ok(f"growth stage -> {stage_id} = {st.get('state') if st else 'no state'}")
    projection_id = next(
        (
            e.get("entity_id")
            for e in ents
            if str(e.get("unique_id", "")).endswith("_stage_projection")
        ),
        None,
    )
    if projection_id:
        st = states.get(projection_id)
        attrs = st.get("attributes", {}) if st else {}
        r.ok(
            f"stage projection -> {projection_id} = "
            f"{st.get('state') if st else 'no state'} d "
            f"(harvest {attrs.get('projected_harvest_date')}, "
            f"ready {attrs.get('projected_ready_date')})"
        )
    else:
        r.warn("stage-projection sensor not found in registry for this space")

    reg_suffixes = {
        suffix
        for ent in ents
        for suffix in AI_SUFFIXES
        if str(ent.get("unique_id", "")).endswith(suffix)
    }
    present = [name for suffix, name in AI_SUFFIXES.items() if suffix in reg_suffixes]
    if present:
        r.ok(f"AI health entities present: {len(present)}/{len(AI_SUFFIXES)}")
    else:
        r.warn("AI health entities not found in registry for this space")

    ai_health = runtime.get("ai_health") or {}
    latest = ai_health.get("latest")
    if latest:
        r.ok(
            f"latest AI check: score={latest.get('score')} "
            f"severity={latest.get('severity')} "
            f"provider={latest.get('provider')} at {latest.get('checked_at')}"
        )
    elif ai_health:
        count = ai_health.get("history_count", 0)
        r.warn(f"no AI check has run yet (history_count={count})")


async def main() -> int:
    env = load_env()
    url = (env.get("HA_URL") or "").rstrip("/")
    token = env.get("HA_TOKEN") or ""
    insecure = env.get("HA_INSECURE", "0") in ("1", "true", "True")

    if not url or not token:
        print(
            f"{RED}Missing HA_URL or HA_TOKEN.{RESET} "
            "Copy .env.example to .env and fill it in."
        )
        return 1

    ws_url = (
        url.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"
    )
    headers = {"Authorization": f"Bearer {token}"}
    ssl_ctx = build_ssl(insecure)

    r = Report()
    print(f"{BOLD}TendrilGrow live validation{RESET}  ->  {url}")
    print("(read-only; token is never printed)\n")

    connector = aiohttp.TCPConnector(ssl=ssl_ctx) if ssl_ctx else None
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with session.get(f"{url}/api/", timeout=timeout) as resp:
                if resp.status != 200:
                    r.fail(f"REST /api/ returned HTTP {resp.status} (token/URL?)")
                    return 1
        except Exception as err:  # noqa: BLE001
            r.fail(f"Cannot reach {url}: {err}")
            return 1
        r.ok("Authenticated to Home Assistant REST API")

        states = await fetch_states(session, url)

        entries: list[dict[str, Any]] = []
        registry: list[dict[str, Any]] = []
        try:
            entries, registry = await fetch_ws_data(session, ws_url, token, ssl_ctx, r)
        except Exception as err:  # noqa: BLE001
            r.warn(f"WebSocket introspection unavailable ({err}); REST only")

        if not entries:
            r.fail(f"No '{DOMAIN}' config entries found. Is it configured?")
            return 1
        plural = "y" if len(entries) == 1 else "ies"
        r.ok(f"Found {len(entries)} grow-space config entr{plural}")
        if len(entries) < 2:
            r.warn("Reference system has 2 tents; found fewer")

        by_entry: dict[str, list[dict[str, Any]]] = {}
        for ent in registry:
            by_entry.setdefault(ent.get("config_entry_id"), []).append(ent)

        for entry in entries:
            entry_id = entry["entry_id"]
            title = entry.get("title", entry_id)
            print(f"\n{BOLD}Grow space: {title}{RESET}  ({entry.get('state')})")
            if entry.get("state") not in (None, "loaded"):
                r.fail(f"Entry not loaded (state={entry.get('state')})")
            diag = await fetch_diagnostics(session, url, entry_id)
            validate_space(r, diag, by_entry.get(entry_id, []), states)

    print(f"\n{BOLD}Summary:{RESET} {r.warnings} warning(s), {r.failures} failure(s)")
    if r.failures:
        print(f"{RED}Live validation FAILED.{RESET}")
        return 1
    tail = " (with warnings)." if r.warnings else "."
    print(f"{GREEN}Live validation PASSED{RESET}{tail}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130)
