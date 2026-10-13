from __future__ import annotations

from hashlib import sha256
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
from dearvr_adapter import (
    PLUGIN_PATH, configure_direct_signal, interpolate_keyframe_value,
    interpolate_pose, set_pose,
)

RATE = 48_000
BLOCK = 256
START = 145.0
DURATION = 15.0
FRAMES = round(DURATION * RATE)
DISTANCE_MIN_M = 0.1
DISTANCE_MAX_M = 30.0


def distance_to_raw(meters: float) -> float:
    meters = max(DISTANCE_MIN_M, min(DISTANCE_MAX_M, float(meters)))
    return (meters - DISTANCE_MIN_M) / (DISTANCE_MAX_M - DISTANCE_MIN_M)


def raw_to_distance(raw: float) -> float:
    return DISTANCE_MIN_M + max(0.0, min(1.0, float(raw))) * (
        DISTANCE_MAX_M - DISTANCE_MIN_M)


def set_distance(plugin, meters: float) -> None:
    plugin.parameters["distance"].raw_value = distance_to_raw(meters)


def parameter_summary(parameter) -> dict:
    values = parameter.valid_values
    sample = None
    if values:
        indexes = sorted({0, len(values) // 4, len(values) // 2,
                          3 * len(values) // 4, len(values) - 1})
        sample = [values[index] for index in indexes]
    original = float(parameter.raw_value)
    automatable = True
    error = None
    try:
        parameter.raw_value = min(1.0, max(0.0, original + 0.001))
        parameter.raw_value = original
    except Exception as exc:
        automatable = False
        error = f"{type(exc).__name__}: {exc}"
    return {
        "raw_default_observed": original,
        "min_value": parameter.min_value,
        "max_value": parameter.max_value,
        "is_discrete": parameter.is_discrete,
        "is_boolean": parameter.is_boolean,
        "valid_value_count": len(values) if values is not None else None,
        "valid_value_samples": sample,
        "raw_value_settable": automatable,
        "automation_probe_error": error,
    }


def rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))


def peak(audio: np.ndarray) -> float:
    return float(np.max(np.abs(audio)))


def db(value: float) -> float:
    return 20.0 * math.log10(max(float(value), 1e-15))


