from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import math

import numpy as np

from dearvr_adapter import DearVRRenderer, interpolate_keyframe_value, interpolate_pose, wrap_azimuth
from tukana_preview_renderer import read_segment, write_pcm16, metrics


def file_hash(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def apply_scene_gain(audio: np.ndarray, source: dict, start_seconds: float,
                     rate: int, block_size: int) -> np.ndarray:
    output = np.empty_like(audio, dtype=np.float32)
    for start in range(0, audio.shape[1], block_size):
        end = min(start + block_size, audio.shape[1])
        time = start_seconds + start / rate
        keyframe_gain = interpolate_keyframe_value(source["keyframes"], time, "gain_db", 0.0)
        gain_db = float(source.get("gain_db", 0.0)) + keyframe_gain
        output[:, start:end] = audio[:, start:end] * (10 ** (gain_db / 20))
    return output


def active_roles(musical_map: dict, start: float, end: float) -> list[str]:
    roles = []
    for role, events in musical_map["stem_events"].items():
        if any(region["start_seconds"] < end and region["end_seconds"] > start
               for region in events["active_regions"]):
            roles.append(role)
    return sorted(roles)


def render_multistem_preview(scene_path: str | Path, musical_map_path: str | Path,
                             output_root: str | Path, start_seconds: float = 127.0,
                             duration_seconds: float = 45.0,
                             block_size: int = 256) -> dict:
    scene_path = Path(scene_path)
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    musical_map = json.loads(Path(musical_map_path).read_text(encoding="utf-8"))
    output_root = Path(output_root)
    stem_root = output_root / "spatial_stems" / "preview_127_172"
    render_root = output_root / "renders"
    stem_root.mkdir(parents=True, exist_ok=True); render_root.mkdir(parents=True, exist_ok=True)

    frame_count = round(duration_seconds * 48000)
    spatial_mix = np.zeros((2, frame_count), dtype=np.float64)
    dry_mix = np.zeros((2, frame_count), dtype=np.float64)
    source_reports = {}
    input_stats = {}

    for source in scene["sources"]:
        role = source["source_id"]
        input_path = Path(source["input_file"])
        input_stats[role] = {"size": input_path.stat().st_size, "mtime_ns": input_path.stat().st_mtime_ns}
        dry, rate = read_segment(input_path, start_seconds, duration_seconds)
        if rate != 48000 or dry.shape[1] != frame_count:
            raise ValueError(f"{role}: unexpected rate or duration")
        dry_gained = apply_scene_gain(dry, source, start_seconds, rate, block_size)
        rendered = DearVRRenderer(rate, block_size).render(
            dry, source, timeline_offset_seconds=start_seconds
        )
        spatial_path = stem_root / f"{role}_spatial.wav"
        write_pcm16(spatial_path, rendered, rate)
        spatial_mix += rendered.astype(np.float64)
        dry_mix += dry_gained.astype(np.float64)
        source_reports[role] = {
            "input": str(input_path), "output": str(spatial_path),
            "trajectory": source["trajectory"], "metrics": metrics(rendered, block_size),
            "output_sha256": file_hash(spatial_path),
        }

    spatial_peak = float(np.max(np.abs(spatial_mix)))
    spatial_rms = float(np.sqrt(np.mean(spatial_mix ** 2)))
    dry_peak = float(np.max(np.abs(dry_mix)))
    dry_rms = float(np.sqrt(np.mean(dry_mix ** 2)))
    spatial_gain = min(1.0, 0.90 / max(spatial_peak, 1e-12))
    dry_gain = spatial_rms * spatial_gain / max(dry_rms, 1e-12)
    if dry_peak * dry_gain > 0.90:
        common = 0.90 / (dry_peak * dry_gain)
        spatial_gain *= common; dry_gain *= common
    spatial_mix = (spatial_mix * spatial_gain).astype(np.float32)
    dry_mix = (dry_mix * dry_gain).astype(np.float32)

    spatial_output = render_root / "tukana_multistem_binaural_preview_127_172.wav"
    dry_output = render_root / "tukana_multistem_dry_comparison_127_172.wav"
    write_pcm16(spatial_output, spatial_mix, 48000)
    write_pcm16(dry_output, dry_mix, 48000)
    after_stats = {source["source_id"]: {
        "size": Path(source["input_file"]).stat().st_size,
        "mtime_ns": Path(source["input_file"]).stat().st_mtime_ns,
    } for source in scene["sources"]}

    percussion = next(source for source in scene["sources"] if source["source_id"] == "percussion")
    times = np.arange(start_seconds, start_seconds + duration_seconds, block_size / 48000)
    unwrapped = np.asarray([interpolate_pose(percussion["keyframes"], time)[0] for time in times])
    wrapped = np.asarray([wrap_azimuth(value) for value in unwrapped])
    circular = (np.diff(wrapped) + 180) % 360 - 180
    spatial_metrics = metrics(spatial_mix, block_size)
    dry_metrics = metrics(dry_mix, block_size)
    loudness_difference = 20 * math.log10(max(spatial_metrics["rms"], 1e-12) /
                                           max(dry_metrics["rms"], 1e-12))
    return {
        "test_id": "T014", "scene": str(scene_path), "scene_sha256": file_hash(scene_path),
        "interval": {"start_seconds": start_seconds, "duration_seconds": duration_seconds,
                     "end_seconds": start_seconds + duration_seconds, "frames": frame_count},
        "active_roles_from_map": active_roles(musical_map, start_seconds, start_seconds + duration_seconds),
        "processing": {"sample_rate": 48000, "sample_type": "float32", "block_size": block_size,
                       "isolated_plugin_instance_per_source": True,
                       "distance_m": 3.0, "dynamic_distance": False},
        "angular_continuity": {"unwrapped_start": float(unwrapped[0]), "unwrapped_end": float(unwrapped[-1]),
                               "wrapped_crossings": int(np.count_nonzero(np.abs(np.diff(wrapped)) > 180)),
                               "max_circular_step_deg": float(np.max(np.abs(circular))),
                               "monotonic": bool(np.all(np.diff(unwrapped) >= 0))},
        "source_reports": source_reports,
        "mixes": {
            "binaural": {"path": str(spatial_output), "metrics": spatial_metrics, "gain": spatial_gain},
            "dry_comparison": {"path": str(dry_output), "metrics": dry_metrics, "gain": dry_gain},
            "rms_difference_db": loudness_difference,
        },
        "originals_unchanged": input_stats == after_stats,
    }
