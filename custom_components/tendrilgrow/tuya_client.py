"""Tuya cloud API client and DP normalization helpers."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any

import aiohttp

LOGGER = logging.getLogger(__name__)

TUYA_REGIONS: dict[str, str] = {
    "us": "https://openapi.tuyaus.com",
    "eu": "https://openapi.tuyaeu.com",
    "cn": "https://openapi.tuyacn.com",
    "in": "https://openapi.tuyain.com",
}

_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()

# Tuya DP code -> normalized TendrilGrow metric key.
_WATER_DP_MAP: dict[str, str] = {
    "tds_in": "tds",
    "tds_out": "tds",
    "tds_value": "tds",
    "tds": "tds",
    "ppm": "tds",
    "ppm_value": "tds",
    "ph_value": "ph",
    "ph": "ph",
    "ph_current": "ph",
    "ph_sensor": "ph",
    "ec_value": "ec",
    "ec": "ec",
    "ec_current": "ec",
    "conductivity_value": "ec",
    "cf": "cf",
    "cf_value": "cf",
    "orp_value": "orp",
    "orp": "orp",
    "water_temp": "water_temp_c",
    "temp_value": "water_temp_c",
    "temp_current": "water_temp_c",
    "air_temp": "ambient_temp_c",
    "ambient_temp": "ambient_temp_c",
    "humidity": "ambient_humidity",
    "humiity": "ambient_humidity",
    "battery_percentage": "battery_pct",
    "battery_state": "battery_pct",
}


class TuyaApiError(RuntimeError):
    """Raised when Tuya OpenAPI returns a failed result."""


def normalize_tuya_statuses(statuses: list[dict[str, Any]]) -> dict[str, float]:
    """Normalize Tuya status items into stable water metrics.

    Supports Tuya shadow/property status entries and v1 status entries.
    """
    reading: dict[str, float] = {}

    for status in statuses:
        code = str(status.get("code", "")).lower().strip()
        if not code or code not in _WATER_DP_MAP:
            continue

        raw_value = status.get("value")
        value = _coerce_float(raw_value)
        if value is None:
            continue

        scale = _coerce_int(status.get("scale"))
        scaled_value = (
            value / (10**scale)
            if scale is not None and scale > 0 and float(value).is_integer()
            else None
        )

        key = _WATER_DP_MAP[code]
        if key in {"water_temp_c", "ambient_temp_c"}:
            reading[key] = scaled_value if scaled_value is not None else (value / 10 if value > 60 else value)
        elif key == "ec":
            reading[key] = scaled_value if scaled_value is not None else (value / 1000 if value > 20 else value)
        elif key == "ph":
            reading[key] = scaled_value if scaled_value is not None else (value / 100 if value > 14 else value)
        else:
            reading[key] = scaled_value if scaled_value is not None else value

    _derive_missing_fields(reading)
    return reading


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _derive_missing_fields(reading: dict[str, float]) -> None:
    # Many Tuya devices only expose TDS. Keep a derived EC for grow logic.
    if "tds" in reading and "ec" not in reading:
        reading["ec"] = round(reading["tds"] / 500.0, 3)
    elif "ec" in reading and "tds" not in reading:
        reading["tds"] = round(reading["ec"] * 500.0, 1)

    # When only one conductivity measure is available, carry it across aliases.
    if "ec" in reading and "cf" not in reading:
        reading["cf"] = reading["ec"]
    elif "cf" in reading and "ec" not in reading:
        reading["ec"] = reading["cf"]


class TuyaCloudClient:
    """Minimal Tuya OpenAPI client for polling device metrics."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        access_id: str,
        access_secret: str,
        region: str,
    ) -> None:
        self._session = session
        self._access_id = access_id
        self._access_secret = access_secret
        self._region = region if region in TUYA_REGIONS else "us"
        self._token: str | None = None
        self._token_expiry: float = 0.0

    @property
    def base_url(self) -> str:
        return TUYA_REGIONS[self._region]

    def _sign(self, method: str, path: str, timestamp: str, token: str = "", body: str = "") -> str:
        content_sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest() if body else _EMPTY_SHA256
        string_to_sign = f"{self._access_id}{token}{timestamp}{method}\\n{content_sha256}\\n\\n{path}"
        return (
            hmac.new(
                self._access_secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                hashlib.sha256,
            )
            .hexdigest()
            .upper()
        )

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry:
            return self._token

        path = "/v1.0/token?grant_type=1"
        timestamp = str(int(time.time() * 1000))
        sign = self._sign("GET", path, timestamp)
        payload = await self._request_json(
            "GET",
            path,
            headers={
                "client_id": self._access_id,
                "sign": sign,
                "t": timestamp,
                "sign_method": "HMAC-SHA256",
            },
        )

        if not payload.get("success"):
            raise TuyaApiError(f"Token error: {payload.get('msg', 'unknown')}")

        result = payload.get("result", {})
        token = result.get("access_token")
        if not token:
            raise TuyaApiError("Token error: missing access token")

        expire_time = float(result.get("expire_time", 7200))
        self._token = token
        self._token_expiry = time.time() + expire_time - 60
        return token

    async def api_get(self, path: str) -> dict[str, Any]:
        token = await self._get_token()
        timestamp = str(int(time.time() * 1000))
        sign = self._sign("GET", path, timestamp, token)
        payload = await self._request_json(
            "GET",
            path,
            headers={
                "client_id": self._access_id,
                "access_token": token,
                "sign": sign,
                "t": timestamp,
                "sign_method": "HMAC-SHA256",
            },
        )

        if not payload.get("success"):
            raise TuyaApiError(f"{payload.get('msg', 'request failed')} (code={payload.get('code')})")
        return payload

    async def list_user_devices(self, uid: str) -> list[dict[str, Any]]:
        payload = await self.api_get(f"/v1.0/users/{uid}/devices")
        result = payload.get("result")
        if isinstance(result, list):
            return result
        return []

    async def fetch_device_statuses(self, device_id: str) -> list[dict[str, Any]]:
        shadow_statuses = await self._fetch_shadow_properties(device_id)
        if shadow_statuses:
            return shadow_statuses

        payload = await self.api_get(f"/v1.0/devices/{device_id}/status")
        result = payload.get("result")
        if isinstance(result, list):
            return result
        return []

    async def _fetch_shadow_properties(self, device_id: str) -> list[dict[str, Any]]:
        try:
            payload = await self.api_get(f"/v2.0/cloud/thing/{device_id}/shadow/properties")
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("Shadow property fetch failed for %s: %s", device_id, err)
            return []

        properties = payload.get("result", {}).get("properties", [])
        if not isinstance(properties, list):
            return []

        statuses: list[dict[str, Any]] = []
        for prop in properties:
            code = prop.get("code")
            value = prop.get("value")
            if code is None or value is None:
                continue
            item: dict[str, Any] = {"code": code, "value": value}
            if prop.get("scale") is not None:
                item["scale"] = prop.get("scale")
            statuses.append(item)
        return statuses

    async def _request_json(self, method: str, path: str, headers: dict[str, str]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        async with self._session.request(method, url, headers=headers) as response:
            response.raise_for_status()
            payload = await response.json(content_type=None)
            if isinstance(payload, dict):
                return payload
            raise TuyaApiError("Unexpected non-object response payload")