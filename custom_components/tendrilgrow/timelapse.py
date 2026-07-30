"""Timelapse capture and assembly helpers for TendrilGrow."""

from __future__ import annotations

import asyncio
import logging
import shlex
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    CONF_TIMELAPSE_DIR,
    CONF_TIMELAPSE_RETENTION_FRAMES,
    DEFAULT_TIMELAPSE_RETENTION_FRAMES,
    DOMAIN,
    SENSOR_ROLE_CAMERA,
)

LOGGER = logging.getLogger(__name__)

_FRAME_PREFIX = "frame-"
_FRAME_SUFFIX = ".jpg"
_TIMELAPSE_SIGNAL_PREFIX = f"{DOMAIN}_timelapse_"


@dataclass(slots=True, frozen=True)
class TimelapsePaths:
    """Resolved file-system and local URL locations for one grow space."""

    directory: Path
    local_url_base: str | None


@dataclass(slots=True, frozen=True)
class CaptureResult:
    """Result of one timelapse frame-capture attempt."""

    success: bool
    capture_dir: Path
    frame_path: Path | None
    allowlist_error: bool
    error: str | None = None


def timelapse_dispatcher_signal(entry_id: str) -> str:
    """Return dispatcher signal for timelapse updates for one entry."""
    return f"{_TIMELAPSE_SIGNAL_PREFIX}{entry_id}"


