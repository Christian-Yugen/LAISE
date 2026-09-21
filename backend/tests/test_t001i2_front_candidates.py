"""
LAISE — T001-I2
Perceptual FRONT Candidate Construction

Purpose
-------
Construct several acoustically different candidates for a geometrically
identical FRONT source:

    azimuth  = 0 degrees
    elevation = 0 degrees
    distance = 3.0 m

The purpose is to determine whether dearVR acoustic/environmental cues
can break the FRONT/BACK perceptual ambiguity observed in T001-C/D/F/G.

One BACK control is included.

IMPORTANT
---------
The output filenames are blind.
Do NOT open the calibration key before listening.

Evidence
--------
evidence/T001/T001-I2/
    audio/
        t001i2_A.wav ...
        t001i2_F.wav

    t001i2_blind_listening_sheet.json
    t001i2_calibration_key.json
    t001i2_results.json
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
    / "T001-I2"
)

AUDIO_DIR = OUTPUT_DIR / "audio"

RESULTS_PATH = (
    OUTPUT_DIR
    / "t001i2_results.json"
)

KEY_PATH = (
    OUTPUT_DIR
    / "t001i2_calibration_key.json"
)

LISTENING_PATH = (
    OUTPUT_DIR
    / "t001i2_blind_listening_sheet.json"
)


# ============================================================
# HELPERS
# ============================================================

def fail(message: str):
    print()
    print("FAIL:", message)
    raise SystemExit(1)


def db_to_raw(db_value: float) -> float:
    """
    dearVR gain parameters:
    -96 dB -> raw 0
    +24 dB -> raw 1
    Linear normalized mapping.
    """
    db_value = max(-96.0, min(24.0, db_value))
    return (db_value + 96.0) / 120.0


def distance_to_raw(distance_m: float) -> float:
    """
    dearVR exposes 300 discrete values:
    0.1 m ... 30.0 m.

    Convert desired distance to normalized discrete index.
    """
    distance_m = max(0.1, min(30.0, distance_m))

    index = round(
        (distance_m - 0.1) / 0.1
    )

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
    parameter = plugin.parameters[name]

    try:
        values = parameter.valid_values
        if values is None:
            return None
        return list(values)
    except Exception:
        return None


def set_discrete_by_text(
    plugin,
    name: str,
    desired_text: str,
):
    """
    Find the normalized raw position corresponding to an exposed
    discrete textual value.

    This avoids guessing the raw value for Virtual Acoustics.
    """

    values = get_valid_values(plugin, name)

    if not values:
        fail(
            f"No valid_values exposed for {name}"
        )

    normalized = [
        str(v).strip()
        for v in values
    ]

    if desired_text not in normalized:
        fail(
            f"{desired_text!r} not available for {name}. "
            f"Available values include: {normalized[:10]}"
        )

    index = normalized.index(desired_text)

    if len(normalized) == 1:
        raw = 0.0
    else:
        raw = index / (len(normalized) - 1)

    set_raw(
        plugin,
        name,
        raw,
    )

    return raw


def write_wav(
    path: Path,
    audio: np.ndarray,
    sample_rate: int,
):
    """
    audio expected shape:
        (channels, samples)
    """

    audio = np.asarray(
        audio,
        dtype=np.float32,
    )

    audio = np.clip(
        audio,
        -1.0,
        1.0,
    )

    pcm = (
        audio.T * 32767.0
    ).astype(np.int16)

    with wave.open(
        str(path),
        "wb",
    ) as wav_file:

        wav_file.setnchannels(
            audio.shape[0]
        )

        wav_file.setsampwidth(2)

        wav_file.setframerate(
            sample_rate
        )

        wav_file.writeframes(
            pcm.tobytes()
        )


def sha256_file(path: Path) -> str:
    sha = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            sha.update(chunk)

    return sha.hexdigest()


def calculate_metrics(audio: np.ndarray):
    left = audio[0]
    right = audio[1]

    peak = float(
        np.max(
            np.abs(audio)
        )
    )

    left_rms = float(
        np.sqrt(
            np.mean(
                np.square(left)
            )
        )
    )

    right_rms = float(
        np.sqrt(
            np.mean(
                np.square(right)
            )
        )
    )

    overall_rms = float(
        np.sqrt(
            np.mean(
                np.square(audio)
            )
        )
    )

    epsilon = 1e-12

    ild_db = float(
        20.0
        * math.log10(
            (left_rms + epsilon)
            /
            (right_rms + epsilon)
        )
    )

    correlation = float(
        np.corrcoef(
            left,
            right,
        )[0, 1]
    )

    return {
        "peak": peak,
        "overall_rms": overall_rms,
        "left_rms": left_rms,
        "right_rms": right_rms,
        "ild_db": ild_db,
        "lr_correlation": correlation,
        "finite": bool(
            np.all(
                np.isfinite(audio)
            )
        ),
        "no_clipping": bool(
            peak < 1.0
        ),
    }


# ============================================================
# STIMULUS
# ============================================================

def create_test_signal():
    """
    Deterministic broadband stimulus.

    Same signal is used for every candidate.
    """

    sample_count = int(
        SAMPLE_RATE
        * DURATION_SECONDS
    )

    rng = np.random.default_rng(
        SEED
    )

    noise = rng.normal(
        0.0,
        1.0,
        sample_count,
    ).astype(np.float32)

    # Gentle normalization.
    noise /= max(
        np.max(np.abs(noise)),
        1e-12,
    )

    noise *= AMPLITUDE

    # Dual mono.
    return np.vstack(
        [
            noise,
            noise,
        ]
    ).astype(np.float32)


# ============================================================
# BASE SPATIAL STATE
# ============================================================

def configure_geometry(
    plugin,
    azimuth_deg: float,
):
    # Polar
    set_raw(
        plugin,
        "coordinate_system",
        1.0,
    )

    set_raw(
        plugin,
        "azimuth",
        azimuth_to_raw(
            azimuth_deg
        ),
    )

    set_raw(
        plugin,
        "elevation",
        elevation_to_raw(
            0.0
        ),
    )

    set_raw(
        plugin,
        "distance",
        distance_to_raw(
            3.0
        ),
    )

    # No occlusion.
    set_raw(
        plugin,
        "occlusion",
        0.0,
    )

    # Keep performance mode disabled.
    set_raw(
        plugin,
        "performance_mode",
        0.0,
    )


# ============================================================
# CANDIDATES
# ============================================================

CANDIDATES = [
    {
        "id": "FRONT_DIRECT",
        "direction": "FRONT",
        "azimuth_deg": 0.0,
        "virtual_acoustics":
            "DirectSignal",
        "reflection": False,
        "reverb": False,
        "reflection_gain_db": None,
        "description":
            "Pure direct binaural FRONT control.",
    },

    {
        "id": "FRONT_HALL_DEFAULT",
        "direction": "FRONT",
        "azimuth_deg": 0.0,
        "virtual_acoustics":
            "MediumRecordingHall",
        "reflection": True,
        "reverb": True,
        "reflection_gain_db": None,
        "description":
            "Current MediumRecordingHall-style FRONT.",
    },

    {
        "id": "FRONT_REFLECTION_ONLY",
        "direction": "FRONT",
        "azimuth_deg": 0.0,
        "virtual_acoustics":
            "MediumRecordingHall",
        "reflection": True,
        "reverb": False,
        "reflection_gain_db": None,
        "description":
            "FRONT with early reflections but no late reverb.",
    },

    {
        "id": "FRONT_REFLECTION_REDUCED",
        "direction": "FRONT",
        "azimuth_deg": 0.0,
        "virtual_acoustics":
            "MediumRecordingHall",
        "reflection": True,
        "reverb": False,
        "reflection_gain_db": -12.0,
        "description":
            "FRONT with lower-level early reflections.",
    },

    {
        "id": "FRONT_CLOSE_DIRECT",
        "direction": "FRONT",
        "azimuth_deg": 0.0,
        "virtual_acoustics":
            "DirectSignal",
        "reflection": False,
        "reverb": False,
        "reflection_gain_db": None,
        "distance_m": 1.0,
        "description":
            "Closer direct FRONT at 1 metre.",
    },

    {
        "id": "BACK_DIRECT_CONTROL",
        "direction": "BACK",
        "azimuth_deg": 180.0,
        "virtual_acoustics":
            "DirectSignal",
        "reflection": False,
        "reverb": False,
        "reflection_gain_db": None,
        "description":
            "Pure direct BACK control.",
    },
]


# ============================================================
# START
# ============================================================

print()
print("=" * 78)
print("LAISE — T001-I2")
print("Perceptual FRONT Candidate Construction")
print("=" * 78)

print()
print("Python:")
print(platform.python_version())

print()
print("Pedalboard:")
print(pedalboard.__version__)

print()
print("Plugin:")
print(PLUGIN_PATH)


# ============================================================
# PRECHECK
# ============================================================

print()
print("-" * 78)
print("PRECHECK")
print("-" * 78)

if not PLUGIN_PATH.is_file():
    fail(
        f"Plugin not found:\n{PLUGIN_PATH}"
    )

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

AUDIO_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

print("dearvr_plugin_exists                    PASS")


# ============================================================
# INPUT
# ============================================================

input_audio = create_test_signal()

print()
print("-" * 78)
print("INPUT STIMULUS")
print("-" * 78)

print(
    "Shape:            ",
    input_audio.shape,
)

print(
    "Peak:             ",
    f"{np.max(np.abs(input_audio)):.8f}",
)

print(
    "RMS:              ",
    f"{np.sqrt(np.mean(np.square(input_audio))):.8f}",
)


# ============================================================
# BLIND ASSIGNMENT
# ============================================================

blind_ids = list(
    "ABCDEF"
)

assignment_rng = random.Random(
    SEED + 200
)

shuffled_candidates = (
    CANDIDATES.copy()
)

assignment_rng.shuffle(
    shuffled_candidates
)

blind_mapping = dict(
    zip(
        blind_ids,
        shuffled_candidates,
    )
)


# ============================================================
# RENDER
# ============================================================

render_records = []

print()
print("-" * 78)
print("RENDERING BLIND CANDIDATES")
print("-" * 78)

for blind_id in blind_ids:

    candidate = blind_mapping[
        blind_id
    ]

    print()
    print(
        f"Rendering blind candidate "
        f"{blind_id}"
    )

    plugin = load_plugin(
        str(PLUGIN_PATH)
    )

    configure_geometry(
        plugin,
        candidate[
            "azimuth_deg"
        ],
    )

    # Optional distance override.
    distance_m = candidate.get(
        "distance_m",
        3.0,
    )

    set_raw(
        plugin,
        "distance",
        distance_to_raw(
            distance_m
        ),
    )

    # Acoustic environment.
    acoustic_raw = (
        set_discrete_by_text(
            plugin,
            "virtual_acoustics",
            candidate[
                "virtual_acoustics"
            ],
        )
    )

    set_raw(
        plugin,
        "reflection",
        1.0
        if candidate[
            "reflection"
        ]
        else 0.0,
    )

    set_raw(
        plugin,
        "reverb",
        1.0
        if candidate[
            "reverb"
        ]
        else 0.0,
    )

    if (
        candidate[
            "reflection_gain_db"
        ]
        is not None
    ):
        set_raw(
            plugin,
            "reflection_gain",
            db_to_raw(
                candidate[
                    "reflection_gain_db"
                ]
            ),
        )

    output = plugin.process(
        input_audio,
        sample_rate=SAMPLE_RATE,
        buffer_size=BUFFER_SIZE,
        reset=True,
    )

    output = np.asarray(
        output,
        dtype=np.float32,
    )

    if (
        output.ndim != 2
        or output.shape[0] != 2
    ):
        fail(
            f"{blind_id}: expected stereo "
            f"output, got {output.shape}"
        )

    metrics = calculate_metrics(
        output
    )

    wav_path = (
        AUDIO_DIR
        / f"t001i2_{blind_id}.wav"
    )

    write_wav(
        wav_path,
        output,
        SAMPLE_RATE,
    )

    sha = sha256_file(
        wav_path
    )

    record = {
        "blind_id":
            blind_id,

        "wav":
            str(wav_path),

        "sha256":
            sha,

        "metrics":
            metrics,

        "observed_plugin_state": {
            "coordinate_system":
                get_repr(
                    plugin,
                    "coordinate_system",
                ),

            "azimuth":
                get_repr(
                    plugin,
                    "azimuth",
                ),

            "elevation":
                get_repr(
                    plugin,
                    "elevation",
                ),

            "distance":
                get_repr(
                    plugin,
                    "distance",
                ),

            "virtual_acoustics":
                get_repr(
                    plugin,
                    "virtual_acoustics",
                ),

            "reflection":
                get_repr(
                    plugin,
                    "reflection",
                ),

            "reverb":
                get_repr(
                    plugin,
                    "reverb",
                ),

            "reflection_gain":
                get_repr(
                    plugin,
                    "reflection_gain",
                ),
        },

        "virtual_acoustics_raw":
            acoustic_raw,
    }

    render_records.append(
        record
    )

    print(
        "  peak:       ",
        f"{metrics['peak']:.8f}",
    )

    print(
        "  L RMS:      ",
        f"{metrics['left_rms']:.8f}",
    )

    print(
        "  R RMS:      ",
        f"{metrics['right_rms']:.8f}",
    )

    print(
        "  ILD L/R:    ",
        f"{metrics['ild_db']:+.4f} dB",
    )

    print(
        "  correlation:",
        f"{metrics['lr_correlation']:+.6f}",
    )

    print(
        "  finite:     ",
        "PASS"
        if metrics["finite"]
        else "FAIL",
    )

    print(
        "  no clipping:",
        "PASS"
        if metrics["no_clipping"]
        else "FAIL",
    )


# ============================================================
# VALIDATION
# ============================================================

print()
print("-" * 78)
print("OBJECTIVE VALIDATIONS")
print("-" * 78)

hashes = [
    record["sha256"]
    for record in render_records
]

validations = {
    "six_audio_files_created":
        len(render_records) == 6,

    "all_outputs_finite":
        all(
            record[
                "metrics"
            ][
                "finite"
            ]
            for record in render_records
        ),

    "all_outputs_non_silent":
        all(
            record[
                "metrics"
            ][
                "overall_rms"
            ] > 1e-7
            for record in render_records
        ),

    "no_clipping":
        all(
            record[
                "metrics"
            ][
                "no_clipping"
            ]
            for record in render_records
        ),

    "all_outputs_distinct":
        len(set(hashes)) == 6,
}

for name, result in validations.items():
    print(
        f"{name:<46}"
        f"{'PASS' if result else 'FAIL'}"
    )


# ============================================================
# BLIND KEY
# ============================================================

key = {}

for blind_id in blind_ids:

    candidate = blind_mapping[
        blind_id
    ]

    key[blind_id] = candidate


with KEY_PATH.open(
    "w",
    encoding="utf-8",
) as file:

    json.dump(
        {
            "WARNING":
                (
                    "DO NOT OPEN BEFORE "
                    "PERCEPTUAL LISTENING."
                ),

            "mapping":
                key,
        },
        file,
        indent=2,
        ensure_ascii=False,
    )


# ============================================================
# LISTENING SHEET
# ============================================================

listening_sheet = {
    "test_id":
        "T001-I2",

    "instructions": [
        (
            "Use headphones."
        ),
        (
            "Do not open the calibration key."
        ),
        (
            "Classify perceived direction, "
            "not which configuration you think it is."
        ),
        (
            "Do not force FRONT/BACK."
        ),
        (
            "AMBIGUOUS is a valid answer."
        ),
    ],

    "allowed_directions": [
        "FRONT",
        "FRONT_RIGHT",
        "RIGHT",
        "BACK_RIGHT",
        "BACK",
        "BACK_LEFT",
        "LEFT",
        "FRONT_LEFT",
        "ABOVE",
        "ABOVE_RIGHT",
        "ABOVE_LEFT",
        "INSIDE_HEAD",
        "AMBIGUOUS",
    ],

    "samples": [
        {
            "blind_id":
                blind_id,

            "file":
                (
                    f"audio/"
                    f"t001i2_{blind_id}.wav"
                ),

            "perceived_direction":
                None,

            "confidence_0_to_5":
                None,

            "externalization_0_to_5":
                None,

            "notes":
                None,
        }
        for blind_id in blind_ids
    ],
}

with LISTENING_PATH.open(
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
# RESULTS
# ============================================================

objective_pass = all(
    validations.values()
)

results = {
    "test_id":
        "T001-I2",

    "timestamp_utc":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "objective_result":
        (
            "PASS"
            if objective_pass
            else "FAIL"
        ),

    "perceptual_result":
        "PENDING",

    "environment": {
        "python":
            platform.python_version(),

        "pedalboard":
            pedalboard.__version__,
    },

    "render_records":
        render_records,

    "validations":
        validations,

    "blind_key_file":
        str(KEY_PATH),

    "listening_sheet_file":
        str(LISTENING_PATH),
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
# FINAL
# ============================================================

print()
print("-" * 78)
print("BLIND LISTENING")
print("-" * 78)

print()
print("Listen to:")

for blind_id in blind_ids:
    print(
        f"  t001i2_{blind_id}.wav"
    )

print()
print("DO NOT OPEN:")
print(KEY_PATH)

print()
print("Listening sheet:")
print(LISTENING_PATH)

print()
print("Results:")
print(RESULTS_PATH)

print()

if objective_pass:
    print("=" * 78)
    print("T001-I2 OBJECTIVE RESULT: PASS")
    print("T001-I2 PERCEPTUAL RESULT: PENDING")
    print("=" * 78)
else:
    print("=" * 78)
    print("T001-I2 OBJECTIVE RESULT: FAIL")
    print("=" * 78)
    raise SystemExit(1)
