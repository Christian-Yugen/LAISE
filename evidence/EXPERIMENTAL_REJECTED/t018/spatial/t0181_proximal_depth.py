from __future__ import annotations

from pathlib import Path
import json
import math
import subprocess
import sys
import wave

import numpy as np
from pedalboard import load_plugin

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "backend" / "mastering"))

from tukana_mastering import ebur128, ffprobe, sha256_file, signal_metrics
from dearvr_adapter import (PLUGIN_PATH, configure_direct_signal,
                            interpolate_keyframe_value, interpolate_pose, set_pose)
from t018_acoustic_depth import (distance_to_raw, set_distance, spectral_distance)

RATE = 48_000
BLOCK = 256
OUTPUT_START = 145.0
PRE_ROLL = 1.0
RENDER_START = OUTPUT_START - PRE_ROLL
DURATION = 15.0
RENDER_FRAMES = round((DURATION + PRE_ROLL) * RATE)
OUTPUT_FRAMES = round(DURATION * RATE)
CROP_FRAME = round(PRE_ROLL * RATE)

MICRO_DISTANCE = {
    "lead_vocal": (3.0, 3.0), "bass": (3.0, 3.0), "drums": (3.0, 3.0),
    "other": (3.0, 3.0), "backing_vocals": (3.0, 3.3),
    "guitar": (3.0, 3.3), "keyboards": (3.0, 3.4),
    "percussion": (3.0, 3.6), "synth": (3.0, 3.6),
    "woodwinds": (3.0, 3.5),
}

CLARITY_PERCENT = {
    "lead_vocal": 6.0, "backing_vocals": 8.0, "drums": 4.0,
    "bass": 3.0, "guitar": 6.0, "keyboards": 8.0,
    "percussion": 10.0, "synth": 8.0, "other": 0.0,
    "woodwinds": 10.0,
}


def db(value: float) -> float:
    return 20.0 * math.log10(max(float(value), 1e-15))


def rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))


def peak(audio: np.ndarray) -> float:
    return float(np.max(np.abs(audio)))


def parameter_raw_for_value(parameter, value) -> float:
    values = list(parameter.valid_values)
    if not values:
        raise ValueError("Parameter has no enumerable values")
    if isinstance(value, str):
        index = values.index(value)
    else:
        index = min(range(len(values)), key=lambda i: abs(float(values[i]) - float(value)))
    return index / max(len(values) - 1, 1)


def set_parameter_value(plugin, name: str, value) -> float:
    parameter = plugin.parameters[name]
    raw = parameter_raw_for_value(parameter, value)
    parameter.raw_value = raw
    return float(parameter.raw_value)


def micro_distance_at(role: str, absolute_time: float) -> float:
    if absolute_time <= OUTPUT_START:
        return 3.0
    progress = min(1.0, (absolute_time - OUTPUT_START) / DURATION)
    near, far = MICRO_DISTANCE[role]
    return near + (far - near) * math.sin(math.pi * progress) ** 2


def clarity_compensation_db(meters: float) -> float:
    return min(0.6, max(0.0, 0.25 * 20.0 * math.log10(max(meters, 3.0) / 3.0)))


def configure_mode(plugin, mode: str, role: str) -> dict:
    configure_direct_signal(plugin)
    state = {"reflection": False, "reverb": False, "clarity_percent": 0.0}
    if mode == "reflections":
        state.update({
            "virtual_acoustics": "SmallRoom",
            "virtual_acoustics_raw": set_parameter_value(plugin, "virtual_acoustics", "SmallRoom"),
            "reflection": True,
            "reflection_raw": set_parameter_value(plugin, "reflection", True),
            "reflection_gain_db": -30.0,
            "reflection_gain_raw": set_parameter_value(plugin, "reflection_gain", -30.0),
            "reflection_high_pass_hz": 120.0,
            "reflection_high_pass_raw": set_parameter_value(plugin, "reflection_high_pass", 120.0),
            "reflection_low_pass_hz": 12000.0,
            "reflection_low_pass_raw": set_parameter_value(plugin, "reflection_low_pass", 12000.0),
        })
        set_parameter_value(plugin, "reverb", False)
    elif mode == "clarity":
        value = CLARITY_PERCENT[role]
        state.update({"clarity_percent": value,
                      "clarity_raw": set_parameter_value(plugin, "clarity", value)})
    return state


