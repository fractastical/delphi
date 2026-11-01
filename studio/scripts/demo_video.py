#!/usr/bin/env python3
"""Build provenance-carrying, captioned Frontier demo videos from a frozen story.

This renderer uses only pinned local screenshots and saved simulation clips. Voice
synthesis is a separate, explicit MiniMax Speech 2.8 call; credentials are read
from MINIMAX_API_KEY or ~/.env and are never logged or stored in receipts.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from typing import Any

from PIL import Image, ImageDraw, ImageFont
import websockets


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORY = Path("/data/worktrees/delphi-frontier/codex-demo/artifacts/demo-video/storyboard.json")
DEFAULT_OUTPUT = ROOT / "artifacts/demo-video"
DEFAULT_AUDIO = Path("/data/artifacts/delphi-evolve-rethink/demo-video/voice")
DEFAULT_MEDIA_MAP = ROOT / "artifacts/demo-video/media-map.json"
DEFAULT_RENDER_WORK = Path("/data/artifacts/delphi-evolve-rethink/demo-video/render-work")
TTS_URL = "wss://api.minimax.io/ws/v1/t2a_v2"
TTS_MODEL = "speech-2.8-turbo"
VOICE_ID = "English_expressive_narrator"
MAX_AUDIO_SEGMENT_BYTES = 8_000_000
MAX_VIDEO_BYTES = 64_000_000


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def stable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def audio_file(receipt: dict) -> Path:
    path = Path(receipt["audio_path"])
    return path if path.is_absolute() else ROOT / path


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as stream:
        temp = Path(stream.name)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def load_story(path: Path) -> dict:
    story = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(story, dict) or story.get("schema") != "frontier.demo-video.storyboard/1":
        raise ValueError("unsupported frozen storyboard schema")
    if story.get("voice_provider") != "MiniMax":
        raise ValueError("storyboard must request MiniMax voice")
    cuts = story.get("cuts")
    if not isinstance(cuts, list) or not cuts:
        raise ValueError("storyboard needs at least one cut")
    for cut in cuts:
        if not isinstance(cut, dict) or cut.get("id") not in {"frontier-60s", "frontier-90s", "frontier-120s"}:
            raise ValueError("storyboard cut id must be frontier-60s, frontier-90s, or frontier-120s")
        scenes = cut.get("scenes")
        if not isinstance(scenes, list) or not scenes:
            raise ValueError(f"{cut['id']} has no scenes")
        cursor = 0.0
        for scene in scenes:
            if not isinstance(scene, dict) or not isinstance(scene.get("narration"), str) or not scene["narration"].strip():
                raise ValueError(f"{cut['id']} scene must have narration text")
            start_s = scene.get("start_s")
            duration_s = scene.get("duration_s")
            if (isinstance(start_s, bool) or not isinstance(start_s, (int, float))
                    or not math.isfinite(start_s) or isinstance(duration_s, bool)
                    or not isinstance(duration_s, (int, float)) or not math.isfinite(duration_s)
                    or duration_s <= 0):
                raise ValueError(f"{cut['id']} scene has invalid timing")
            if abs(float(start_s) - cursor) > 1e-6:
                raise ValueError(f"{cut['id']} scene timings must be contiguous")
            if not isinstance(scene.get("id"), str) or not isinstance(scene.get("headline"), str):
                raise ValueError(f"{cut['id']} scene must have an id and headline")
            cursor += float(duration_s)
        if abs(cursor - float(cut.get("duration_s", 0))) > 1e-6:
            raise ValueError(f"{cut['id']} scene durations do not equal requested duration")
    return story


def load_api_key() -> str:
    """Load only MiniMax slot 1 from the normal environment or mode-0600 ~/.env."""
    value = os.environ.get("MINIMAX_API_KEY", "").strip()
    if value:
        return value
    env_file = Path.home() / ".env"
    if env_file.is_file():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            name, separator, candidate = line.partition("=")
            if separator and name.strip() == "MINIMAX_API_KEY":
                value = candidate.strip().strip('"').strip("'")
                if value:
                    return value
    raise RuntimeError("MiniMax API key unavailable in process environment or ~/.env")


def _base_ok(message: dict) -> bool:
    response = message.get("base_resp")
    return isinstance(response, dict) and response.get("status_code") == 0


async def synthesize_segment(text: str, api_key: str, output: Path, *, voice_id: str, speed: float) -> dict:
    """Call one non-retried MiniMax TTS task and write its returned MP3 bytes."""
    headers = {"Authorization": f"Bearer {api_key}"}
    chunks: list[bytes] = []
    audio_bytes = 0
    trace_id = None
    usage = None
    # Default TLS certificate verification remains enabled. No player/subprocess
    # runs inside this credentialed network call.
    async with websockets.connect(TTS_URL, extra_headers=headers, open_timeout=20, close_timeout=5,
                                   max_size=2_000_000, ping_interval=20, ping_timeout=20) as socket:
        connected = json.loads(await asyncio.wait_for(socket.recv(), timeout=30))
        if connected.get("event") != "connected_success" or not _base_ok(connected):
            raise RuntimeError("MiniMax speech connection was not accepted")
        trace_id = connected.get("trace_id")
        await socket.send(json.dumps({
            "event": "task_start",
            "model": TTS_MODEL,
            "voice_setting": {"voice_id": voice_id, "speed": speed, "vol": 1.0, "pitch": 0,
                              "english_normalization": True},
            "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 1},
        }))
        started = json.loads(await asyncio.wait_for(socket.recv(), timeout=30))
        if started.get("event") != "task_started" or not _base_ok(started):
            raise RuntimeError("MiniMax did not accept the speech task")
        trace_id = started.get("trace_id") or trace_id
        await socket.send(json.dumps({"event": "task_continue", "text": text}))
        while True:
            message = json.loads(await asyncio.wait_for(socket.recv(), timeout=60))
            if message.get("event") == "task_failed" or not _base_ok(message):
                raise RuntimeError("MiniMax speech task failed; no automatic retry was attempted")
            hex_audio = message.get("data", {}).get("audio")
            if hex_audio:
                chunk = bytes.fromhex(hex_audio)
                audio_bytes += len(chunk)
                if audio_bytes > MAX_AUDIO_SEGMENT_BYTES:
                    raise RuntimeError("MiniMax audio response exceeded the per-scene size bound")
                chunks.append(chunk)
            if isinstance(message.get("extra_info"), dict):
                usage = message["extra_info"]
            if message.get("is_final"):
                break
        await socket.send(json.dumps({"event": "task_finish"}))
    audio = b"".join(chunks)
    if not audio:
        raise RuntimeError("MiniMax returned no audio data")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix=f".{output.name}.", delete=False) as stream:
        temp = Path(stream.name)
        stream.write(audio)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, output)
    safe_usage = {key: usage[key] for key in (
        "audio_length", "audio_sample_rate", "audio_size", "bitrate", "word_count", "usage_characters",
        "audio_format", "audio_channel") if usage and key in usage}
    return {"provider": "MiniMax", "endpoint": TTS_URL, "model": TTS_MODEL, "voice_id": voice_id,
            "voice_settings": {"speed": speed, "volume": 1.0, "pitch": 0, "english_normalization": True},
            "trace_id": trace_id, "text_sha256": sha256_bytes(text.encode("utf-8")),
            "audio_sha256": sha256_file(output), "audio_bytes": output.stat().st_size,
            "audio_path": str(output), "usage": safe_usage}


def tts_cache_key(text: str, voice_id: str, speed: float) -> str:
    identity = {"text_sha256": sha256_bytes(text.encode("utf-8")), "model": TTS_MODEL,
                "voice_id": voice_id, "speed": speed, "sample_rate": 32000,
                "bitrate": 128000, "format": "mp3", "channel": 1}
    return sha256_bytes(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode())


async def synthesize_cut(cut: dict, api_key: str, audio_root: Path, *, voice_id: str, speed: float) -> dict:
    entries = []
    provider_requests = 0
    for scene in cut["scenes"]:
        text_sha = sha256_bytes(scene["narration"].encode("utf-8"))
        cache_key = tts_cache_key(scene["narration"], voice_id, speed)
        output = audio_root / cut["id"] / f"{scene['id']}-{cache_key[:12]}.mp3"
        receipt_path = output.with_suffix(".receipt.json")
        legacy_outputs = [
            audio_root / cut["id"] / f"{scene['id']}.mp3",
            audio_root / cut["id"] / f"{scene['id']}-{text_sha[:12]}.mp3",
        ]
        if output.exists() or receipt_path.exists():
            if not output.is_file() or not receipt_path.is_file():
                raise FileExistsError(f"incomplete prior narration output for {cut['id']}/{scene['id']}; inspect before retry")
            existing = json.loads(receipt_path.read_text(encoding="utf-8"))
            if (existing.get("text_sha256") != text_sha or existing.get("audio_sha256") != sha256_file(output)
                    or existing.get("voice_id") != voice_id or existing.get("voice_settings", {}).get("speed") != speed):
                raise FileExistsError(f"existing narration differs from frozen input for {cut['id']}/{scene['id']}")
            existing = dict(existing)
            existing["scene_budget_s_current"] = scene["duration_s"]
            existing["reused_existing_audio"] = True
            entries.append(existing)
            continue
        reused = False
        for legacy_output in legacy_outputs:
            legacy_receipt_path = legacy_output.with_suffix(".receipt.json")
            if not legacy_output.is_file() or not legacy_receipt_path.is_file():
                continue
            legacy = json.loads(legacy_receipt_path.read_text(encoding="utf-8"))
            if (legacy.get("text_sha256") == text_sha and legacy.get("audio_sha256") == sha256_file(legacy_output)
                    and legacy.get("voice_id") == voice_id
                    and legacy.get("voice_settings", {}).get("speed") == speed):
                # Reuse the first pass for unchanged script segments without a
                # second paid provider request. Its original receipt is retained.
                legacy = dict(legacy)
                legacy["cache_key_sha256"] = cache_key
                legacy["scene_budget_s_current"] = scene["duration_s"]
                legacy["reused_existing_audio"] = True
                entries.append(legacy)
                reused = True
                break
        if reused:
            continue
        receipt = await synthesize_segment(scene["narration"], api_key, output, voice_id=voice_id, speed=speed)
        receipt.update({"cut_id": cut["id"], "scene_id": scene["id"], "narration": scene["narration"],
                        "word_count": len(scene["narration"].split()), "scene_budget_s": scene["duration_s"],
                        "scene_budget_s_current": scene["duration_s"], "cache_key_sha256": cache_key,
                        "reused_existing_audio": False})
        receipt["audio_path"] = stable_path(Path(receipt["audio_path"]))
        atomic_json(receipt_path, receipt)
        entries.append(receipt)
        provider_requests += 1
        print(json.dumps({"cut": cut["id"], "scene": scene["id"], "trace_id": receipt["trace_id"],
                          "usage_characters": receipt.get("usage", {}).get("usage_characters"),
                          "audio_bytes": receipt["audio_bytes"]}))
    return {"cut_id": cut["id"], "voice_model": TTS_MODEL, "voice_id": voice_id, "voice_speed": speed,
            "provider_requests": provider_requests, "segments": entries}


def run_synthesis(story_path: Path, audio_root: Path, output_root: Path, *, voice_id: str = VOICE_ID,
                  speed: float = 1.0, only_cut: str | None = None) -> dict:
    story = load_story(story_path)
    if not 0.5 <= speed <= 2.0:
        raise ValueError("MiniMax speed must be between 0.5 and 2.0")
    if not voice_id or len(voice_id) > 128:
        raise ValueError("voice id must be a nonempty string up to 128 characters")
    selected_cuts = [cut for cut in story["cuts"] if only_cut is None or cut["id"] == only_cut]
    if only_cut is not None and not selected_cuts:
        raise ValueError(f"requested cut is absent from frozen storyboard: {only_cut}")
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "tts-manifest.json"
    storyboard_sha = sha256_file(story_path)
    if manifest_path.is_file():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous.get("storyboard_sha256") != storyboard_sha:
            old_sha = str(previous.get("storyboard_sha256", "unknown"))[:12]
            backup_path = output_root / f"tts-manifest-superseded-{old_sha}.json"
            if not backup_path.exists():
                backup_path.write_bytes(manifest_path.read_bytes())
    api_key = load_api_key()
    results = asyncio.run(_synthesize_story(selected_cuts, api_key, audio_root, voice_id=voice_id, speed=speed))
    for cut in results:
        for segment in cut["segments"]:
            segment["audio_path"] = stable_path(audio_file(segment))
    manifest = {"schema": "frontier.demo-video.tts-manifest/1", "status": "complete",
                "storyboard_sha256": storyboard_sha, "storyboard_path": stable_path(story_path),
                "provider": "MiniMax", "model": TTS_MODEL, "voice_id": voice_id, "voice_speed": speed,
                "provider_requests_this_run": sum(cut["provider_requests"] for cut in results), "cuts": results}
    atomic_json(manifest_path, manifest)
    return manifest


async def _synthesize_story(cuts: list[dict], api_key: str, audio_root: Path, *, voice_id: str,
                            speed: float) -> list[dict]:
    return [await synthesize_cut(cut, api_key, audio_root, voice_id=voice_id, speed=speed) for cut in cuts]


def prepare_audio_edit(story_path: Path, tts_path: Path, output_root: Path, *, tempo: float) -> dict:
    """Create pitch-preserved sped-up scene files and an exact retimed edit copy."""
    if not 1.0 <= tempo <= 2.0:
        raise ValueError("editorial tempo must be between 1.0 and 2.0")
    story = load_story(story_path)
    tts_manifest = json.loads(tts_path.read_text(encoding="utf-8"))
    if tts_manifest.get("storyboard_sha256") != sha256_file(story_path):
        raise ValueError("source TTS manifest does not match the exact frozen storyboard")
    processed_root = output_root / "sources" / "voice" / f"processed-tempo-{tempo:.2f}"
    edited_manifest = copy.deepcopy(tts_manifest)
    duration_rows = []
    for cut in edited_manifest["cuts"]:
        scene_rows = {row["scene_id"]: row for row in cut["segments"]}
        if set(scene_rows) != {scene["id"] for scene in next(c for c in story["cuts"] if c["id"] == cut["cut_id"])["scenes"]}:
            raise ValueError("TTS scene IDs differ from frozen storyboard")
        for scene_id, segment in scene_rows.items():
            source_path = audio_file(segment)
            if sha256_file(source_path) != segment.get("audio_sha256"):
                raise ValueError(f"source narration hash mismatch for {scene_id}")
            processed_path = processed_root / cut["cut_id"] / f"{scene_id}-atempo-{tempo:.2f}.mp3"
            if processed_path.exists():
                raise FileExistsError(f"processed audio already exists; inspect before reuse: {processed_path.name}")
            processed_path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source_path),
                            "-map", "0:a:0", "-vn", "-af", f"atempo={tempo:.8g}", "-c:a", "libmp3lame",
                            "-q:a", "2", "-ar", "32000", "-ac", "1", str(processed_path)],
                           check=True, timeout=90, capture_output=True, text=True)
            source_audio = {"path": segment["audio_path"], "sha256": segment["audio_sha256"],
                            "bytes": segment["audio_bytes"], "duration_s": round(probe_duration(source_path), 3)}
            segment.update({"original_audio": source_audio,
                            "audio_path": stable_path(processed_path),
                            "audio_sha256": sha256_file(processed_path),
                            "audio_bytes": processed_path.stat().st_size,
                            "audio_duration_s": round(probe_duration(processed_path), 6),
                            "reused_existing_audio": True})
            duration_rows.append({"cut_id": cut["cut_id"], "scene_id": scene_id,
                                  "original_duration_s": source_audio["duration_s"],
                                  "processed_duration_s": segment["audio_duration_s"]})
    edited_manifest["audio_postprocessing"] = {
        "method": "FFmpeg atempo filter; pitch preserved",
        "tempo": tempo,
        "tts_voice_speed": tts_manifest.get("voice_speed"),
        "source_tts_manifest_path": stable_path(tts_path),
        "source_tts_manifest_sha256": sha256_file(tts_path),
        "provider_requests_this_edit": 0,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    edited_tts_path = output_root / "tts-manifest-edited.json"
    atomic_json(edited_tts_path, edited_manifest)

    edit_story = copy.deepcopy(story)
    edit_story["audio_source_storyboard_sha256"] = sha256_file(story_path)
    edit_story["audio_source_storyboard_path"] = stable_path(story_path)
    for cut in edit_story["cuts"]:
        tts_cut = next(row for row in edited_manifest["cuts"] if row["cut_id"] == cut["id"])
        audio = {row["scene_id"]: probe_duration(audio_file(row)) for row in tts_cut["segments"]}
        total_audio = sum(audio[scene["id"]] for scene in cut["scenes"])
        available = float(cut["duration_s"]) - total_audio
        if available <= 0:
            raise ValueError(f"processed narration exceeds {cut['id']} cut duration")
        hold = available / len(cut["scenes"])
        cursor = 0.0
        timing_rows = []
        for scene in cut["scenes"]:
            original_budget = scene["duration_s"]
            scene_duration = audio[scene["id"]] + hold
            scene["start_s"] = cursor
            scene["duration_s"] = scene_duration
            timing_rows.append({"scene_id": scene["id"], "source_scene_budget_s": original_budget,
                                "spoken_audio_s": round(audio[scene["id"]], 6),
                                "hold_after_audio_s": round(hold, 6),
                                "edited_scene_duration_s": round(scene_duration, 6)})
            cursor += scene_duration
        cut["scenes"][-1]["duration_s"] += float(cut["duration_s"]) - cursor
        cut["editing"] = {"duration_s": cut["duration_s"], "spoken_audio_s": round(total_audio, 6),
                          "distributed_scene_holds_s": round(available, 6), "scenes": timing_rows}
    edit_story["revision"] = 3
    edit_story["editing"] = {
        "kind": "editorial timing revision; spoken narration unchanged",
        "source_revision": story.get("revision"),
        "audio_tempo": tempo,
        "pitch_preserved": True,
        "tts_source_voice_speed": tts_manifest.get("voice_speed"),
        "audio_duration_rows": duration_rows,
        "cuts": [row.get("editing") for row in edit_story["cuts"]],
    }
    edit_story_path = output_root / "edit-storyboard.json"
    atomic_json(edit_story_path, edit_story)
    return {"audio_manifest_path": stable_path(edited_tts_path), "edit_storyboard_path": stable_path(edit_story_path),
            "audio_postprocessing": edited_manifest["audio_postprocessing"],
            "cuts": edit_story["editing"]["cuts"]}


def probe_duration(path: Path) -> float:
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                            check=True, capture_output=True, text=True, timeout=30)
    return float(result.stdout.strip())


def _format_srt(seconds: float, separator: str = ",") -> str:
    millis = max(0, round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    seconds_int, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds_int:02d}{separator}{millis:03d}"


def generate_subtitles(cut: dict, tts_cut: dict, output: Path) -> dict:
    receipts = {entry["scene_id"]: entry for entry in tts_cut["segments"]}
    cues = []
    overruns = []
    for scene in cut["scenes"]:
        receipt = receipts[scene["id"]]
        audio_duration = probe_duration(audio_file(receipt))
        budget = scene["duration_s"]
        if audio_duration > budget + 0.05:
            overruns.append({"scene_id": scene["id"], "scene_budget_s": budget, "voice_duration_s": round(audio_duration, 3),
                             "overrun_s": round(audio_duration - budget, 3), "word_count": receipt["word_count"]})
        # Captions preserve exact narration and are split to <=2 readable lines.
        # Timing is estimated by phrase word counts across provider-measured scene
        # audio; MiniMax does not provide word-forced alignment for these calls.
        lines = textwrap.wrap(scene["narration"], width=42, break_long_words=False, break_on_hyphens=False)
        groups = [lines[index:index + 2] for index in range(0, len(lines), 2)]
        group_words = [len(" ".join(group).split()) for group in groups]
        word_total = max(1, sum(group_words))
        elapsed_words = 0
        for group, words in zip(groups, group_words):
            start = float(scene["start_s"]) + audio_duration * elapsed_words / word_total
            elapsed_words += words
            end = float(scene["start_s"]) + audio_duration * elapsed_words / word_total
            cues.append((start, end, "\n".join(group)))
    if overruns:
        atomic_json(output.with_suffix(".overruns.json"), {"schema": "frontier.demo-video.overruns/1", "overruns": overruns})
        raise RuntimeError(f"voice overrun in {len(overruns)} scene(s); see {output.with_suffix('.overruns.json')}")
    output.parent.mkdir(parents=True, exist_ok=True)
    srt_body = "\n\n".join(f"{index}\n{_format_srt(start)} --> {_format_srt(end)}\n{text}" for index, (start, end, text) in enumerate(cues, 1)) + "\n"
    output.write_text(srt_body, encoding="utf-8")
    vtt_path = output.with_suffix(".vtt")
    vtt_body = "WEBVTT\n\n" + "\n\n".join(f"{index}\n{_format_srt(start, '.')} --> {_format_srt(end, '.')}\n{text}" for index, (start, end, text) in enumerate(cues, 1)) + "\n"
    vtt_path.write_text(vtt_body, encoding="utf-8")
    return {"subtitle_path": str(output), "vtt_path": str(vtt_path), "cues": len(cues), "overruns": [],
            "alignment": "estimated by phrase word counts within provider-measured scene audio; no word-forced timestamps are supplied"}


def validate_media_map(story: dict, media_map_path: Path) -> tuple[dict, list[dict]]:
    media_map = json.loads(media_map_path.read_text(encoding="utf-8"))
    if media_map.get("schema") != "frontier.demo-video.media-map/1":
        raise ValueError("unsupported media-map schema")
    cuts = media_map.get("cuts")
    if not isinstance(cuts, dict):
        raise ValueError("media-map cuts must be an object")
    sources: dict[str, dict] = {}
    for cut in story["cuts"]:
        cut_map = cuts.get(cut["id"])
        if not isinstance(cut_map, dict):
            raise ValueError(f"media-map missing {cut['id']}")
        for scene in cut["scenes"]:
            spec = cut_map.get(scene["id"])
            if not isinstance(spec, dict) or not isinstance(spec.get("shots"), list) or not spec["shots"]:
                raise ValueError(f"media-map missing shots for {cut['id']}/{scene['id']}")
            shot_total = 0.0
            for shot in spec["shots"]:
                layout = shot.get("layout")
                expected = {"single": 1, "grid-2": 2, "grid-4": 4}.get(layout)
                shot_sources = shot.get("sources")
                if expected is None or not isinstance(shot_sources, list) or len(shot_sources) != expected:
                    raise ValueError(f"invalid layout/source count in {cut['id']}/{scene['id']}")
                duration = shot.get("duration_s")
                if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not 0 < duration <= scene["duration_s"]:
                    raise ValueError(f"invalid shot duration in {cut['id']}/{scene['id']}")
                if len(shot.get("badge", "")) > 180:
                    raise ValueError("shot badge is too long")
                shot_total += float(duration)
                for source in shot_sources:
                    if not isinstance(source, dict) or not {"path", "sha256", "kind", "label", "provenance"}.issubset(source) or set(source) - {"path", "sha256", "kind", "label", "provenance", "crop_y"}:
                        raise ValueError("source must declare path, sha256, kind, label and provenance")
                    if "crop_y" in source and (source["kind"] != "image" or isinstance(source["crop_y"], bool) or not isinstance(source["crop_y"], int) or not 0 <= source["crop_y"] <= 500):
                        raise ValueError("crop_y is supported only for images and must be an integer from 0 to 500")
                    path = Path(source["path"])
                    if not path.is_file() or path.is_symlink():
                        raise ValueError(f"missing or symlinked media source {path.name}")
                    if source["kind"] not in {"image", "video"} or len(source["label"]) > 120 or len(source["provenance"]) > 1000:
                        raise ValueError("invalid or overlong source metadata")
                    actual = sha256_file(path)
                    if actual != source["sha256"]:
                        raise ValueError(f"source hash mismatch for {path.name}")
                    sources[str(path.resolve())] = {"path": str(path.resolve()), "sha256": actual,
                                                    "bytes": path.stat().st_size, "kind": source["kind"],
                                                    "label": source["label"], "provenance": source["provenance"]}
            if abs(shot_total - scene["duration_s"]) > 0.001:
                raise ValueError(f"shot durations do not equal {cut['id']}/{scene['id']} budget")
            spec["headline"] = scene["headline"]
            if len(spec.get("badge", "")) > 180:
                raise ValueError("scene badge is too long")
    return media_map, list(sources.values())


def _source_reference(source_path: str, fallback_commit: str) -> dict:
    path = Path(source_path).resolve()
    try:
        repo = Path(subprocess.run(["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
                                   check=True, capture_output=True, text=True, timeout=10).stdout.strip())
        relative = path.relative_to(repo).as_posix()
        commit_result = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%H", "--", relative],
                                       check=True, capture_output=True, text=True, timeout=10)
        commit = commit_result.stdout.strip() or fallback_commit
        remote = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"],
                                check=True, capture_output=True, text=True, timeout=10).stdout.strip()
        if remote.startswith("https://github.com/"):
            url = f"{remote.rstrip('.git')}/blob/{commit}/{relative}"
        else:
            url = None
        return {"path": relative, "commit": commit, "url": url}
    except (subprocess.CalledProcessError, OSError, ValueError, subprocess.TimeoutExpired):
        return {"path": path.name, "commit": fallback_commit, "url": None}


def _font_path(bold: bool = False) -> Path:
    preferred = Path("/home/ubuntu/.local/share/fonts/Inter-SemiBold.ttf" if bold else "/home/ubuntu/.local/share/fonts/Inter-Regular.ttf")
    fallback = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    path = preferred if preferred.is_file() else fallback
    if not path.is_file():
        raise RuntimeError("no supported sans-serif font is installed")
    return path


def _draw_overlay(scene_spec: dict, shot: dict, path: Path) -> dict:
    width, height = 1920, 1080
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    title_font = ImageFont.truetype(str(_font_path(True)), 56)
    kicker_font = ImageFont.truetype(str(_font_path(True)), 24)
    badge_font = ImageFont.truetype(str(_font_path(True)), 27)
    small_font = ImageFont.truetype(str(_font_path(True)), 30)

    title_lines = textwrap.wrap(scene_spec["headline"], width=64)
    title = "\n".join(title_lines[:2])
    header_bottom = 202 if len(title_lines) > 1 else 142
    badge_top = header_bottom + 10
    media_top = badge_top + 62
    box = (48, 18, 1872, header_bottom)
    draw.rounded_rectangle(box, radius=24, fill=(5, 20, 35, 226), outline=(116, 230, 190, 150), width=2)
    draw.text((76, 25), "MORPHOSWARM FRONTIER", font=kicker_font, fill=(115, 238, 194, 255))
    draw.multiline_text((76, 58), title, font=title_font, fill=(255, 255, 255, 255), spacing=1)
    badge = shot.get("badge", scene_spec.get("badge", ""))
    if badge:
        draw.rounded_rectangle((48, badge_top, 1872, media_top), radius=14, fill=(5, 20, 35, 228))
        draw.text((72, badge_top + 10), badge, font=badge_font, fill=(255, 238, 188, 255))

    # Add provenance-conscious model labels inside each montage tile. These are
    # labels only; no scientific image or trajectory pixels are invented.
    positions = {
        "single": [(72, 820)],
        "grid-2": [(72, 820), (1020, 820)],
        "grid-4": [(72, 820), (1020, 820), (72, 872), (1020, 872)],
    }[shot["layout"]]
    for source, (x, y) in zip(shot["sources"], positions):
        label = source["label"].strip()
        if not label:
            continue
        label = textwrap.shorten(label, width=82, placeholder="…")
        box_width = min(width - x - 20, max(310, int(draw.textlength(label, font=small_font)) + 32))
        draw.rounded_rectangle((x, y, x + box_width, y + 52), radius=10, fill=(5, 20, 35, 228))
        draw.text((x + 14, y + 8), label, font=small_font, fill=(236, 249, 247, 255))
    overlay.save(path)
    return {"width": width, "height": height, "headline_font_px": 56, "kicker_font_px": 24,
            "caption_font_px": 32, "safe_margin_px": 72,
            "font_files": {"regular": str(_font_path()), "semibold": str(_font_path(True))}}


def _video_input_args(source: dict) -> list[str]:
    if source["kind"] == "image":
        return ["-loop", "1", "-framerate", "30", "-i", source["path"]]
    return ["-i", source["path"]]


def render_shot(shot: dict, scene_spec: dict, output: Path, overlay_path: Path, *, extra_hold_s: float = 0.0) -> None:
    duration = float(shot["duration_s"]) + extra_hold_s
    sources = shot["sources"]
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for source in sources:
        args.extend(_video_input_args(source))
    args.extend(["-loop", "1", "-framerate", "30", "-i", str(overlay_path)])
    filters = []
    if shot["layout"] == "single":
        source = sources[0]
        if source["kind"] == "image":
            # Screenshots are cropped to the central content band: the renderer
            # replaces the original site header with its own title, while the
            # exact table/graph pixels remain at native 1080p scale.
            crop_y = source.get("crop_y", 190)
            filters.append(f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x07121f,crop=1920:580:0:{crop_y},pad=1920:1080:0:220:color=0x07121f,setsar=1,fps=30,tpad=stop_mode=clone:stop_duration={duration},trim=duration={duration},setpts=PTS-STARTPTS[vbase]")
        else:
            # Preserve all source-video pixels and their embedded axes/labels;
            # letterbox within the reserved media band below the title.
            filters.append(f"[0:v]scale=1032:580:force_original_aspect_ratio=decrease,pad=1032:580:(ow-iw)/2:(oh-ih)/2:color=0x07121f,setsar=1,fps=30,tpad=stop_mode=clone:stop_duration={duration},trim=duration={duration},setpts=PTS-STARTPTS,pad=1920:1080:444:220:color=0x07121f[vbase]")
        base = "[vbase]"
    else:
        title_lines = textwrap.wrap(scene_spec["headline"], width=64)
        media_top = (202 if len(title_lines) > 1 else 142) + 72
        tile_width, tile_height = (960, 820 - media_top) if shot["layout"] == "grid-2" else (960, (820 - media_top) // 2)
        labels = []
        for index in range(len(sources)):
            filters.append(f"[{index}:v]scale={tile_width}:{tile_height}:force_original_aspect_ratio=decrease,pad={tile_width}:{tile_height}:(ow-iw)/2:(oh-ih)/2:color=0x07121f,setsar=1,fps=30,tpad=stop_mode=clone:stop_duration={duration},trim=duration={duration},setpts=PTS-STARTPTS[v{index}]")
            labels.append(f"[v{index}]")
        if shot["layout"] == "grid-2":
            filters.append(f"{''.join(labels)}xstack=inputs=2:layout=0_{media_top}|960_{media_top}:fill=0x07121f,pad=1920:1080:0:0:color=0x07121f,format=yuv420p[vbase]")
        else:
            filters.append(f"{''.join(labels)}xstack=inputs=4:layout=0_{media_top}|960_{media_top}|0_{media_top + tile_height}|960_{media_top + tile_height}:fill=0x07121f,pad=1920:1080:0:0:color=0x07121f,format=yuv420p[vbase]")
        base = "[vbase]"
    overlay_index = len(sources)
    filters.append(f"{base}[{overlay_index}:v]overlay=0:0:shortest=1,format=yuv420p[vout]")
    args.extend(["-filter_complex_threads", "1", "-threads", "2", "-filter_complex", ";".join(filters), "-map", "[vout]", "-t", f"{duration:.6f}",
                 "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-maxrate", "3500k",
                 "-bufsize", "7000k", "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart", str(output)])
    subprocess.run(args, check=True, timeout=max(90, int(duration * 20)), capture_output=True, text=True)


def render_scene(scene: dict, scene_spec: dict, cut_dir: Path, *, extra_hold_s: float = 0.0) -> Path:
    shot_files = []
    for index, shot in enumerate(scene_spec["shots"]):
        path = cut_dir / f"{scene['id']}-shot-{index:02d}.mp4"
        overlay = cut_dir / f"{scene['id']}-shot-{index:02d}-overlay.png"
        _draw_overlay(scene_spec, shot, overlay)
        is_last_shot = index == len(scene_spec["shots"]) - 1
        render_shot(shot, scene_spec, path, overlay,
                    extra_hold_s=(extra_hold_s if is_last_shot else 0.0))
        shot_files.append(path)
    scene_path = cut_dir / f"{scene['id']}.mp4"
    if len(shot_files) == 1:
        return shot_files[0]
    list_path = cut_dir / f"{scene['id']}-shots.txt"
    list_path.write_text("".join(f"file '{path.as_posix()}'\n" for path in shot_files), encoding="utf-8")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-filter_complex_threads", "1", "-threads", "2", "-f", "concat", "-safe", "0", "-i", str(list_path),
                    "-c", "copy", "-movflags", "+faststart", str(scene_path)],
                   check=True, timeout=120, capture_output=True, text=True)
    return scene_path


def _escape_filter_path(path: Path) -> str:
    return path.resolve().as_posix().replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _build_cut_audio(cut: dict, tts_cut: dict, output: Path) -> tuple[float, list[dict]]:
    entries = {row["scene_id"]: row for row in tts_cut["segments"]}
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for scene in cut["scenes"]:
        args.extend(["-i", entries[scene["id"]]["audio_path"]])
    filters = []
    for index, scene in enumerate(cut["scenes"]):
        duration = float(scene["duration_s"])
        voice = audio_file(entries[scene["id"]])
        actual = probe_duration(voice)
        if actual > duration + 0.05:
            raise RuntimeError(f"{cut['id']}/{scene['id']} narration overruns by {actual - duration:.3f}s")
        filters.append(f"[{index}:a]aresample=48000,apad,atrim=duration={duration},asetpts=PTS-STARTPTS[a{index}]")
    join = "".join(f"[a{index}]" for index in range(len(cut["scenes"])))
    filters.append(f"{join}concat=n={len(cut['scenes'])}:v=0:a=1,atrim=duration={cut['duration_s']},asetpts=PTS-STARTPTS[aout]")
    args.extend(["-filter_complex_threads", "1", "-threads", "2", "-filter_complex", ";".join(filters), "-map", "[aout]", "-t", str(cut["duration_s"]),
                 "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(output)])
    subprocess.run(args, check=True, timeout=180, capture_output=True, text=True)
    durations = [{"scene_id": scene["id"], "voice_duration_s": round(probe_duration(audio_file(entries[scene["id"]])), 3),
                 "scene_budget_s": scene["duration_s"]} for scene in cut["scenes"]]
    return probe_duration(output), durations


def render_cut(cut: dict, cut_map: dict, tts_cut: dict, output_root: Path, work_root: Path,
               storyboard_path: Path, media_map_path: Path) -> dict:
    output_root.mkdir(parents=True, exist_ok=True)
    cut_dir = work_root / cut["id"]
    cut_dir.mkdir(parents=True, exist_ok=True)
    srt_path = output_root / f"{cut['id']}.srt"
    txt_path = output_root / f"{cut['id']}.txt"
    subtitle = generate_subtitles(cut, tts_cut, srt_path)
    txt_path.write_text("\n\n".join(scene["narration"] for scene in cut["scenes"]) + "\n", encoding="utf-8")

    xfade_s = 0.3
    scene_paths = []
    for index, scene in enumerate(cut["scenes"]):
        scene_spec = cut_map[scene["id"]]
        extra = xfade_s if index > 0 else 0.0
        scene_paths.append(render_scene(scene, scene_spec, cut_dir, extra_hold_s=extra))

    filter_parts = []
    previous = "[0:v]"
    cumulative = float(cut["scenes"][0]["duration_s"])
    for index in range(1, len(scene_paths)):
        next_label = f"[x{index}]"
        offset = cumulative - xfade_s
        filter_parts.append(f"{previous}[{index}:v]xfade=transition=fade:duration={xfade_s}:offset={offset:.6f}{next_label}")
        previous = next_label
        cumulative += float(cut["scenes"][index]["duration_s"])
    style = "PlayResX=1920,PlayResY=1080,FontName=Inter,FontSize=32,Outline=2,Shadow=1,BorderStyle=3,BackColour=&H900B1220,MarginV=68,Alignment=2"
    subtitle_expr = f"subtitles=filename='{_escape_filter_path(srt_path)}':original_size=1920x1080:force_style='{style}'"
    filter_parts.append(f"{previous}{subtitle_expr},format=yuv420p[vout]")
    graph = ";".join(filter_parts)
    voice_wav = work_root / f"{cut['id']}-voice.wav"
    audio_track_duration, audio_timing = _build_cut_audio(cut, tts_cut, voice_wav)
    spoken_duration = sum(row["voice_duration_s"] for row in audio_timing)
    final_path = output_root / f"{cut['id']}.mp4"
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-filter_complex_threads", "1", "-threads", "2"]
    for path in scene_paths:
        args.extend(["-i", str(path)])
    args.extend(["-i", str(voice_wav), "-filter_complex", graph, "-map", "[vout]", "-map", f"{len(scene_paths)}:a",
                 "-t", str(cut["duration_s"]), "-c:v", "libx264", "-preset", "medium", "-crf", "21",
                 "-maxrate", "3500k", "-bufsize", "7000k", "-pix_fmt", "yuv420p", "-r", "30",
                 "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(final_path)])
    subprocess.run(args, check=True, timeout=max(300, cut["duration_s"] * 30), capture_output=True, text=True)
    duration = probe_duration(final_path)
    if abs(duration - cut["duration_s"]) > 0.1:
        raise RuntimeError(f"{cut['id']} rendered to {duration:.3f}s, outside the 0.1s duration tolerance")
    size = final_path.stat().st_size
    if size > MAX_VIDEO_BYTES:
        raise RuntimeError(f"{cut['id']} exceeds the 64MB release limit")
    poster = output_root / f"{cut['id']}-poster.jpg"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "0.2", "-i", str(final_path),
                    "-frames:v", "1", "-update", "1", "-threads", "2", "-q:v", "2", str(poster)],
                   check=True, timeout=30, capture_output=True, text=True)
    vtt_path = output_root / f"{cut['id']}.vtt"
    files = {}
    for role, path in (("video", final_path), ("poster", poster), ("captions", vtt_path),
                       ("transcript", txt_path), ("subtitles_srt", srt_path)):
        files[role] = {"path": str(path.relative_to(output_root)), "sha256": sha256_file(path), "bytes": path.stat().st_size}
    title = cut.get("title") or {60: "One-minute tour", 90: "Ninety-second tour", 120: "Two-minute tour"}.get(cut["duration_s"], "Frontier demo")
    return {"id": cut["id"], "title": title,
            "duration_s": round(duration, 3), "files": files,
            "narration_duration_s": round(spoken_duration, 3),
            "audio_track_duration_s": round(audio_track_duration, 3), "audio_timing": audio_timing,
            "subtitle_cues": subtitle["cues"], "video_size_limit_bytes": MAX_VIDEO_BYTES}


def render_storyboard(story_path: Path, media_map_path: Path, tts_path: Path,
                      output_root: Path, work_root: Path, only_cut: str | None = None) -> dict:
    story = load_story(story_path)
    media_map, source_rows = validate_media_map(story, media_map_path)
    tts_manifest = json.loads(tts_path.read_text(encoding="utf-8"))
    source_storyboard_sha = story.get("audio_source_storyboard_sha256", sha256_file(story_path))
    if tts_manifest.get("storyboard_sha256") != source_storyboard_sha:
        raise ValueError("TTS manifest does not match the exact frozen storyboard")
    cuts_tts = {cut["cut_id"]: cut for cut in tts_manifest["cuts"]}
    rendered = []
    selected_cuts = [cut for cut in story["cuts"] if only_cut is None or cut["id"] == only_cut]
    if only_cut is not None and not selected_cuts:
        raise ValueError(f"requested cut is absent from frozen storyboard: {only_cut}")
    for cut in selected_cuts:
        entries = {row["scene_id"]: row for row in cuts_tts[cut["id"]]["segments"]}
        if set(entries) != {scene["id"] for scene in cut["scenes"]}:
            raise ValueError("edited storyboard scene IDs differ from the frozen narration")
        for scene in cut["scenes"]:
            if entries[scene["id"]].get("narration") != scene["narration"]:
                raise ValueError("edited storyboard changed frozen narration text")
    for cut in selected_cuts:
        rendered.append(render_cut(cut, media_map["cuts"][cut["id"]], cuts_tts[cut["id"]],
                                   output_root, work_root, story_path, media_map_path))
    capture_manifest_path = Path(media_map["capture_manifest_path"])
    if not capture_manifest_path.is_file() or sha256_file(capture_manifest_path) != media_map["capture_manifest_sha256"]:
        raise ValueError("captured-screen manifest hash mismatch")
    renderer_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                     text=True, timeout=10, check=True).stdout.strip()
    renderer_sha256 = sha256_file(Path(__file__).resolve())
    stable_sources = []
    for row in source_rows:
        reference = _source_reference(row["path"], renderer_commit)
        stable_sources.append({**row, "path": reference["path"], "source_commit": reference["commit"],
                               "source_url": reference["url"]})
    storyboard_rel = stable_path(story_path)
    source_storyboard_path = story.get("audio_source_storyboard_path")
    manifest = {"schema": "frontier.demo-video.release/1", "status": "complete" if only_cut is None else "preview",
                "storyboard": {"path": storyboard_rel, "sha256": sha256_file(story_path), "commit": media_map["storyboard_commit"]},
                "source_storyboard": ({"path": source_storyboard_path,
                                        "sha256": source_storyboard_sha}
                                       if source_storyboard_path else None),
                "editing": story.get("editing"),
                "renderer_commit": renderer_commit,
                "media_map": {"path": str(media_map_path.relative_to(ROOT)), "sha256": sha256_file(media_map_path)},
                "tts_manifest": {"path": tts_path.resolve().relative_to(ROOT).as_posix() if tts_path.resolve().is_relative_to(ROOT) else str(tts_path.resolve()), "sha256": sha256_file(tts_path),
                                 "provider": tts_manifest["provider"], "model": tts_manifest["model"],
                                 "voice_id": tts_manifest["voice_id"],
                                 "voice_speed": tts_manifest.get("voice_speed"),
                                 "provider_requests_this_run": tts_manifest["provider_requests_this_run"],
                                 "audio_postprocessing": tts_manifest.get("audio_postprocessing")},
                "source_capture_manifest": {"path": stable_path(capture_manifest_path), "sha256": sha256_file(capture_manifest_path),
                                             "release_sha": media_map["site_release_sha"]},
                "source_files": stable_sources, "cuts": rendered,
                "renderer_sha256": renderer_sha256,
                "limits": ["Computational prototype; not a biologically realized flying fish.",
                           "Simulation playback retains source timing; short clips hold on their final saved state for display only.",
                           "No total spend claim; provider execution, runtime allocation and scientific success are separately sourced."],
                "disclaimer": "Narrated computational prototype. Each claim is bounded by the exact source/model/context labels on screen; no biological realization or validation is implied."}
    atomic_json(output_root / "manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("synthesize", "prepare-edit", "render"), help="Synthesis uses MiniMax; editing and rendering use saved local media.")
    parser.add_argument("--storyboard", type=Path, default=DEFAULT_STORY)
    parser.add_argument("--audio-root", type=Path, default=DEFAULT_AUDIO)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--media-map", type=Path, default=DEFAULT_MEDIA_MAP)
    parser.add_argument("--tts-manifest", type=Path, default=None)
    parser.add_argument("--work-root", type=Path, default=DEFAULT_RENDER_WORK)
    parser.add_argument("--cut", choices=("frontier-60s", "frontier-90s", "frontier-120s"), help="render one cut as a preview; omit for all cuts")
    parser.add_argument("--voice-id", default=VOICE_ID, help="MiniMax voice id; used only by synthesize")
    parser.add_argument("--speed", type=float, default=1.0, help="MiniMax voice speed in the provider's 0.5–2.0 range")
    parser.add_argument("--tempo", type=float, default=1.3, help="pitch-preserving editorial atempo multiplier for prepare-edit")
    args = parser.parse_args(argv)
    try:
        if args.command == "synthesize":
            result = run_synthesis(args.storyboard, args.audio_root, args.output,
                                  voice_id=args.voice_id, speed=args.speed, only_cut=args.cut)
            summary = {"ok": True, "manifest": str(args.output / "tts-manifest.json"),
                       "provider_requests_this_run": result["provider_requests_this_run"],
                       "cuts": [{"id": cut["cut_id"], "segments": len(cut["segments"])} for cut in result["cuts"]]}
        elif args.command == "prepare-edit":
            result = prepare_audio_edit(args.storyboard, args.tts_manifest or args.output / "tts-manifest.json",
                                        args.output, tempo=args.tempo)
            summary = {"ok": True, **result}
        else:
            tts_path = args.tts_manifest or args.output / "tts-manifest.json"
            result = render_storyboard(args.storyboard, args.media_map, tts_path, args.output, args.work_root, args.cut)
            summary = {"ok": True, "manifest": str(args.output / "manifest.json"),
                       "cuts": [{"id": cut["id"], "duration_s": cut["duration_s"],
                                 "bytes": cut["files"]["video"]["bytes"]} for cut in result["cuts"]]}
    except Exception as exc:  # Suppress provider exception text; it may include request metadata.
        print(json.dumps({"ok": False, "error_type": type(exc).__name__}), file=sys.stderr)
        return 1
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
