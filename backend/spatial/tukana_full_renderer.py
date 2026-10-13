from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import ctypes
import json
import math
import re
import shutil
import subprocess
import time
import wave

import numpy as np
from pedalboard import load_plugin

from dearvr_adapter import (
    PLUGIN_PATH,
    configure_direct_signal,
    interpolate_keyframe_value,
    interpolate_pose,
    set_pose,
)


def file_hash(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def working_set_mb() -> float | None:
    try:
        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        counters = Counters(); counters.cb = ctypes.sizeof(counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return counters.WorkingSetSize / (1024 * 1024)
    except Exception:
        pass
    return None


class Metrics:
    def __init__(self):
        self.frames = 0; self.peak = 0.0; self.squares = 0.0
        self.max_delta = 0.0; self.max_boundary_delta = 0.0
        self.finite = True; self.previous = None

    def update(self, audio: np.ndarray) -> None:
        self.frames += audio.shape[1]
        self.finite = self.finite and bool(np.isfinite(audio).all())
        self.peak = max(self.peak, float(np.max(np.abs(audio))))
        self.squares += float(np.sum(audio.astype(np.float64) ** 2))
        if audio.shape[1] > 1:
            self.max_delta = max(self.max_delta, float(np.max(np.abs(np.diff(audio, axis=1)))))
        if self.previous is not None:
            self.max_boundary_delta = max(self.max_boundary_delta,
                                          float(np.max(np.abs(audio[:, 0] - self.previous))))
        self.previous = audio[:, -1].copy()

    def result(self) -> dict:
        rms = math.sqrt(self.squares / max(self.frames * 2, 1))
        return {"frames": self.frames, "finite": self.finite, "peak": self.peak,
                "peak_dbfs": 20 * math.log10(max(self.peak, 1e-12)), "rms": rms,
                "rms_dbfs": 20 * math.log10(max(rms, 1e-12)),
                "max_sample_delta": self.max_delta,
                "max_block_boundary_delta": self.max_boundary_delta}


def write_block(stream: wave.Wave_write, audio: np.ndarray) -> None:
    raw = (np.clip(np.nan_to_num(audio), -0.999, 0.999).T.reshape(-1) * 32767).astype("<i2")
    stream.writeframesraw(raw.tobytes())


def scan_memmap(audio: np.memmap, chunk: int = 65536) -> dict:
    meter = Metrics()
    for start in range(0, audio.shape[1], chunk):
        meter.update(np.asarray(audio[:, start:start + chunk], dtype=np.float32))
    return meter.result()


def write_scaled_mix(path: Path, audio: np.memmap, gain: float,
                     rate: int, chunk: int = 65536) -> dict:
    meter = Metrics()
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2); stream.setsampwidth(2); stream.setframerate(rate)
        for start in range(0, audio.shape[1], chunk):
            block = np.asarray(audio[:, start:start + chunk], dtype=np.float32) * gain
            meter.update(block); write_block(stream, block)
    return meter.result()


def ebur128(path: Path) -> dict:
    process = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    integrated = re.findall(r"I:\s*(-?\d+(?:\.\d+)?) LUFS", process.stderr)
    true_peak = re.findall(r"Peak:\s*(-?\d+(?:\.\d+)?) dBFS", process.stderr)
    return {"method": "FFmpeg ebur128 peak=true", "returncode": process.returncode,
            "integrated_lufs": float(integrated[-1]) if integrated else None,
            "true_peak_dbtp": float(true_peak[-1]) if true_peak else None}


def render_full(scene_path: str | Path, project_root: str | Path,
                block_size: int = 256) -> dict:
    started = time.time(); scene_path = Path(scene_path); root = Path(project_root)
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    rate = 48000; frames = 12_844_801; duration = frames / rate
    stem_root = root / "spatial_stems" / "full"
    render_root = root / "renders"; report_root = root / "reports"
    work_root = render_root / "_t015_work"
    for folder in (stem_root, render_root, report_root, work_root): folder.mkdir(parents=True, exist_ok=True)
    spatial_mix = np.memmap(work_root / "spatial_mix.f32", mode="w+", dtype=np.float32, shape=(2, frames))
    dry_mix = np.memmap(work_root / "dry_mix.f32", mode="w+", dtype=np.float32, shape=(2, frames))
    spatial_mix[:] = 0; dry_mix[:] = 0
    source_reports = {}; progress = []; peak_memory = working_set_mb() or 0.0

    for source_index, source in enumerate(scene["sources"], 1):
        role = source["source_id"]; input_path = Path(source["input_file"])
        output_path = stem_root / f"{role}_spatial.wav"; meter = Metrics()
        plugin = load_plugin(str(PLUGIN_PATH)); configure_direct_signal(plugin)
        first_block = True; stem_started = time.time()
        with wave.open(str(input_path), "rb") as input_stream, wave.open(str(output_path), "wb") as output_stream:
            if (input_stream.getnchannels(), input_stream.getsampwidth(), input_stream.getframerate(),
                input_stream.getnframes()) != (2, 2, rate, frames):
                raise ValueError(f"{role}: input format or duration changed")
            output_stream.setnchannels(2); output_stream.setsampwidth(2); output_stream.setframerate(rate)
            cursor = 0; next_progress = 0.1
            while cursor < frames:
                count = min(block_size, frames - cursor)
                raw = input_stream.readframes(count)
                dry = np.frombuffer(raw, dtype="<i2").astype(np.float32).reshape(-1, 2).T / 32768.0
                time_seconds = cursor / rate
                azimuth, elevation = interpolate_pose(source["keyframes"], time_seconds)
                set_pose(plugin, azimuth, elevation)
                processed = plugin.process(dry, sample_rate=rate, buffer_size=block_size, reset=first_block)
                first_block = False; processed = processed[:, :count].astype(np.float32, copy=False)
                keyframe_gain = interpolate_keyframe_value(source["keyframes"], time_seconds, "gain_db", 0.0)
                gain = 10 ** ((float(source.get("gain_db", 0.0)) + keyframe_gain) / 20)
                processed *= gain; dry *= gain
                meter.update(processed); write_block(output_stream, processed)
                spatial_mix[:, cursor:cursor + count] += processed
                dry_mix[:, cursor:cursor + count] += dry
                cursor += count
                fraction = cursor / frames
                if fraction >= next_progress or cursor == frames:
                    memory = working_set_mb(); peak_memory = max(peak_memory, memory or 0.0)
                    progress.append({"source": role, "percent": round(fraction * 100, 1),
                                     "working_set_mb": memory})
                    print(f"[{source_index:02d}/10] {role}: {fraction * 100:5.1f}% | memory={memory}", flush=True)
                    next_progress += 0.1
        source_reports[role] = {"input": str(input_path), "output": str(output_path),
                                "metrics": meter.result(), "sha256": file_hash(output_path),
                                "elapsed_seconds": time.time() - stem_started}
        del plugin
    spatial_mix.flush(); dry_mix.flush()

    spatial_raw = scan_memmap(spatial_mix); dry_raw = scan_memmap(dry_mix)
    target_peak = 10 ** (-3.0 / 20)
    spatial_gain = min(1.0, target_peak / max(spatial_raw["peak"], 1e-12))
    dry_gain = spatial_raw["rms"] * spatial_gain / max(dry_raw["rms"], 1e-12)
    if dry_raw["peak"] * dry_gain > target_peak:
        common = target_peak / (dry_raw["peak"] * dry_gain)
        spatial_gain *= common; dry_gain *= common

    binaural_path = render_root / "TUKANA_binaural_full_master_candidate.wav"
    dry_path = render_root / "TUKANA_dry_full_comparison.wav"
    binaural_metrics = write_scaled_mix(binaural_path, spatial_mix, spatial_gain, rate)
    dry_metrics = write_scaled_mix(dry_path, dry_mix, dry_gain, rate)
    del spatial_mix, dry_mix
    (work_root / "spatial_mix.f32").unlink(); (work_root / "dry_mix.f32").unlink(); work_root.rmdir()

    effective_scene = render_root / "TUKANA_effective_spatial_scene.json"
    shutil.copy2(scene_path, effective_scene)
    rms_difference = 20 * math.log10(max(binaural_metrics["rms"], 1e-12) /
                                      max(dry_metrics["rms"], 1e-12))
    return {
        "test_id": "T015", "delivery_status": "MASTER_CANDIDATE",
        "human_approval_required": True, "duration_seconds": duration,
        "frames": frames, "sample_rate": rate, "block_size": block_size,
        "processing": {"float32": True, "incremental": True,
                       "independent_dearvr_instances": True,
                       "distance_m": 3.0, "dynamic_distance": False,
                       "peak_working_set_mb": peak_memory},
        "headroom_policy": {"target_sample_peak_dbfs": -3.0,
                            "uniform_spatial_mix_gain": spatial_gain,
                            "dry_level_match_gain": dry_gain},
        "source_reports": source_reports,
        "outputs": {
            "binaural": {"path": str(binaural_path), "sha256": file_hash(binaural_path),
                         "metrics": binaural_metrics, "ebu_r128": ebur128(binaural_path)},
            "dry_comparison": {"path": str(dry_path), "sha256": file_hash(dry_path),
                               "metrics": dry_metrics, "ebu_r128": ebur128(dry_path)},
            "effective_scene": {"path": str(effective_scene), "sha256": file_hash(effective_scene)},
            "rms_difference_db": rms_difference,
        },
        "progress_log": progress, "elapsed_seconds": time.time() - started,
        "pending": ["full human listening approval", "dynamic distance validation",
                    "global front/back perceptual validation", "final mastering", "YouTube packaging"],
    }