def read_excerpt(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (2, 2, RATE):
            raise ValueError(f"Unexpected stem format: {path}")
        stream.setpos(round(RENDER_START * RATE))
        raw = stream.readframes(RENDER_FRAMES)
    return np.frombuffer(raw, dtype="<i2").astype(np.float32).reshape(-1, 2).T / 32768.0


def render_mode(scene: dict, mode: str) -> tuple[np.ndarray, dict]:
    mix = np.zeros((2, RENDER_FRAMES), dtype=np.float32)
    source_reports = {}
    for source in scene["sources"]:
        role = source["source_id"]
        dry = read_excerpt(Path(source["input_file"]))
        plugin = load_plugin(str(PLUGIN_PATH))
        state = configure_mode(plugin, mode, role)
        output = np.zeros_like(dry)
        distance_raw = []
        compensation = []
        first = True
        for start in range(0, RENDER_FRAMES, BLOCK):
            end = min(start + BLOCK, RENDER_FRAMES)
            absolute_time = RENDER_START + start / RATE
            azimuth, elevation = interpolate_pose(source["keyframes"], absolute_time)
            set_pose(plugin, azimuth, elevation)
            meters = micro_distance_at(role, absolute_time) if mode == "microdistance" else 3.0
            set_distance(plugin, meters)
            distance_raw.append(float(plugin.parameters["distance"].raw_value))
            gain_compensation = clarity_compensation_db(meters) if mode == "microdistance" else 0.0
            compensation.append(gain_compensation)
            block = plugin.process(dry[:, start:end], sample_rate=RATE,
                                   buffer_size=BLOCK, reset=first)
            first = False
            gain_db = float(source.get("gain_db", 0.0)) + interpolate_keyframe_value(
                source["keyframes"], absolute_time, "gain_db", 0.0) + gain_compensation
            output[:, start:end] = block[:, :end - start] * 10 ** (gain_db / 20.0)
        mix += output
        raw_steps = np.abs(np.diff(np.asarray(distance_raw)))
        source_reports[role] = {
            "mode": mode, "configuration": state,
            "distance_range_m": list(MICRO_DISTANCE[role]) if mode == "microdistance" else [3.0, 3.0],
            "distance_raw_min": min(distance_raw), "distance_raw_max": max(distance_raw),
            "maximum_distance_raw_step": float(raw_steps.max(initial=0.0)),
            "maximum_level_compensation_db": max(compensation),
        }
    return mix[:, CROP_FRAME:CROP_FRAME + OUTPUT_FRAMES], source_reports


def decode_baseline(path: Path) -> np.ndarray:
    process = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(OUTPUT_START), "-i", str(path),
         "-t", str(DURATION), "-f", "f32le", "-acodec", "pcm_f32le",
         "-ac", "2", "-ar", str(RATE), "-"], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=True)
    return np.frombuffer(process.stdout, dtype="<f4").reshape(-1, 2).T[:, :OUTPUT_FRAMES]


def write_pcm24(path: Path, audio: np.ndarray) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(RATE),
         "-ac", "2", "-i", "-", "-c:a", "pcm_s24le", str(path)],
        input=np.asarray(audio.T, dtype="<f4").tobytes(), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=True)


