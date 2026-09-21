"""
LAISE — T001-G
Blind Azimuth / Front-Back Perceptual Calibration

Purpose
-------
Investigate the front/back ambiguity observed in:

    t001c_front_static.wav
    t001d_front_000.wav
    t001d_back_180.wav
    t001f_orbit_360.wav

This test deliberately DOES NOT assume that the current LAISE angular
mapping is perceptually correct.

It renders eight equally spaced raw values of dearVR PRO 2's normalized
azimuth parameter.

IMPORTANT:
The generated audio filenames contain only anonymous IDs (A-H).
The raw azimuth values are stored separately in a private key JSON.

This allows blind listening before inspecting the mapping.

Signal
------
Deterministic broadband noise
48 kHz
4 seconds per position
Amplitude = 0.10
Dual-mono input
dearVR PRO 2
Polar coordinate system
Elevation = 0°
Fixed distance
No azimuth movement

Outputs
-------
evidence/T001/T001-G/audio/
    t001g_A.wav
    ...
    t001g_H.wav

evidence/T001/T001-G/
    t001g_blind_listening_sheet.json
    t001g_calibration_key.json
    t001g_results.json
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import random
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from pedalboard import load_plugin


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PLUGIN_PATH = Path(
    r"C:\Program Files\Common Files\VST3"
    r"\dearVR PRO 2.vst3"
    r"\Contents\x86_64-win"
    r"\dearVR PRO 2.vst3"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "evidence"
    / "T001"
    / "T001-G"
)

AUDIO_DIR = OUTPUT_DIR / "audio"

LISTENING_SHEET_PATH = (
    OUTPUT_DIR
    / "t001g_blind_listening_sheet.json"
)

CALIBRATION_KEY_PATH = (
    OUTPUT_DIR
    / "t001g_calibration_key.json"
)

RESULTS_PATH = (
    OUTPUT_DIR
    / "t001g_results.json"
)


# ============================================================
# TEST CONFIGURATION
# ============================================================

SAMPLE_RATE = 48_000
DURATION_SECONDS = 4.0

BLOCK_SIZE = 256

SIGNAL_AMPLITUDE = 0.10

SEED = 20260920

ELEVATION_RAW = 0.5

# Keep the same distance used in the previous T001 tests.
DISTANCE_RAW = 0.0969899744

RAW_AZIMUTH_VALUES = [
    0.000,
    0.125,
    0.250,
    0.375,
    0.500,
    0.625,
    0.750,
    0.875,
]

BLIND_IDS = [
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
]


# ============================================================
# HELPERS
# ============================================================

def sha256_file(path: Path) -> str:
    sha = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            block = file.read(1024 * 1024)

            if not block:
                break

            sha.update(block)

    return sha.hexdigest().upper()


def fail(message: str) -> None:
    print()
    print("FAIL:", message)
    print()
    print("T001-G RESULT: FAIL")
    raise SystemExit(1)


def pass_fail(value: bool) -> str:
    return "PASS" if value else "FAIL"


def rms(signal: np.ndarray) -> float:
    if signal.size == 0:
        return 0.0

    return float(
        np.sqrt(
            np.mean(
                np.square(
                    signal.astype(np.float64)
                )
            )
        )
    )


def write_wav_float_to_pcm16(
    path: Path,
    audio: np.ndarray,
    sample_rate: int,
) -> None:
    """
    audio shape:
        (channels, samples)

    Writes stereo 16-bit PCM WAV.
    """

    clipped = np.clip(
        audio,
        -1.0,
        1.0,
    )

    interleaved = clipped.T.reshape(-1)

    pcm16 = (
        interleaved * 32767.0
    ).astype("<i2")

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(audio.shape[0])
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm16.tobytes())


def set_parameter_raw(
    plugin,
    parameter_name: str,
    raw_value: float,
) -> None:
    if parameter_name not in plugin.parameters:
        fail(
            f"Plugin parameter not found: "
            f"{parameter_name}"
        )

    parameter = plugin.parameters[
        parameter_name
    ]

    parameter.raw_value = float(raw_value)


# ============================================================
# HEADER
# ============================================================

print()
print("=" * 76)
print("LAISE — T001-G")
print("Blind Azimuth / Front-Back Perceptual Calibration")
print("=" * 76)
print()

print("Python:")
print(platform.python_version())

print()
print("Plugin:")
print(PLUGIN_PATH)

print()
print("Sample rate:")
print(SAMPLE_RATE, "Hz")

print()
print("Duration per file:")
print(DURATION_SECONDS, "s")

print()
print("Block size:")
print(BLOCK_SIZE, "samples")

print()
print("Seed:")
print(SEED)


# ============================================================
# PRECHECK
# ============================================================

print()
print("-" * 76)
print("PRECHECK")
print("-" * 76)

plugin_exists = PLUGIN_PATH.is_file()

print(
    f"{'dearvr_plugin_exists':<40}"
    f"{pass_fail(plugin_exists)}"
)

if not plugin_exists:
    fail(
        f"dearVR PRO 2 not found:\n"
        f"{PLUGIN_PATH}"
    )

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

AUDIO_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# CREATE IDENTICAL DETERMINISTIC STIMULUS
# ============================================================

sample_count = int(
    SAMPLE_RATE * DURATION_SECONDS
)

rng = np.random.default_rng(SEED)

mono_signal = rng.normal(
    loc=0.0,
    scale=1.0,
    size=sample_count,
).astype(np.float32)

# Normalize deterministic broadband stimulus.
max_abs = float(
    np.max(
        np.abs(mono_signal)
    )
)

if max_abs <= 0.0:
    fail("Generated stimulus is silent.")

mono_signal /= max_abs

mono_signal *= SIGNAL_AMPLITUDE

# Same signal in both input channels.
input_audio = np.vstack(
    [
        mono_signal,
        mono_signal,
    ]
).astype(np.float32)


print()
print("-" * 76)
print("INPUT STIMULUS")
print("-" * 76)

print(
    f"Shape:             "
    f"{input_audio.shape}"
)

print(
    f"Peak:              "
    f"{np.max(np.abs(input_audio)):.8f}"
)

print(
    f"RMS:               "
    f"{rms(input_audio):.8f}"
)


# ============================================================
# RANDOMIZE BLIND PRESENTATION
# ============================================================

pairs = list(
    zip(
        BLIND_IDS,
        RAW_AZIMUTH_VALUES,
    )
)

blind_randomizer = random.Random(
    SEED + 1
)

blind_randomizer.shuffle(pairs)


# ============================================================
# RENDER ALL POSITIONS
# ============================================================

print()
print("-" * 76)
print("RENDERING BLIND POSITIONS")
print("-" * 76)

render_records = []

for index, (blind_id, raw_azimuth) in enumerate(
    pairs,
    start=1,
):
    print()
    print(
        f"Rendering blind sample "
        f"{index}/{len(pairs)}: "
        f"{blind_id}"
    )

    # Fresh plugin instance for every static position.
    # This prevents state leakage from one position to another.
    plugin = load_plugin(
        str(PLUGIN_PATH)
    )

    required_parameters = [
        "coordinate_system",
        "azimuth",
        "elevation",
        "distance",
    ]

    for parameter_name in required_parameters:
        if parameter_name not in plugin.parameters:
            fail(
                f"Required parameter missing: "
                f"{parameter_name}"
            )

    # Polar mode.
    set_parameter_raw(
        plugin,
        "coordinate_system",
        1.0,
    )

    # Static position under test.
    set_parameter_raw(
        plugin,
        "azimuth",
        raw_azimuth,
    )

    # 0° elevation according to the normalized
    # parameter interpretation established in T001-B.
    set_parameter_raw(
        plugin,
        "elevation",
        ELEVATION_RAW,
    )

    set_parameter_raw(
        plugin,
        "distance",
        DISTANCE_RAW,
    )

    # Process whole static stimulus through one plugin state.
    output_audio = plugin.process(
        input_audio,
        sample_rate=SAMPLE_RATE,
        buffer_size=BLOCK_SIZE,
        reset=True,
    )

    output_audio = np.asarray(
        output_audio,
        dtype=np.float32,
    )

    if output_audio.ndim != 2:
        fail(
            f"Unexpected output dimensions "
            f"for sample {blind_id}: "
            f"{output_audio.shape}"
        )

    if output_audio.shape[0] != 2:
        fail(
            f"Expected stereo output for "
            f"sample {blind_id}, got "
            f"{output_audio.shape[0]} channels."
        )

    finite = bool(
        np.all(
            np.isfinite(output_audio)
        )
    )

    peak = float(
        np.max(
            np.abs(output_audio)
        )
    )

    left_rms = rms(
        output_audio[0]
    )

    right_rms = rms(
        output_audio[1]
    )

    overall_rms = rms(
        output_audio
    )

    if right_rms > 0:
        ild_db = (
            20.0
            * math.log10(
                left_rms / right_rms
            )
        )
    else:
        ild_db = None

    clipping = peak >= 1.0

    output_path = (
        AUDIO_DIR
        / f"t001g_{blind_id}.wav"
    )

    write_wav_float_to_pcm16(
        output_path,
        output_audio,
        SAMPLE_RATE,
    )

    file_hash = sha256_file(
        output_path
    )

    render_records.append(
        {
            "blind_id":
                blind_id,

            "raw_azimuth":
                raw_azimuth,

            "output_file":
                str(
                    output_path.relative_to(
                        PROJECT_ROOT
                    )
                ),

            "sha256":
                file_hash,

            "peak":
                peak,

            "overall_rms":
                overall_rms,

            "left_rms":
                left_rms,

            "right_rms":
                right_rms,

            "ild_db_left_over_right":
                ild_db,

            "finite":
                finite,

            "clipping":
                clipping,
        }
    )

    print(
        f"  peak:       "
        f"{peak:.8f}"
    )

    print(
        f"  L RMS:      "
        f"{left_rms:.8f}"
    )

    print(
        f"  R RMS:      "
        f"{right_rms:.8f}"
    )

    if ild_db is not None:
        print(
            f"  ILD L/R:    "
            f"{ild_db:+.4f} dB"
        )

    print(
        f"  finite:     "
        f"{pass_fail(finite)}"
    )

    print(
        f"  no clipping:"
        f" {pass_fail(not clipping)}"
    )


# ============================================================
# OBJECTIVE VALIDATION
# ============================================================

all_files_exist = all(
    (
        PROJECT_ROOT
        / record["output_file"]
    ).is_file()
    for record in render_records
)

all_finite = all(
    record["finite"]
    for record in render_records
)

no_clipping_all = all(
    not record["clipping"]
    for record in render_records
)

all_non_silent = all(
    record["overall_rms"] > 1e-6
    for record in render_records
)

unique_hashes = len(
    {
        record["sha256"]
        for record in render_records
    }
)

all_outputs_distinct = (
    unique_hashes
    == len(render_records)
)

validations = {
    "eight_audio_files_created":
        all_files_exist,

    "all_outputs_finite":
        all_finite,

    "all_outputs_non_silent":
        all_non_silent,

    "no_clipping":
        no_clipping_all,

    "all_eight_outputs_distinct":
        all_outputs_distinct,
}


# ============================================================
# BLIND LISTENING SHEET
# ============================================================

blind_order = [
    record["blind_id"]
    for record in render_records
]

listening_sheet = {
    "test_id":
        "T001-G",

    "purpose":
        "Blind perceptual azimuth calibration",

    "instructions": [
        (
            "Do not inspect "
            "t001g_calibration_key.json "
            "before completing the listening test."
        ),
        (
            "Use the same headphones, orientation, "
            "volume and listening environment for "
            "all samples."
        ),
        (
            "Do not use speaker playback. "
            "Use headphones."
        ),
        (
            "For each file, identify the perceived "
            "direction without consulting the "
            "expected software position."
        ),
    ],

    "allowed_responses": [
        "FRONT",
        "FRONT_RIGHT",
        "RIGHT",
        "BACK_RIGHT",
        "BACK",
        "BACK_LEFT",
        "LEFT",
        "FRONT_LEFT",
        "AMBIGUOUS",
    ],

    "presentation_order":
        blind_order,

    "listener_1": {
        blind_id: {
            "perceived_direction": None,
            "confidence_0_to_5": None,
            "notes": None,
        }
        for blind_id in blind_order
    },

    "listener_2": {
        blind_id: {
            "perceived_direction": None,
            "confidence_0_to_5": None,
            "notes": None,
        }
        for blind_id in blind_order
    },
}

with LISTENING_SHEET_PATH.open(
    "w",
    encoding="utf-8",
) as file:
    json.dump(
        listening_sheet,
        file,
        indent=2,
        ensure_ascii=False,
    )


# ============================================================
# CALIBRATION KEY
# ============================================================

calibration_key = {
    "test_id":
        "T001-G",

    "warning":
        (
            "Do not inspect this mapping until "
            "blind listening is complete."
        ),

    "mapping": {
        record["blind_id"]:
            record["raw_azimuth"]
        for record in render_records
    },
}

with CALIBRATION_KEY_PATH.open(
    "w",
    encoding="utf-8",
) as file:
    json.dump(
        calibration_key,
        file,
        indent=2,
        ensure_ascii=False,
    )


# ============================================================
# RESULT MANIFEST
# ============================================================

objective_pass = all(
    validations.values()
)

results = {
    "test_id":
        "T001-G",

    "test_name":
        (
            "Blind Azimuth / Front-Back "
            "Perceptual Calibration"
        ),

    "timestamp_utc":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "objective_render_result":
        (
            "PASS"
            if objective_pass
            else "FAIL"
        ),

    "perceptual_result":
        "PENDING",

    "environment": {
        "python_version":
            platform.python_version(),

        "numpy_version":
            np.__version__,

        "sample_rate_hz":
            SAMPLE_RATE,

        "duration_seconds":
            DURATION_SECONDS,

        "block_size":
            BLOCK_SIZE,

        "seed":
            SEED,
    },

    "plugin": {
        "path":
            str(PLUGIN_PATH),

        "coordinate_system_raw":
            1.0,

        "elevation_raw":
            ELEVATION_RAW,

        "distance_raw":
            DISTANCE_RAW,
    },

    "stimulus": {
        "type":
            "deterministic_broadband_noise",

        "amplitude":
            SIGNAL_AMPLITUDE,

        "dual_mono":
            True,
    },

    "renders":
        render_records,

    "validations":
        validations,

    "blind_listening_sheet":
        str(
            LISTENING_SHEET_PATH.relative_to(
                PROJECT_ROOT
            )
        ),

    "calibration_key":
        str(
            CALIBRATION_KEY_PATH.relative_to(
                PROJECT_ROOT
            )
        ),
}

with RESULTS_PATH.open(
    "w",
    encoding="utf-8",
) as file:
    json.dump(
        results,
        file,
        indent=2,
        ensure_ascii=False,
    )


# ============================================================
# TERMINAL SUMMARY
# ============================================================

print()
print("-" * 76)
print("OBJECTIVE VALIDATIONS")
print("-" * 76)

for name, result in validations.items():
    print(
        f"{name:<45}"
        f"{pass_fail(result)}"
    )

print()
print("-" * 76)
print("BLIND LISTENING")
print("-" * 76)

print()
print("Listen in this order:")

for blind_id in blind_order:
    print(
        f"  t001g_{blind_id}.wav"
    )

print()
print(
    "DO NOT OPEN:"
)

print(
    CALIBRATION_KEY_PATH
)

print()
print(
    "until both listeners have completed "
    "their perceptual classifications."
)

print()
print("Listening sheet:")
print(LISTENING_SHEET_PATH)

print()
print("Results manifest:")
print(RESULTS_PATH)

print()

if objective_pass:
    print("=" * 76)
    print(
        "T001-G OBJECTIVE RENDER RESULT: PASS"
    )
    print(
        "T001-G PERCEPTUAL RESULT: PENDING"
    )
    print("=" * 76)
else:
    print("=" * 76)
    print(
        "T001-G OBJECTIVE RENDER RESULT: FAIL"
    )
    print("=" * 76)

    raise SystemExit(1)
