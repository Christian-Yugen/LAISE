from __future__ import annotations

import hashlib
import json
import math
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SPATIAL_DIR = ROOT / "backend" / "spatial"
if str(SPATIAL_DIR) not in sys.path:
    sys.path.insert(0, str(SPATIAL_DIR))

from spatial_composer import build_scene, write_scene
from dearvr_adapter import DearVRRenderer

INPUT_DIR = ROOT / "evidence" / "T002" / "T002-CDF" / "stems"
OUT = ROOT / "evidence" / "T003"
SPATIAL_STEMS = OUT / "spatial_stems"
SCENE_PATH = OUT / "spatial_scene.json"
MIX_PATH = OUT / "laise_first_spatial_mix.wav"
RESULTS_PATH = OUT / "t003_results.json"

ROLES = {
    "strings_pad": "01_strings_pad_dry.wav",
    "bass_sub": "02_bass_sub_dry.wav",
    "drums_impacts": "03_drums_impacts_dry.wav",
    "lead_melody": "04_lead_melody_dry.wav",
}

SAMPLE_RATE = 48000


def read_pcm16_stereo(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        if wf.getnchannels() != 2:
            raise RuntimeError(f"{path.name}: expected stereo")
        if wf.getsampwidth() != 2:
            raise RuntimeError(f"{path.name}: expected PCM16")
        if wf.getframerate() != SAMPLE_RATE:
            raise RuntimeError(f"{path.name}: expected {SAMPLE_RATE} Hz")
        raw = wf.readframes(wf.getnframes())

    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return x.reshape(-1, 2).T


def write_pcm16_stereo(path: Path, audio: np.ndarray) -> None:
    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
    audio = np.clip(audio, -0.999, 0.999)
    interleaved = (audio.T.reshape(-1) * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(interleaved.tobytes())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(audio: np.ndarray) -> dict:
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))
    left = float(np.sqrt(np.mean(np.square(audio[0], dtype=np.float64))))
    right = float(np.sqrt(np.mean(np.square(audio[1], dtype=np.float64))))
    ild = 20.0 * math.log10(max(left, 1e-12) / max(right, 1e-12))
    return {
        "samples": int(audio.shape[1]),
        "duration_seconds": audio.shape[1] / SAMPLE_RATE,
        "peak": peak,
        "peak_dbfs": 20.0 * math.log10(max(peak, 1e-12)),
        "rms": rms,
        "rms_dbfs": 20.0 * math.log10(max(rms, 1e-12)),
        "left_rms": left,
        "right_rms": right,
        "ild_db": ild,
        "finite": bool(np.isfinite(audio).all()),
        "not_silent": rms > 1e-6,
    }


def main():
    print("=" * 78)
    print("LAISE — T003")
    print("Spatial Composer v0.1 + dearVR multistem render")
    print("=" * 78)

    OUT.mkdir(parents=True, exist_ok=True)
    SPATIAL_STEMS.mkdir(parents=True, exist_ok=True)

    paths = {role: INPUT_DIR / filename for role, filename in ROLES.items()}
    missing = [str(p) for p in paths.values() if not p.is_file()]
    if missing:
        raise FileNotFoundError("Missing T002 stems:\n" + "\n".join(missing))

    dry = {role: read_pcm16_stereo(path) for role, path in paths.items()}
    max_samples = max(a.shape[1] for a in dry.values())
    duration = max_samples / SAMPLE_RATE

    scene = build_scene(paths, duration)
    write_scene(SCENE_PATH, scene)

    renderer = DearVRRenderer(sample_rate=SAMPLE_RATE, buffer_size=256)
    spatial = {}
    report = {}

    for source in scene["sources"]:
        role = source["source_id"]
        print(f"Rendering spatial source: {role} | {source['trajectory']}")
        rendered = renderer.render(dry[role], source)
        spatial[role] = rendered

        out_path = SPATIAL_STEMS / f"{role}_spatial.wav"
        write_pcm16_stereo(out_path, rendered)
        report[role] = {
            "trajectory": source["trajectory"],
            "keyframe_count": len(source["keyframes"]),
            "output": str(out_path),
            "sha256": sha256(out_path),
            "metrics": metrics(rendered),
        }

    mix = np.zeros((2, max_samples), dtype=np.float32)
    for role, audio in spatial.items():
        mix[:, : audio.shape[1]] += audio

    pre_peak = float(np.max(np.abs(mix)))
    # Transparent safety normalization only when necessary.
    normalization_gain = 1.0
    if pre_peak > 0.92:
        normalization_gain = 0.92 / pre_peak
        mix *= normalization_gain

    write_pcm16_stereo(MIX_PATH, mix)
    mix_metrics = metrics(mix)

    validations = {
        "scene_has_four_sources": len(scene["sources"]) == 4,
        "four_spatial_stems_created": len(list(SPATIAL_STEMS.glob("*_spatial.wav"))) == 4,
        "all_sources_finite": all(v["metrics"]["finite"] for v in report.values()),
        "all_sources_non_silent": all(v["metrics"]["not_silent"] for v in report.values()),
        "all_trajectories_have_multiple_keyframes": all(
            v["keyframe_count"] >= 3 for v in report.values()
        ),
        "final_mix_finite": mix_metrics["finite"],
        "final_mix_non_silent": mix_metrics["not_silent"],
        "final_mix_no_clipping": mix_metrics["peak"] < 0.999,
        "distinct_spatial_outputs": len({v["sha256"] for v in report.values()}) == 4,
    }

    result = "PASS" if all(validations.values()) else "FAIL"

    results = {
        "test_id": "T003",
        "result": result,
        "scene": str(SCENE_PATH),
        "renderer": "dearVR PRO 2",
        "sample_rate": SAMPLE_RATE,
        "buffer_size": 256,
        "sources": report,
        "mix": {
            "output": str(MIX_PATH),
            "sha256": sha256(MIX_PATH),
            "pre_normalization_peak": pre_peak,
            "normalization_gain": normalization_gain,
            "metrics": mix_metrics,
        },
        "validations": validations,
        "perceptual_result": "PENDING",
    }
    RESULTS_PATH.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "-" * 78)
    print("AUTOMATED VALIDATION")
    print("-" * 78)
    for name, passed in validations.items():
        print(f"{name:<48}{'PASS' if passed else 'FAIL'}")

    print("\n" + "=" * 78)
    print("T003 OBJECTIVE RESULT:", result)
    print("T003 PERCEPTUAL RESULT: PENDING")
    print("=" * 78)
    print("Scene:        ", SCENE_PATH)
    print("Spatial stems:", SPATIAL_STEMS)
    print("Spatial mix:  ", MIX_PATH)
    print("Results:      ", RESULTS_PATH)


if __name__ == "__main__":
    main()
