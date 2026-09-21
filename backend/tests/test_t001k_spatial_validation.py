"""
LAISE — T001-K
Spatial Signal Analyzer + Guided Training + Blind ABX

Purpose
-------
Test whether dearVR FRONT (0 deg) and BACK (180 deg) are objectively different
and whether a listener can learn to discriminate them after guided exposure.

K1: objective FRONT/BACK analysis
K2: labelled training references FRONT/BACK/LEFT/RIGHT
K3: 20-trial blind ABX FRONT vs BACK

IMPORTANT
---------
Do not open PRIVATE/abx_key.json before completing the ABX listening test.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import random
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pedalboard
from pedalboard import load_plugin

# ============================================================
# CONFIGURATION
# ============================================================

SAMPLE_RATE = 48000
DURATION_SECONDS = 5.0
AMPLITUDE = 0.10
BUFFER_SIZE = 256
SEED = 20260920
ABX_TRIALS = 20
DISTANCE_M = 3.0

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PLUGIN_PATH = Path(
    r"C:\Program Files\Common Files\VST3"
    r"\dearVR PRO 2.vst3"
    r"\Contents\x86_64-win"
    r"\dearVR PRO 2.vst3"
)

OUTPUT_DIR = PROJECT_ROOT / "evidence" / "T001" / "T001-K"
K1_DIR = OUTPUT_DIR / "K1_OBJECTIVE"
K2_DIR = OUTPUT_DIR / "K2_TRAINING"
K3_DIR = OUTPUT_DIR / "K3_ABX"
PRIVATE_DIR = OUTPUT_DIR / "PRIVATE"

OBJECTIVE_PATH = K1_DIR / "objective_analysis.json"
ABX_KEY_PATH = PRIVATE_DIR / "abx_key.json"
ABX_SHEET_PATH = K3_DIR / "abx_listening_sheet.json"
RESULTS_PATH = OUTPUT_DIR / "t001k_results.json"

# ============================================================
# HELPERS
# ============================================================


def fail(message: str):
    print()
    print("FAIL:", message)
    raise SystemExit(1)


def distance_to_raw(distance_m: float) -> float:
    distance_m = max(0.1, min(30.0, distance_m))
    index = round((distance_m - 0.1) / 0.1)
    return index / 299.0


def azimuth_to_raw(degrees: float) -> float:
    degrees = max(-180.0, min(180.0, degrees))
    return (degrees + 180.0) / 360.0


def elevation_to_raw(degrees: float) -> float:
    degrees = max(-90.0, min(90.0, degrees))
    return (degrees + 90.0) / 180.0


def set_raw(plugin, name: str, value: float):
    if name not in plugin.parameters:
        fail(f"Missing plugin parameter: {name}")
    plugin.parameters[name].raw_value = float(value)


def get_repr(plugin, name: str) -> str:
    return str(plugin.parameters[name])


def get_valid_values(plugin, name: str):
    try:
        values = plugin.parameters[name].valid_values
        return None if values is None else list(values)
    except Exception:
        return None


def set_discrete_by_text(plugin, name: str, desired_text: str):
    values = get_valid_values(plugin, name)
    if not values:
        fail(f"No valid_values exposed for {name}")
    normalized = [str(v).strip() for v in values]
    if desired_text not in normalized:
        fail(
            f"{desired_text!r} not available for {name}. "
            f"Available values include: {normalized[:10]}"
        )
    index = normalized.index(desired_text)
    raw = 0.0 if len(normalized) == 1 else index / (len(normalized) - 1)
    set_raw(plugin, name, raw)
    return raw


def write_wav(path: Path, audio: np.ndarray, sample_rate: int):
    audio = np.asarray(audio, dtype=np.float32)
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio.T * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(audio.shape[0])
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())


def sha256_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def create_test_signal() -> np.ndarray:
    sample_count = int(SAMPLE_RATE * DURATION_SECONDS)
    rng = np.random.default_rng(SEED)
    noise = rng.normal(0.0, 1.0, sample_count).astype(np.float32)
    noise /= max(float(np.max(np.abs(noise))), 1e-12)
    noise *= AMPLITUDE
    return np.vstack([noise, noise]).astype(np.float32)


def configure_direct_geometry(plugin, azimuth_deg: float):
    # T001-H established: raw 1.0 = Polar.
    set_raw(plugin, "coordinate_system", 1.0)
    set_raw(plugin, "azimuth", azimuth_to_raw(azimuth_deg))
    set_raw(plugin, "elevation", elevation_to_raw(0.0))
    set_raw(plugin, "distance", distance_to_raw(DISTANCE_M))
    set_raw(plugin, "occlusion", 0.0)
    set_raw(plugin, "performance_mode", 0.0)

    # Direct binaural signal: remove room/reflection variables.
    set_discrete_by_text(plugin, "virtual_acoustics", "DirectSignal")
    set_raw(plugin, "reflection", 0.0)
    set_raw(plugin, "reverb", 0.0)


def render_direction(input_audio: np.ndarray, azimuth_deg: float):
    plugin = load_plugin(str(PLUGIN_PATH))
    configure_direct_geometry(plugin, azimuth_deg)

    state = {
        "coordinate_system": get_repr(plugin, "coordinate_system"),
        "azimuth": get_repr(plugin, "azimuth"),
        "elevation": get_repr(plugin, "elevation"),
        "distance": get_repr(plugin, "distance"),
        "virtual_acoustics": get_repr(plugin, "virtual_acoustics"),
        "reflection": get_repr(plugin, "reflection"),
        "reverb": get_repr(plugin, "reverb"),
    }

    output = plugin.process(
        input_audio,
        sample_rate=SAMPLE_RATE,
        buffer_size=BUFFER_SIZE,
        reset=True,
    )
    output = np.asarray(output, dtype=np.float32)
    if output.ndim != 2 or output.shape[0] != 2:
        fail(f"Expected stereo output, got {output.shape}")
    return output, state


def basic_metrics(audio: np.ndarray):
    left, right = audio[0], audio[1]
    peak = float(np.max(np.abs(audio)))
    left_rms = float(np.sqrt(np.mean(np.square(left))))
    right_rms = float(np.sqrt(np.mean(np.square(right))))
    overall_rms = float(np.sqrt(np.mean(np.square(audio))))
    eps = 1e-12
    ild_db = float(20.0 * math.log10((left_rms + eps) / (right_rms + eps)))
    correlation = float(np.corrcoef(left, right)[0, 1])
    return {
        "peak": peak,
        "overall_rms": overall_rms,
        "left_rms": left_rms,
        "right_rms": right_rms,
        "ild_db": ild_db,
        "lr_correlation": correlation,
        "finite": bool(np.all(np.isfinite(audio))),
        "no_clipping": bool(peak < 1.0),
    }


def estimate_itd(audio: np.ndarray, max_lag_ms: float = 1.5):
    """Estimate L/R delay using normalized FFT cross-correlation near zero lag."""
    left = audio[0].astype(np.float64)
    right = audio[1].astype(np.float64)
    left -= np.mean(left)
    right -= np.mean(right)

    n = len(left)
    nfft = 1 << (2 * n - 1).bit_length()
    spectrum = np.fft.rfft(left, nfft) * np.conj(np.fft.rfft(right, nfft))
    corr = np.fft.irfft(spectrum, nfft)
    corr = np.concatenate((corr[-(n - 1):], corr[:n]))
    lags = np.arange(-(n - 1), n)

    max_lag = int(round(max_lag_ms * SAMPLE_RATE / 1000.0))
    mask = np.abs(lags) <= max_lag
    local_corr = corr[mask]
    local_lags = lags[mask]
    best_index = int(np.argmax(np.abs(local_corr)))
    lag_samples = int(local_lags[best_index])
    lag_us = float(lag_samples * 1_000_000.0 / SAMPLE_RATE)

    denom = np.linalg.norm(left) * np.linalg.norm(right) + 1e-18
    normalized_peak = float(local_corr[best_index] / denom)
    return {
        "lag_samples_L_vs_R": lag_samples,
        "lag_microseconds_L_vs_R": lag_us,
        "normalized_xcorr_at_best_lag": normalized_peak,
        "search_window_ms": max_lag_ms,
    }


def band_rms_db(signal: np.ndarray, low_hz: float, high_hz: float) -> float:
    signal = signal.astype(np.float64)
    window = np.hanning(len(signal))
    spectrum = np.fft.rfft(signal * window)
    freqs = np.fft.rfftfreq(len(signal), 1.0 / SAMPLE_RATE)
    mask = (freqs >= low_hz) & (freqs < high_hz)
    if not np.any(mask):
        return -240.0
    power = float(np.mean(np.abs(spectrum[mask]) ** 2))
    return float(10.0 * math.log10(power + 1e-24))


def spectral_profile(audio: np.ndarray):
    bands = [
        (80, 250),
        (250, 500),
        (500, 1000),
        (1000, 2000),
        (2000, 4000),
        (4000, 8000),
        (8000, 16000),
        (16000, 22000),
    ]
    result = {}
    for low, high in bands:
        label = f"{low}-{high}_Hz"
        l_db = band_rms_db(audio[0], low, high)
        r_db = band_rms_db(audio[1], low, high)
        result[label] = {
            "left_db": l_db,
            "right_db": r_db,
            "ild_db": l_db - r_db,
        }
    return result


def compare_audio(a: np.ndarray, b: np.ndarray):
    delta = a.astype(np.float64) - b.astype(np.float64)
    rms_delta = float(np.sqrt(np.mean(np.square(delta))))
    rms_a = float(np.sqrt(np.mean(np.square(a.astype(np.float64)))))
    rms_b = float(np.sqrt(np.mean(np.square(b.astype(np.float64)))))
    denom = np.linalg.norm(a.ravel()) * np.linalg.norm(b.ravel()) + 1e-18
    cosine = float(np.dot(a.ravel(), b.ravel()) / denom)
    return {
        "sample_rms_difference": rms_delta,
        "difference_vs_mean_signal_rms_ratio": float(
            rms_delta / (((rms_a + rms_b) / 2.0) + 1e-18)
        ),
        "flattened_cosine_similarity": cosine,
        "sample_identical": bool(np.array_equal(a, b)),
        "allclose_1e-7": bool(np.allclose(a, b, atol=1e-7, rtol=0.0)),
    }


def binomial_two_sided_p_value(k: int, n: int, p: float = 0.5) -> float:
    """Exact two-sided binomial p-value for the later ABX scoring step."""
    observed = math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))
    total = 0.0
    for i in range(n + 1):
        probability = math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
        if probability <= observed + 1e-15:
            total += probability
    return min(1.0, total)


# ============================================================
# START
# ============================================================

print()
print("=" * 78)
print("LAISE — T001-K")
print("Spatial Signal Analyzer + Guided Training + Blind ABX")
print("=" * 78)
print("Python:    ", platform.python_version())
print("Pedalboard:", pedalboard.__version__)
print("Plugin:    ", PLUGIN_PATH)

if not PLUGIN_PATH.is_file():
    fail(f"Plugin not found:\n{PLUGIN_PATH}")

for directory in (K1_DIR, K2_DIR, K3_DIR, PRIVATE_DIR):
    directory.mkdir(parents=True, exist_ok=True)

input_audio = create_test_signal()
print("Input shape:", input_audio.shape)
print("Input peak: ", f"{np.max(np.abs(input_audio)):.8f}")

# ============================================================
# K1 — OBJECTIVE FRONT/BACK ANALYSIS
# ============================================================

print()
print("-" * 78)
print("K1 — OBJECTIVE FRONT/BACK ANALYSIS")
print("-" * 78)

front, front_state = render_direction(input_audio, 0.0)
back, back_state = render_direction(input_audio, 180.0)

front_path = K1_DIR / "front_0deg.wav"
back_path = K1_DIR / "back_180deg.wav"
write_wav(front_path, front, SAMPLE_RATE)
write_wav(back_path, back, SAMPLE_RATE)

front_metrics = basic_metrics(front)
back_metrics = basic_metrics(back)
front_itd = estimate_itd(front)
back_itd = estimate_itd(back)
front_spectrum = spectral_profile(front)
back_spectrum = spectral_profile(back)
comparison = compare_audio(front, back)

band_differences = {}
for band in front_spectrum:
    band_differences[band] = {
        "front_minus_back_left_db": (
            front_spectrum[band]["left_db"] - back_spectrum[band]["left_db"]
        ),
        "front_minus_back_right_db": (
            front_spectrum[band]["right_db"] - back_spectrum[band]["right_db"]
        ),
        "front_minus_back_ild_db": (
            front_spectrum[band]["ild_db"] - back_spectrum[band]["ild_db"]
        ),
    }

objective = {
    "test_id": "T001-K1",
    "front": {
        "azimuth_deg": 0.0,
        "wav": str(front_path),
        "sha256": sha256_file(front_path),
        "plugin_state": front_state,
        "metrics": front_metrics,
        "itd": front_itd,
        "spectral_bands": front_spectrum,
    },
    "back": {
        "azimuth_deg": 180.0,
        "wav": str(back_path),
        "sha256": sha256_file(back_path),
        "plugin_state": back_state,
        "metrics": back_metrics,
        "itd": back_itd,
        "spectral_bands": back_spectrum,
    },
    "front_vs_back": comparison,
    "spectral_band_differences": band_differences,
}

with OBJECTIVE_PATH.open("w", encoding="utf-8") as file:
    json.dump(objective, file, indent=2, ensure_ascii=False)

print("FRONT ILD:", f"{front_metrics['ild_db']:+.4f} dB")
print("BACK  ILD:", f"{back_metrics['ild_db']:+.4f} dB")
print("FRONT ITD:", f"{front_itd['lag_microseconds_L_vs_R']:+.2f} us")
print("BACK  ITD:", f"{back_itd['lag_microseconds_L_vs_R']:+.2f} us")
print("F/B cosine similarity:", f"{comparison['flattened_cosine_similarity']:.8f}")
print("F/B sample-identical: ", comparison["sample_identical"])

# ============================================================
# K2 — GUIDED TRAINING REFERENCES
# ============================================================

print()
print("-" * 78)
print("K2 — GUIDED TRAINING REFERENCES")
print("-" * 78)

training_directions = {
    "FRONT": 0.0,
    "RIGHT": 90.0,
    "BACK": 180.0,
    "LEFT": -90.0,
}

training_records = {}
training_audio = {}

for label, azimuth in training_directions.items():
    # Reuse K1 exact FRONT/BACK buffers where possible.
    if label == "FRONT":
        audio, state = front.copy(), front_state
    elif label == "BACK":
        audio, state = back.copy(), back_state
    else:
        audio, state = render_direction(input_audio, azimuth)

    path = K2_DIR / f"{label}_{int(azimuth):+d}deg.wav"
    write_wav(path, audio, SAMPLE_RATE)
    training_audio[label] = audio
    training_records[label] = {
        "azimuth_deg": azimuth,
        "wav": str(path),
        "sha256": sha256_file(path),
        "metrics": basic_metrics(audio),
        "plugin_state": state,
    }
    print(f"{label:<6} {azimuth:+7.1f} deg -> {path.name}")

# ============================================================
# K3 — BLIND ABX FRONT vs BACK
# ============================================================

print()
print("-" * 78)
print("K3 — BLIND ABX FRONT vs BACK")
print("-" * 78)

# A and B are explicitly known references. X is randomized per trial.
a_path = K3_DIR / "A_FRONT.wav"
b_path = K3_DIR / "B_BACK.wav"
write_wav(a_path, front, SAMPLE_RATE)
write_wav(b_path, back, SAMPLE_RATE)

rng = random.Random(SEED + 300)
answers = ["A" if rng.random() < 0.5 else "B" for _ in range(ABX_TRIALS)]

# Guarantee both classes occur; deterministic fallback only if pathological.
if len(set(answers)) < 2:
    answers[0] = "A"
    answers[-1] = "B"

trials = []
private_trials = []
for index, answer in enumerate(answers, start=1):
    audio = front if answer == "A" else back
    x_path = K3_DIR / f"X{index:02d}.wav"
    write_wav(x_path, audio, SAMPLE_RATE)
    trials.append(
        {
            "trial": index,
            "file": x_path.name,
            "listener_answer_A_or_B": None,
            "confidence_0_to_5": None,
            "notes": None,
        }
    )
    private_trials.append(
        {
            "trial": index,
            "file": x_path.name,
            "correct_answer": answer,
            "direction": "FRONT" if answer == "A" else "BACK",
            "sha256": sha256_file(x_path),
        }
    )

abx_sheet = {
    "test_id": "T001-K3",
    "design": "ABX FRONT vs BACK",
    "A": {"label": "FRONT", "file": a_path.name, "azimuth_deg": 0.0},
    "B": {"label": "BACK", "file": b_path.name, "azimuth_deg": 180.0},
    "instructions": [
        "Use the same headphones and listening configuration for the whole test.",
        "First complete K2 guided training and repeat the labelled references as needed.",
        "In K3, A is the known FRONT reference and B is the known BACK reference.",
        "For each X file, decide only whether X matches A or B.",
        "Do not open PRIVATE/abx_key.json before all answers are recorded.",
        "Do not use waveform editors, hashes, file comparison tools, or metadata to answer.",
    ],
    "trials": trials,
}

with ABX_SHEET_PATH.open("w", encoding="utf-8") as file:
    json.dump(abx_sheet, file, indent=2, ensure_ascii=False)

with ABX_KEY_PATH.open("w", encoding="utf-8") as file:
    json.dump(
        {
            "WARNING": "DO NOT OPEN BEFORE COMPLETING ALL ABX LISTENING TRIALS.",
            "seed": SEED + 300,
            "trials": private_trials,
            "scoring_note": (
                "After listening, count correct A/B answers. Under chance p=0.5, "
                "use an exact binomial test; helper function is included in this script."
            ),
            "reference_example_p_values": {
                str(k): binomial_two_sided_p_value(k, ABX_TRIALS)
                for k in range((ABX_TRIALS // 2), ABX_TRIALS + 1)
            },
        },
        file,
        indent=2,
        ensure_ascii=False,
    )

print(f"A reference: {a_path.name} = FRONT")
print(f"B reference: {b_path.name} = BACK")
print(f"Blind trials created: {ABX_TRIALS}")

# ============================================================
# VALIDATION / RESULTS
# ============================================================

all_training_ok = all(
    rec["metrics"]["finite"]
    and rec["metrics"]["no_clipping"]
    and rec["metrics"]["overall_rms"] > 1e-7
    for rec in training_records.values()
)

validations = {
    "plugin_exists": PLUGIN_PATH.is_file(),
    "front_output_finite": front_metrics["finite"],
    "back_output_finite": back_metrics["finite"],
    "front_non_silent": front_metrics["overall_rms"] > 1e-7,
    "back_non_silent": back_metrics["overall_rms"] > 1e-7,
    "front_no_clipping": front_metrics["no_clipping"],
    "back_no_clipping": back_metrics["no_clipping"],
    "front_back_not_sample_identical": not comparison["sample_identical"],
    "four_training_references_created": len(training_records) == 4,
    "training_references_valid": all_training_ok,
    "twenty_abx_trials_created": len(private_trials) == ABX_TRIALS,
    "abx_contains_A_and_B": len(set(answers)) == 2,
}

objective_pass = all(validations.values())

results = {
    "test_id": "T001-K",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "objective_result": "PASS" if objective_pass else "FAIL",
    "perceptual_result": "PENDING",
    "environment": {
        "python": platform.python_version(),
        "pedalboard": pedalboard.__version__,
        "sample_rate": SAMPLE_RATE,
        "buffer_size": BUFFER_SIZE,
        "seed": SEED,
    },
    "K1_objective_analysis": str(OBJECTIVE_PATH),
    "K2_training": training_records,
    "K3_abx_sheet": str(ABX_SHEET_PATH),
    "K3_private_key": str(ABX_KEY_PATH),
    "validations": validations,
}

with RESULTS_PATH.open("w", encoding="utf-8") as file:
    json.dump(results, file, indent=2, ensure_ascii=False)

print()
print("-" * 78)
print("VALIDATIONS")
print("-" * 78)
for name, result in validations.items():
    print(f"{name:<48}{'PASS' if result else 'FAIL'}")

print()
print("=" * 78)
print(f"T001-K OBJECTIVE RESULT: {'PASS' if objective_pass else 'FAIL'}")
print("T001-K PERCEPTUAL RESULT: PENDING")
print("=" * 78)
print()
print("LISTENING ORDER")
print("1. Open K2_TRAINING and learn FRONT / RIGHT / BACK / LEFT.")
print("2. In K3_ABX, compare A_FRONT.wav and B_BACK.wav as often as needed.")
print("3. Classify X01.wav ... X20.wav only as A or B.")
print("4. Record every answer before opening the private key.")
print()
print("DO NOT OPEN BEFORE LISTENING:")
print(ABX_KEY_PATH)
print()
print("ABX listening sheet:")
print(ABX_SHEET_PATH)
print()
print("Objective analysis:")
print(OBJECTIVE_PATH)
print()
print("Results:")
print(RESULTS_PATH)

if not objective_pass:
    raise SystemExit(1)
