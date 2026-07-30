"""Tests for timelapse helpers and execution paths."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.tendrilgrow.const import (
    CONF_TIMELAPSE_DIR,
    CONF_TIMELAPSE_RETENTION_FRAMES,
    SENSOR_ROLE_CAMERA,
)
from custom_components.tendrilgrow.timelapse import (
    async_build_timelapse_video,
    async_capture_frame,
    build_ffmpeg_command,
    build_frame_filename,
    is_probable_allowlist_error,
    parse_frame_timestamp,
    resolve_timelapse_paths,
    select_frames_to_prune,
)


def test_resolve_timelapse_paths_default_and_local_url(tmp_path: Path) -> None:
    paths = resolve_timelapse_paths(str(tmp_path), "4x4 Flower Tent", None)
    assert paths.directory == (
        tmp_path / "www" / "tendrilgrow" / "4x4_flower_tent" / "timelapse"
    )
    assert paths.local_url_base == "/local/tendrilgrow/4x4_flower_tent/timelapse"


def test_resolve_timelapse_paths_override_absolute_non_www(tmp_path: Path) -> None:
    override = tmp_path / "captures"
    paths = resolve_timelapse_paths(str(tmp_path), "Tent A", str(override))
    assert paths.directory == override
    assert paths.local_url_base is None


def test_frame_filename_and_timestamp_roundtrip() -> None:
    now = datetime(2026, 7, 30, 10, 20, 30, tzinfo=UTC)
    filename = build_frame_filename(now)
    assert filename == "frame-20260730-102030.jpg"
    parsed = parse_frame_timestamp(Path(filename))
    assert parsed == now


def test_select_frames_to_prune_keeps_newest() -> None:
    frames = [Path(f"frame-20260730-1020{n:02d}.jpg") for n in range(6)]
    prune = select_frames_to_prune(frames, retention_cap=3)
    assert [path.name for path in prune] == [
        "frame-20260730-102000.jpg",
        "frame-20260730-102001.jpg",
        "frame-20260730-102002.jpg",
    ]


def test_build_ffmpeg_command() -> None:
    cmd = build_ffmpeg_command(
        "ffmpeg",
        "/tmp/frames/frame-*.jpg",
        24,
        "/tmp/frames/timelapse.mp4",
    )
    assert cmd[:6] == ["ffmpeg", "-y", "-framerate", "24", "-pattern_type", "glob"]
    assert cmd[-1] == "/tmp/frames/timelapse.mp4"


@pytest.mark.asyncio
async def test_async_capture_frame_success_and_prune(tmp_path: Path) -> None:
    capture_dir = tmp_path / "captures"

    async def _snapshot(_domain, _service, data, blocking):
        _ = blocking
        Path(data["filename"]).write_bytes(b"jpg")

    hass = SimpleNamespace(
        config=SimpleNamespace(config_dir=str(tmp_path)),
        data={},
        verify_event_loop_thread=Mock(),
        services=SimpleNamespace(async_call=AsyncMock(side_effect=_snapshot)),
    )
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A")
    grow_space = SimpleNamespace(
        name="Tent A",
        sensor_mappings={SENSOR_ROLE_CAMERA: "camera.tent_a"},
    )
    merged = {
        CONF_TIMELAPSE_DIR: str(capture_dir),
        CONF_TIMELAPSE_RETENTION_FRAMES: 2,
    }

    # Create two old frames so capture + prune keeps only the newest two.
    capture_dir.mkdir(parents=True, exist_ok=True)
    (capture_dir / "frame-20260730-100000.jpg").write_bytes(b"old")
    (capture_dir / "frame-20260730-100100.jpg").write_bytes(b"old")

    result = await async_capture_frame(hass, entry, grow_space, merged)

    assert result.success is True
    assert result.allowlist_error is False
    frames = sorted(path.name for path in capture_dir.glob("frame-*.jpg"))
    assert len(frames) == 2
    assert "frame-20260730-100000.jpg" not in frames


@pytest.mark.asyncio
async def test_async_capture_frame_allowlist_error(tmp_path: Path) -> None:
    async def _snapshot(_domain, _service, _data, blocking):
        _ = blocking
        raise RuntimeError("Path is not in allowlist_external_dirs")

    hass = SimpleNamespace(
        config=SimpleNamespace(config_dir=str(tmp_path)),
        data={},
        verify_event_loop_thread=Mock(),
        services=SimpleNamespace(async_call=AsyncMock(side_effect=_snapshot)),
    )
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A")
    grow_space = SimpleNamespace(
        name="Tent A",
        sensor_mappings={SENSOR_ROLE_CAMERA: "camera.tent_a"},
    )

    result = await async_capture_frame(hass, entry, grow_space, {})

    assert result.success is False
    assert result.allowlist_error is True


@pytest.mark.asyncio
async def test_async_build_timelapse_video_graceful_when_ffmpeg_missing(
    tmp_path: Path,
) -> None:
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir(parents=True, exist_ok=True)
    (capture_dir / "frame-20260730-100000.jpg").write_bytes(b"jpg")

    hass = SimpleNamespace(
        config=SimpleNamespace(config_dir=str(tmp_path)),
        data={},
        verify_event_loop_thread=Mock(),
    )
    entry = SimpleNamespace(entry_id="entry-1", title="Tent A")
    grow_space = SimpleNamespace(name="Tent A", sensor_mappings={})

    output = await async_build_timelapse_video(
        hass,
        entry,
        grow_space,
        {CONF_TIMELAPSE_DIR: str(capture_dir)},
    )

    assert output is None


def test_allowlist_error_detection() -> None:
    assert is_probable_allowlist_error("not allow-listed") is True
    assert is_probable_allowlist_error("network timeout") is False