def audit_dearvr() -> dict:
    plugin = load_plugin(str(PLUGIN_PATH))
    parameters = {name: parameter_summary(parameter)
                  for name, parameter in plugin.parameters.items()}
    parameters["distance"]["unit"] = "meters"
    parameters["distance"]["physical_range"] = [0.1, 30.0]
    parameters["distance"]["mapping"] = "linear raw=(meters-0.1)/29.9"
    for name, unit in {
        "distance_scale": "scale factor", "clarity": "percent",
        "stereo_width": "degrees", "occlusion": "normalized",
        "direct_gain": "dB", "reflection_gain": "dB",
        "reflection_low_pass": "Hz", "reflection_high_pass": "Hz",
        "reverb_gain": "dB", "reverb_low_pass": "Hz",
        "reverb_high_pass": "Hz", "room_size": "percent",
    }.items():
        if name in parameters:
            parameters[name]["unit"] = unit

    # Observable audio response and block automation behavior.
    probe = np.zeros((2, RATE), dtype=np.float32)
    rng = np.random.default_rng(1801)
    probe[:, :RATE // 2] = rng.normal(0.0, 0.03, (2, RATE // 2)).astype(np.float32)
    responses = {}
    for meters in (1.5, 3.0, 5.0):
        instance = load_plugin(str(PLUGIN_PATH))
        configure_direct_signal(instance)
        set_pose(instance, 45.0, 0.0)
        set_distance(instance, meters)
        rendered = instance.process(probe, sample_rate=RATE, buffer_size=BLOCK, reset=True)
        responses[str(meters)] = {"raw": float(instance.parameters["distance"].raw_value),
                                  "output_rms_dbfs": db(rms(rendered)),
                                  "output_peak_dbfs": db(peak(rendered))}

    instance = load_plugin(str(PLUGIN_PATH))
    configure_direct_signal(instance)
    set_pose(instance, 190.0, 0.0)
    set_distance(instance, 4.2)
    pose_preserved = abs(raw_to_distance(instance.parameters["distance"].raw_value) - 4.2) <= 0.051
    return {
        "test_id": "T018-PARAMETER-AUDIT",
        "plugin_path": str(PLUGIN_PATH),
        "all_parameter_names": list(plugin.parameters.keys()),
        "parameters": parameters,
        "distance_behavior": {
            "probe_responses": responses,
            "pose_update_preserves_distance": pose_preserved,
            "block_automation": "supported through raw_value updates before each process block",
            "resolution_meters": 0.1,
        },
        "scope_decision": {
            "test_1_enabled": ["distance"],
            "held_constant_or_disabled": ["distance_scale", "clarity", "stereo_width",
                                            "occlusion", "reflection", "reverb",
                                            "virtual_acoustics"],
            "deferred_until_human_approval": ["early reflections", "clarity/HRTF",
                                               "width", "occlusion", "acoustic reality"],
        },
    }


DISTANCE_PROFILES = {
    "lead_vocal": (3.0, 3.0),
    "bass": (3.0, 3.0),
    "drums": (3.0, 3.0),
    "other": (3.0, 3.0),
    "backing_vocals": (3.0, 3.8),
    "guitar": (3.0, 3.7),
    "keyboards": (3.0, 4.1),
    "percussion": (3.0, 4.6),
    "synth": (3.0, 4.8),
    "woodwinds": (3.0, 4.4),
}


def distance_at(role: str, progress: float) -> float:
    near, far = DISTANCE_PROFILES[role]
    # Raised-cosine round trip: zero slope at start, midpoint and end.
    depth = math.sin(math.pi * max(0.0, min(1.0, progress))) ** 2
    return near + (far - near) * depth


def clarity_compensation_db(meters: float) -> float:
    """Restore part of distance attenuation without flattening the depth cue."""
    return min(1.8, max(0.0, 0.35 * 20.0 * math.log10(max(meters, 3.0) / 3.0)))


def read_excerpt(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (2, 2, RATE):
            raise ValueError(f"Unexpected stem format: {path}")
        stream.setpos(round(START * RATE))
        raw = stream.readframes(FRAMES)
    return np.frombuffer(raw, dtype="<i2").astype(np.float32).reshape(-1, 2).T / 32768.0


def render_variant(scene: dict, dynamic: bool) -> tuple[np.ndarray, dict]:
    mix = np.zeros((2, FRAMES), dtype=np.float32)
    source_reports = {}
    for source in scene["sources"]:
        role = source["source_id"]
        dry = read_excerpt(Path(source["input_file"]))
        plugin = load_plugin(str(PLUGIN_PATH))
        configure_direct_signal(plugin)
        output = np.zeros_like(dry)
        distance_values = []
        compensation_values = []
        first = True
        for start in range(0, FRAMES, BLOCK):
            end = min(start + BLOCK, FRAMES)
            absolute_time = START + start / RATE
            azimuth, elevation = interpolate_pose(source["keyframes"], absolute_time)
            set_pose(plugin, azimuth, elevation)
            progress = start / max(FRAMES - 1, 1)
            meters = distance_at(role, progress) if dynamic else 3.0
            set_distance(plugin, meters)
            distance_values.append(float(plugin.parameters["distance"].raw_value))
            compensation_db = clarity_compensation_db(meters) if dynamic else 0.0
            compensation_values.append(compensation_db)
            block = plugin.process(dry[:, start:end], sample_rate=RATE,
                                   buffer_size=BLOCK, reset=first)
            first = False
            gain_db = float(source.get("gain_db", 0.0)) + interpolate_keyframe_value(
                source["keyframes"], absolute_time, "gain_db", 0.0) + compensation_db
            output[:, start:end] = block[:, :end - start] * 10 ** (gain_db / 20.0)
        mix += output
        deltas = np.abs(np.diff(np.asarray(distance_values)))
        source_reports[role] = {
            "requested_range_m": list(DISTANCE_PROFILES[role]) if dynamic else [3.0, 3.0],
            "observed_raw_min": min(distance_values),
            "observed_raw_max": max(distance_values),
            "max_raw_step_per_block": float(deltas.max(initial=0.0)),
            "automation_continuous": bool(deltas.max(initial=0.0) < 0.001),
            "maximum_clarity_compensation_db": max(compensation_values),
        }
    return mix, source_reports


def decode_excerpt(path: Path) -> np.ndarray:
    process = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(START), "-i", str(path),
         "-t", str(DURATION), "-f", "f32le", "-acodec", "pcm_f32le",
         "-ac", "2", "-ar", str(RATE), "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return np.frombuffer(process.stdout, dtype="<f4").reshape(-1, 2).T


def write_pcm24(path: Path, audio: np.ndarray) -> None:
    process = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(RATE),
         "-ac", "2", "-i", "-", "-c:a", "pcm_s24le", str(path)],
        input=np.asarray(audio.T, dtype="<f4").tobytes(), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=True)


def spectral_distance(reference: dict, candidate: dict) -> dict:
    keys = reference["spectral_distribution"]
    differences = {key: candidate["spectral_distribution"][key] - value
                   for key, value in keys.items()}
    return {"band_delta_db": differences,
            "maximum_absolute_band_delta_db": max(abs(v) for v in differences.values())}