def execute(project_root: str | Path) -> dict:
    root = Path(project_root)
    out = root / "renders" / "t018_1"
    out.mkdir(parents=True, exist_ok=True)
    baseline_path = root / "renders" / "mastering" / "t017" / "TUKANA_B2_transient_refinement_24bit.wav"
    scene_path = root / "spatial_scenes" / "tukana_balanced_scene.json"
    protected_hash = sha256_file(baseline_path)
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    baseline_audio = decode_baseline(baseline_path)

    fixed, fixed_report = render_mode(scene, "fixed")
    variants = {}
    source_reports = {"fixed": fixed_report}
    for mode in ("microdistance", "reflections", "clarity"):
        rendered, source_reports[mode] = render_mode(scene, mode)
        variants[mode] = baseline_audio + (rendered - fixed)

    maximum = max([peak(baseline_audio)] + [peak(audio) for audio in variants.values()])
    common_gain = min(1.0, 10 ** (-2.0 / 20.0) / maximum)
    material = {"B2_baseline": baseline_audio * common_gain,
                **{name: audio * common_gain for name, audio in variants.items()}}
    target_rms = min(rms(audio) for audio in material.values())
    material = {name: audio * target_rms / max(rms(audio), 1e-15)
                for name, audio in material.items()}

    filenames = {
        "B2_baseline": "TUKANA_T0181_B2_baseline_145_160_level_matched_24bit.wav",
        "microdistance": "TUKANA_T0181_A_microdistance_145_160_level_matched_24bit.wav",
        "reflections": "TUKANA_T0181_B_early_reflections_145_160_level_matched_24bit.wav",
        "clarity": "TUKANA_T0181_C_clarity_145_160_level_matched_24bit.wav",
    }
    artifacts = {}
    for name, audio in material.items():
        path = out / filenames[name]
        write_pcm24(path, audio)
        artifacts[name] = {"path": str(path), "sha256": sha256_file(path),
                           "format": ffprobe(path), "signal": signal_metrics(path),
                           "loudness": ebur128(path)}

    reference = artifacts["B2_baseline"]["signal"]
    comparisons = {}
    for name in ("microdistance", "reflections", "clarity"):
        signal = artifacts[name]["signal"]
        comparisons[name] = {
            "spectral": spectral_distance(reference, signal),
            "crest_delta_db": signal["crest_factor_db"] - reference["crest_factor_db"],
            "correlation_delta": signal["lr_correlation"] - reference["lr_correlation"],
            "channel_balance_delta_db": signal["channel_balance_db"] - reference["channel_balance_db"],
            "max_sample_delta_change": signal["max_adjacent_sample_delta"] -
                                       reference["max_adjacent_sample_delta"],
        }
    loudness = [item["loudness"]["integrated_lufs"] for item in artifacts.values()]
    tests = {
        "b2_preserved": protected_hash == sha256_file(baseline_path),
        "four_outputs": len(artifacts) == 4,
        "exact_duration": all(item["signal"]["frames"] == OUTPUT_FRAMES for item in artifacts.values()),
        "pcm24_48khz_stereo": all(item["format"]["sample_fmt"] == "s32" and
                                   item["format"]["sample_rate"] == str(RATE) and
                                   item["format"]["channels"] == 2 for item in artifacts.values()),
        "finite_no_clipping": all(item["signal"]["finite"] and item["signal"]["sample_peak"] < 1.0
                                  for item in artifacts.values()),
        "true_peak_headroom": all(item["loudness"]["true_peak_dbtp"] <= -1.5
                                  for item in artifacts.values()),
        "loudness_matched": max(loudness) - min(loudness) <= 0.2,
        "spectral_change_conservative": all(value["spectral"]["maximum_absolute_band_delta_db"] <= 1.0
                                            for value in comparisons.values()),
        "transients_preserved": all(value["crest_delta_db"] >= -0.5 for value in comparisons.values()),
        "correlation_stable": all(abs(value["correlation_delta"]) <= 0.08
                                  for value in comparisons.values()),
        "channel_balance_stable": all(abs(value["channel_balance_delta_db"]) <= 0.35
                                      for value in comparisons.values()),
        "no_large_new_discontinuity": all(value["max_sample_delta_change"] <= 0.10
                                           for value in comparisons.values()),
    }
    report = {
        "test_id": "T018.1", "status": "PASS" if all(tests.values()) else "FAIL",
        "human_review": "PENDING", "baseline": str(baseline_path),
        "preview": {"start_seconds": OUTPUT_START,
                    "end_seconds": OUTPUT_START + DURATION,
                    "pre_roll_seconds": PRE_ROLL},
        "isolation": {
            "microdistance": {"only_variable": "distance", "profiles_m": MICRO_DISTANCE,
                              "compensation": "25% geometric, maximum +0.6 dB"},
            "reflections": {"only_variable": "early reflections", "room": "SmallRoom",
                            "gain_db": -30.0, "high_pass_hz": 120.0,
                            "low_pass_hz": 12000.0, "reverb": False},
            "clarity": {"only_variable": "clarity", "per_role_percent": CLARITY_PERCENT},
            "combined_version_created": False,
        },
        "common_safety_gain": common_gain,
        "level_match": "equal RMS across all four files plus EBU verification",
        "source_reports": source_reports, "artifacts": artifacts,
        "comparisons_to_b2": comparisons, "tests": tests,
        "next_step": "Await independent human comparison before combining any dimension.",
    }
    report_path = root / "reports" / "t0181_proximal_acoustic_depth.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = execute(ROOT / "projects" / "tukana")
    print(json.dumps({"status": result["status"], "tests": result["tests"]}, indent=2))