def resolve_timelapse_paths(
    config_dir: str,
    grow_space_name: str,
    override_dir: str | None,
) -> TimelapsePaths:
    """Resolve timelapse directory and local URL base for a grow space."""
    base_config = Path(config_dir)
    configured = (override_dir or "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = base_config / candidate
        directory = candidate
    else:
        directory = (
            base_config
            / "www"
            / "tendrilgrow"
            / slugify(grow_space_name)
            / "timelapse"
        )

    return TimelapsePaths(
        directory=directory,
        local_url_base=_local_url_for_path(base_config, directory),
    )


def _local_url_for_path(config_root: Path, target: Path) -> str | None:
    """Translate <config>/www/* to /local/* and return None otherwise."""
    www_root = (config_root / "www").resolve()
    resolved = target.resolve()
    try:
        relative = resolved.relative_to(www_root)
    except ValueError:
        return None
    return f"/local/{relative.as_posix()}"


def build_frame_filename(now: datetime) -> str:
    """Build a deterministic timelapse frame filename for a timestamp."""
    ts = dt_util.as_utc(now).strftime("%Y%m%d-%H%M%S")
    return f"{_FRAME_PREFIX}{ts}{_FRAME_SUFFIX}"


def parse_frame_timestamp(path: Path) -> datetime | None:
    """Parse UTC timestamp from a frame filename."""
    name = path.name
    if not (name.startswith(_FRAME_PREFIX) and name.endswith(_FRAME_SUFFIX)):
        return None
    stamp = name[len(_FRAME_PREFIX) : -len(_FRAME_SUFFIX)]
    try:
        parsed = datetime.strptime(stamp, "%Y%m%d-%H%M%S")
    except ValueError:
        return None
    return dt_util.as_utc(parsed)


def list_frame_files(directory: Path) -> list[Path]:
    """Return known frame files sorted oldest-first by filename."""
    return sorted(
        directory.glob(f"{_FRAME_PREFIX}*{_FRAME_SUFFIX}"),
        key=lambda p: p.name,
    )


def select_frames_to_prune(files: list[Path], retention_cap: int) -> list[Path]:
    """Select oldest files that should be deleted to satisfy retention cap."""
    if retention_cap < 1:
        retention_cap = 1
    ordered = sorted(files, key=lambda p: p.name)
    overflow = len(ordered) - retention_cap
    if overflow <= 0:
        return []
    return ordered[:overflow]


def build_ffmpeg_command(
    ffmpeg_bin: str,
    frame_glob: str,
    framerate: int,
    output_path: str,
) -> list[str]:
    """Build ffmpeg command for frame-sequence timelapse assembly."""
    safe_rate = max(1, int(framerate))
    return [
        ffmpeg_bin,
        "-y",
        "-framerate",
        str(safe_rate),
        "-pattern_type",
        "glob",
        "-i",
        frame_glob,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        output_path,
    ]


def is_probable_allowlist_error(error: Exception | str) -> bool:
    """Return True when an error likely indicates allow-list write restriction."""
    message = str(error).lower()
    probes = (
        "allowlist_external_dirs",
        "not allowlisted",
        "not allow-listed",
        "no access to path",
        "path is not whitelisted",
    )
    return any(probe in message for probe in probes)


async def async_capture_frame(
    hass: HomeAssistant,
    entry: ConfigEntry,
    grow_space: Any,
    merged_config: dict[str, Any],
) -> CaptureResult:
    """Capture one timelapse frame, verify write, and enforce retention."""
    paths = resolve_timelapse_paths(
        hass.config.config_dir,
        getattr(grow_space, "name", entry.title),
        merged_config.get(CONF_TIMELAPSE_DIR),
    )
    camera_entity_id = getattr(grow_space, "sensor_mappings", {}).get(
        SENSOR_ROLE_CAMERA
    )
    if not camera_entity_id:
        return CaptureResult(
            success=False,
            capture_dir=paths.directory,
            frame_path=None,
            allowlist_error=False,
            error="No camera is mapped for this grow space",
        )

    retention = int(
        merged_config.get(
            CONF_TIMELAPSE_RETENTION_FRAMES,
            DEFAULT_TIMELAPSE_RETENTION_FRAMES,
        )
        or DEFAULT_TIMELAPSE_RETENTION_FRAMES
    )

    await asyncio.to_thread(paths.directory.mkdir, parents=True, exist_ok=True)
    frame_path = paths.directory / build_frame_filename(dt_util.utcnow())
    try:
        await hass.services.async_call(
            "camera",
            "snapshot",
            {"entity_id": camera_entity_id, "filename": str(frame_path)},
            blocking=True,
        )
    except Exception as err:  # noqa: BLE001
        return CaptureResult(
            success=False,
            capture_dir=paths.directory,
            frame_path=frame_path,
            allowlist_error=is_probable_allowlist_error(err),
            error=str(err),
        )

    exists = await asyncio.to_thread(frame_path.exists)
    if not exists:
        return CaptureResult(
            success=False,
            capture_dir=paths.directory,
            frame_path=frame_path,
            allowlist_error=False,
            error="Snapshot did not produce a frame file",
        )

    all_frames = await asyncio.to_thread(list_frame_files, paths.directory)
    prune = select_frames_to_prune(all_frames, retention)
    for file_path in prune:
        try:
            await asyncio.to_thread(file_path.unlink, missing_ok=True)
        except Exception:  # noqa: BLE001
            LOGGER.debug("Unable to prune timelapse frame %s", file_path, exc_info=True)

    async_dispatcher_send(hass, timelapse_dispatcher_signal(entry.entry_id))
    return CaptureResult(
        success=True,
        capture_dir=paths.directory,
        frame_path=frame_path,
        allowlist_error=False,
    )


async def async_build_timelapse_video(
    hass: HomeAssistant,
    entry: ConfigEntry,
    grow_space: Any,
    merged_config: dict[str, Any],
    *,
    framerate: int = 24,
) -> Path | None:
    """Build a timelapse video from captured frames using ffmpeg."""
    paths = resolve_timelapse_paths(
        hass.config.config_dir,
        getattr(grow_space, "name", entry.title),
        merged_config.get(CONF_TIMELAPSE_DIR),
    )
    frame_glob = str(paths.directory / f"{_FRAME_PREFIX}*{_FRAME_SUFFIX}")
    frames = await asyncio.to_thread(list_frame_files, paths.directory)
    if not frames:
        LOGGER.info("Skipping timelapse build for %s: no frames found", entry.entry_id)
        return None

    output_path = paths.directory / (
        f"timelapse-{dt_util.utcnow().strftime('%Y%m%d-%H%M%S')}.mp4"
    )

    ffmpeg_bin: str | None = None
    try:
        from homeassistant.components.ffmpeg import get_ffmpeg_manager

        ffmpeg_bin = get_ffmpeg_manager(hass).binary
    except Exception:  # noqa: BLE001
        ffmpeg_bin = None

    manual_cmd = build_ffmpeg_command(
        ffmpeg_bin or "ffmpeg",
        frame_glob,
        framerate,
        str(output_path),
    )
    if not ffmpeg_bin:
        LOGGER.warning(
            "FFmpeg is unavailable for timelapse build on %s. Run manually: %s",
            entry.entry_id,
            shlex.join(manual_cmd),
        )
        return None

    process = await asyncio.create_subprocess_exec(
        *manual_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        LOGGER.error(
            "FFmpeg timelapse build failed for %s (exit=%s): %s",
            entry.entry_id,
            process.returncode,
            (stderr or stdout).decode(errors="ignore").strip(),
        )
        return None

    async_dispatcher_send(hass, timelapse_dispatcher_signal(entry.entry_id))
    LOGGER.info("Built timelapse for %s at %s", entry.entry_id, output_path)
    return output_path