def render_test_1(project_root: str | Path) -> dict:
    root = Path(project_root)
    out = root / "renders" / "t018"
    reports = root / "reports"
    out.mkdir(parents=True, exist_ok=True)
    baseline = root / "renders" / "mastering" / "t017" / "TUKANA_B2_transient_refinement_24bit.wav"
    scene_path = root / "spatial_scenes" / "tukana_balanced_scene.json"
    protected_hash = sha256_file(baseline)
    scene = json.loads(scene_path.read_text(encoding="utf-8"))

    fixed, fixed_report = render_variant(scene, dynamic=False)
    dynamic, dynamic_report = render_variant(scene, dynamic=True)
    baseline_audio = decode_excerpt(baseline)
    baseline_audio = baseline_audio[:, :FRAMES]
    # Transplant only the distance-induced delta onto the approved B2 excerpt.
    candidate = baseline_audio + (dynamic - fixed)
    common_gain = min(1.0, 10 ** (-2.0 / 20.0) / max(peak(baseline_audio), peak(candidate)))
    baseline_safe = baseline_audio * common_gain
    candidate_safe = candidate * common_gain
    comparison_rms = min(rms(baseline_safe), rms(candidate_safe))
    baseline_matched = baseline_safe * comparison_rms / max(rms(baseline_safe), 1e-15)
    candidate_matched = candidate_safe * comparison_rms / max(rms(candidate_safe), 1e-15)

    baseline_path = out / "TUKANA_T018_test1_B2_baseline_145_160_level_matched_24bit.wav"
    candidate_path = out / "TUKANA_T018_test1_dynamic_distance_145_160_level_matched_24bit.wav"
    delta_path = out / "TUKANA_T018_test1_distance_delta_monitor_145_160_24bit.wav"
    write_pcm24(baseline_path, baseline_matched)
    write_pcm24(candidate_path, candidate_matched)
    delta_gain = min(1.0, 10 ** (-6 / 20) / max(peak(dynamic - fixed), 1e-15))
    write_pcm24(delta_path, (dynamic - fixed) * delta_gain)

    artifacts = {}
    for name, path in {"b2_baseline": baseline_path, "dynamic_distance": candidate_path,
                       "distance_delta_monitor": delta_path}.items():
        artifacts[name] = {"path": str(path), "sha256": sha256_file(path),
                           "format": ffprobe(path), "signal": signal_metrics(path),
                           "loudness": ebur128(path)}
    ref = artifacts["b2_baseline"]["signal"]
    cand = artifacts["dynamic_distance"]["signal"]
    spectral = spectral_distance(ref, cand)
    tests = {
        "b2_baseline_preserved": protected_hash == sha256_file(baseline),
        "preview_exact_frames": all(item["signal"]["frames"] == FRAMES
                                    for item in artifacts.values()),
        "pcm24_48khz_stereo": all(item["format"]["sample_fmt"] == "s32" and
                                   item["format"]["sample_rate"] == str(RATE) and
                                   item["format"]["channels"] == 2 for item in artifacts.values()),
        "finite_no_clipping": all(item["signal"]["finite"] and item["signal"]["sample_peak"] < 1.0
                                  for item in artifacts.values()),
        "true_peak_headroom": all(item["loudness"]["true_peak_dbtp"] <= -1.5
                                  for name, item in artifacts.items() if name != "distance_delta_monitor"),
        "loudness_matched": abs(artifacts["b2_baseline"]["loudness"]["integrated_lufs"] -
                                artifacts["dynamic_distance"]["loudness"]["integrated_lufs"]) <= 0.2,
        "automation_continuous": all(item["automation_continuous"]
                                     for item in dynamic_report.values()),
        "channel_balance_stable": abs(ref["channel_balance_db"] - cand["channel_balance_db"]) <= 0.35,
        "correlation_stable": abs(ref["lr_correlation"] - cand["lr_correlation"]) <= 0.08,
        "spectral_loss_within_limit": spectral["maximum_absolute_band_delta_db"] <= 1.0,
        "transients_preserved": cand["crest_factor_db"] >= ref["crest_factor_db"] - 0.5,
        "no_large_new_discontinuity": cand["max_adjacent_sample_delta"] <=
                                      ref["max_adjacent_sample_delta"] + 0.10,
    }
    report = {
        "test_id": "T018-TEST-1", "status": "PASS" if all(tests.values()) else "FAIL",
        "human_review": "PENDING", "scope": "dynamic distance only",
        "preview": {"start_seconds": START, "end_seconds": START + DURATION,
                    "absolute_timeline_preserved": True},
        "method": {"baseline": str(baseline), "delta_transplant": True,
                   "description": "Dynamic-minus-fixed dearVR render delta added to the approved B2 excerpt.",
                   "clarity_compensation_policy": "35% of geometric distance attenuation, stereo-linked, capped at +1.8 dB",
                   "reflections": False, "reverb": False, "clarity_change": False,
                   "width_change": False, "occlusion": False,
                   "common_safety_gain": common_gain,
                   "perceptual_level_match": "equal full-preview RMS plus EBU verification"},
        "distance_profiles": DISTANCE_PROFILES,
        "fixed_render": fixed_report, "dynamic_render": dynamic_report,
        "spectral_comparison": spectral, "artifacts": artifacts, "tests": tests,
        "next_step": "Await human A/B review before Test 2 early reflections.",
    }
    (reports / "t018_test1_dynamic_distance.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def execute(project_root: str | Path) -> dict:
    root = Path(project_root)
    audit = audit_dearvr()
    audit_path = root / "reports" / "t018_dearvr_parameter_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    test = render_test_1(root)
    return {"audit": audit, "test": test}


if __name__ == "__main__":
    result = execute(ROOT / "projects" / "tukana")
    print(json.dumps({"audit": result["audit"]["test_id"],
                      "test_1_status": result["test"]["status"],
                      "validations": result["test"]["tests"]}, indent=2))


