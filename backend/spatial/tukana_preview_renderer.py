from __future__ import annotations

from pathlib import Path
import json
import math
import wave

import numpy as np

from dearvr_adapter import DearVRRenderer, interpolate_pose, wrap_azimuth


def read_segment(path: str | Path, start_seconds: float,
                 duration_seconds: float) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as stream:
        if stream.getnchannels() != 2 or stream.getsampwidth() != 2:
            raise ValueError(f"preview expects stereo PCM16: {path}")
        rate = stream.getframerate()
        start = round(start_seconds * rate)
        count = round(duration_seconds * rate)
        if start + count > stream.getnframes():
            raise ValueError(f"preview interval exceeds {path}")
        stream.setpos(start)
        raw = stream.readframes(count)
    audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return audio.reshape(-1, 2).T, rate


def write_pcm16(path: str | Path, audio: np.ndarray, rate: int) -> None:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    raw = (np.clip(np.nan_to_num(audio), -0.999, 0.999).T.reshape(-1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2); stream.setsampwidth(2); stream.setframerate(rate)
        stream.writeframes(raw.tobytes())


def metrics(audio: np.ndarray, block_size: int) -> dict:
    delta = np.abs(np.diff(audio, axis=1))
    boundaries = np.arange(block_size, audio.shape[1], block_size)
    boundary = np.abs(audio[:, boundaries] - audio[:, boundaries - 1])
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    return {
        "frames": int(audio.shape[1]), "finite": bool(np.isfinite(audio).all()),
        "peak": peak, "peak_dbfs": 20 * math.log10(max(peak, 1e-12)),
        "rms": rms, "rms_dbfs": 20 * math.log10(max(rms, 1e-12)),
        "max_sample_delta": float(np.max(delta)),
        "p999_sample_delta": float(np.quantile(delta, 0.999)),
        "max_block_boundary_delta": float(np.max(boundary)),
    }


def render_preview(scene: dict, output_path: str | Path,
                   start_seconds: float = 136.0, duration_seconds: float = 7.0,
                   block_size: int = 256) -> dict:
    sources = {source["source_id"]: source for source in scene["sources"]
               if source["source_id"] in ("percussion", "woodwinds")}
    rendered = {}
    rate = None
    for role, source in sources.items():
        dry, source_rate = read_segment(source["input_file"], start_seconds, duration_seconds)
        rate = rate or source_rate
        if source_rate != rate:
            raise ValueError("preview stems are not sample-aligned")
        rendered[role] = DearVRRenderer(rate, block_size).render(
            dry, source, timeline_offset_seconds=start_seconds
        )
    mix = (rendered["percussion"] + rendered["woodwinds"]) * 0.5
    pre_peak = float(np.max(np.abs(mix)))
    safety_gain = min(1.0, 0.95 / max(pre_peak, 1e-12))
    mix *= safety_gain
    write_pcm16(output_path, mix, rate)

    times = np.arange(start_seconds, start_seconds + duration_seconds, block_size / rate)
    unwrapped = np.asarray([interpolate_pose(sources["percussion"]["keyframes"], time)[0] for time in times])
    wrapped = np.asarray([wrap_azimuth(value) for value in unwrapped])
    circular_steps = (np.diff(wrapped) + 180.0) % 360.0 - 180.0
    return {
        "preview_interval": {"start_seconds": start_seconds,
                             "end_seconds": start_seconds + duration_seconds},
        "output": str(Path(output_path)), "sample_rate": rate, "block_size": block_size,
        "distance_policy": {"meters": 3.0, "raw": 0.0969899744, "dynamic": False},
        "angular_validation": {
            "unwrapped_start_deg": float(unwrapped[0]),
            "unwrapped_end_deg": float(unwrapped[-1]),
            "wrapped_boundary_crossings": int(np.count_nonzero(np.abs(np.diff(wrapped)) > 180)),
            "max_circular_step_deg": float(np.max(np.abs(circular_steps))),
            "monotonic_unwrapped": bool(np.all(np.diff(unwrapped) >= 0)),
        },
        "sources": {role: metrics(audio, block_size) for role, audio in rendered.items()},
        "mix": metrics(mix, block_size) | {"pre_safety_peak": pre_peak, "safety_gain": safety_gain},
    }


def run(scene_path: str | Path, output_path: str | Path,
        report_path: str | Path) -> dict:
    scene = json.loads(Path(scene_path).read_text(encoding="utf-8"))
    report = render_preview(scene, output_path)
    report_path = Path(report_path); report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
