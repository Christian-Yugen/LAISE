from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from music02_t005_common import (
    RATE,
    BLOCK,
    features,
    feature_distance,
    classify,
)

from music02_t005_render import render
from music02_t003 import key, distance_keys
from music02_preview import write24


ROOT = Path(r"C:\Projetos2026\LAISE")

PROJECT = (
    ROOT
    / "projects"
    / "tukana_02_a_mata_se_move"
)

OUT = (
    PROJECT
    / "experiments"
    / "TUK2_T005"
)

REPORT = (
    OUT
    / "reports"
    / "TUK2_T005B_dynamic_spatial_validation.json"
)

LIBRARY_PATH = (
    OUT
    / "reports"
    / "probe_library_native256.json"
)

RENDERS = (
    OUT
    / "renders"
    / "dynamic_validation"
)


def load(path):
    return json.loads(
        path.read_text(encoding="utf-8-sig")
    )


def dump(path, data):
    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


def pink_reference(seconds, seed):
    n = round(seconds * RATE)

    rng = np.random.default_rng(seed)

    noise = rng.normal(
        size=n
    )

    spectrum = np.fft.rfft(noise)

    freq = np.fft.rfftfreq(
        n,
        1 / RATE
    )

    spectrum *= np.where(
        (freq >= 60)
        & (freq <= 20000),

        1 / np.sqrt(
            np.maximum(freq, 60)
        ),

        0.0
    )

    mono = np.fft.irfft(
        spectrum,
        n=n
    )

    mono *= (
        0.025
        / max(
            np.max(np.abs(mono)),
            1e-12
        )
    )

    return np.vstack(
        (mono, mono)
    ).astype(np.float32)


def continuous_multitone(seconds):
    n = round(seconds * RATE)

    t = (
        np.arange(n, dtype=np.float64)
        / RATE
    )

    mono = (
        0.012 * np.sin(2*np.pi*320*t)
        + 0.008 * np.sin(2*np.pi*870*t)
        + 0.005 * np.sin(2*np.pi*2400*t)
    )

    return np.vstack(
        (mono, mono)
    ).astype(np.float32)


def fixed_source(
    az,
    el,
    distance=1.0
):
    return {
        "gain_db": 0.0,

        "home": {
            "distance_m": distance
        },

        "growth_reference_distance_m":
            distance,

        "keyframes": [
            key(
                0,
                az,
                el,
                "Static same-content reference"
            ),

            key(
                300,
                az,
                el,
                "Hold"
            ),
        ],

        "distance_keyframes":
            distance_keys(
                300,
                distance
            ),
    }


def same_content_static(
    raw,
    az,
    el,
    distance=1.0
):
    # Same method used by LAISE spatial QA:
    # preroll + content + latency tail.
    padded = np.concatenate(
        (
            np.zeros(
                (2, RATE),
                dtype=np.float32
            ),

            raw,

            np.zeros(
                (2, 512),
                dtype=np.float32
            ),
        ),
        axis=1
    )

    reference, _, _ = render(
        padded,
        fixed_source(
            az,
            el,
            distance
        )
    )

    count = raw.shape[1]

    return reference[
        :,
        RATE + 512:
        RATE + 512 + count
    ]


def wrap_angle(x):
    return (
        (np.asarray(x) + 180.0)
        % 360.0
    ) - 180.0


def circular_steps(wrapped):
    d = np.diff(wrapped)

    return (
        (d + 180.0)
        % 360.0
    ) - 180.0


def intended_linear_pose(
    time_seconds,
    t0,
    t1,
    a0,
    a1
):
    fraction = np.clip(
        (time_seconds - t0)
        / (t1 - t0),
        0.0,
        1.0
    )

    return (
        a0
        + fraction * (a1 - a0)
    )


def boundary_jump_metrics(
    audio,
    crossing_sample
):
    mono_jump = np.max(
        np.abs(
            np.diff(
                audio,
                axis=1
            )
        ),
        axis=0
    )

    boundaries = np.arange(
        BLOCK,
        audio.shape[1],
        BLOCK
    )

    boundary_jumps = np.array(
        [
            float(
                np.max(
                    np.abs(
                        audio[:, i]
                        -
                        audio[:, i-1]
                    )
                )
            )
            for i in boundaries
        ],
        dtype=np.float64
    )

    nearest_index = int(
        np.argmin(
            np.abs(
                boundaries
                - crossing_sample
            )
        )
    )

    crossing_boundary = int(
        boundaries[nearest_index]
    )

    crossing_jump = float(
        boundary_jumps[
            nearest_index
        ]
    )

    others = np.delete(
        boundary_jumps,
        nearest_index
    )

    other_p95 = float(
        np.percentile(
            others,
            95
        )
    )

    other_p99 = float(
        np.percentile(
            others,
            99
        )
    )

    global_p999 = float(
        np.percentile(
            mono_jump,
            99.9
        )
    )

    ratio_to_p99 = (
        crossing_jump
        / max(
            other_p99,
            1e-12
        )
    )

    ratio_to_global = (
        crossing_jump
        / max(
            global_p999,
            1e-12
        )
    )

    return {
        "nearest_crossing_boundary_sample":
            crossing_boundary,

        "distance_from_theoretical_crossing_samples":
            int(
                abs(
                    crossing_boundary
                    - crossing_sample
                )
            ),

        "crossing_boundary_jump":
            crossing_jump,

        "other_boundary_p95":
            other_p95,

        "other_boundary_p99":
            other_p99,

        "global_sample_delta_p999":
            global_p999,

        "crossing_vs_other_p99_ratio":
            ratio_to_p99,

        "crossing_vs_global_p999_ratio":
            ratio_to_global,
    }


if REPORT.exists():
    raise RuntimeError(
        f"Refusing overwrite: {REPORT}"
    )

if not LIBRARY_PATH.exists():
    raise RuntimeError(
        "TUK2-T005A probe library missing."
    )

library = load(
    LIBRARY_PATH
)

if (
    library[
        "validation"
    ]["status"]
    != "PASS"
):
    raise RuntimeError(
        "TUK2-T005A did not PASS."
    )


RENDERS.mkdir(
    parents=True,
    exist_ok=False
)


print()
print(
    "=================================================="
)
print(
    "TUK2-T005B - DYNAMIC SPATIAL VALIDATION"
)
print(
    "=================================================="
)


# ============================================================
# TEST 1 — CONTINUOUS 360 ORBIT
# ============================================================

print()
print(
    "[1/3] Continuous 360-degree orbit"
)

PRE = 1.0
ORBIT_DURATION = 24.0
TOTAL = 26.0

x = pink_reference(
    TOTAL,
    seed=5021
)

orbit_source = {
    "gain_db": 0.0,

    "home": {
        "distance_m": 1.0
    },

    "growth_reference_distance_m":
        1.0,

    "keyframes": [
        key(
            0.0,
            0,
            0,
            "Warm-up"
        ),

        key(
            PRE,
            0,
            0,
            "Orbit start"
        ),

        key(
            PRE + ORBIT_DURATION,
            360,
            0,
            "Orbit complete"
        ),

        key(
            TOTAL,
            360,
            0,
            "Final hold"
        ),
    ],

    "distance_keyframes":
        distance_keys(
            TOTAL,
            1.0
        ),
}

orbit_full, _, _ = render(
    x,
    orbit_source
)

orbit = orbit_full[
    :,
    round(PRE * RATE):
    round(
        (PRE + ORBIT_DURATION)
        * RATE
    )
]

orbit_path = (
    RENDERS
    / "TUK2_T005B_360_orbit.wav"
)

write24(
    orbit_path,
    orbit
)


# Control-grid geometry
times = (
    PRE
    + np.arange(
        0,
        orbit.shape[1],
        BLOCK
    )
    / RATE
)

unwrapped = intended_linear_pose(
    times,
    PRE,
    PRE + ORBIT_DURATION,
    0.0,
    360.0
)

wrapped = wrap_angle(
    unwrapped
)

steps = circular_steps(
    wrapped
)

wrapped_crossings = int(
    np.sum(
        np.abs(
            np.diff(wrapped)
        )
        > 180.0
    )
)

max_circular_step = float(
    np.max(
        np.abs(steps)
    )
)


# Same-content static comparisons every 30 degrees.
orbit_windows = []

expected_ild = []
actual_ild = []
paired_distances = []

for deg in range(
    0,
    361,
    30
):
    center = (
        deg / 360.0
        * ORBIT_DURATION
    )

    # Avoid edge clipping.
    center = min(
        max(center, 0.30),
        ORBIT_DURATION - 0.30
    )

    start = center - 0.25
    end = center + 0.25

    a = round(
        start * RATE
    )

    b = round(
        end * RATE
    )

    real = orbit[:, a:b]

    raw_start = round(
        (
            PRE + start
        )
        * RATE
    )

    raw_end = (
        raw_start
        + real.shape[1]
    )

    raw = x[
        :,
        raw_start:raw_end
    ]

    intended_az = (
        center
        / ORBIT_DURATION
        * 360.0
    )

    static = same_content_static(
        raw,
        intended_az,
        0.0,
        1.0
    )

    count = min(
        real.shape[1],
        static.shape[1]
    )

    real = real[:, :count]
    static = static[:, :count]

    f_real = features(real)
    f_static = features(static)

    distance = feature_distance(
        f_static,
        f_real,
        library
    )

    expected_ild.append(
        f_static[
            "ild_global_db"
        ]
    )

    actual_ild.append(
        f_real[
            "ild_global_db"
        ]
    )

    paired_distances.append(
        distance
    )

    orbit_windows.append({
        "nominal_azimuth_unwrapped_deg":
            float(intended_az),

        "nominal_azimuth_wrapped_deg":
            float(
                wrap_angle(
                    [intended_az]
                )[0]
            ),

        "paired_signature_distance":
            float(distance),

        "expected_ild_db":
            float(
                f_static[
                    "ild_global_db"
                ]
            ),

        "actual_ild_db":
            float(
                f_real[
                    "ild_global_db"
                ]
            ),

        "static_classification":
            classify(
                f_static,
                library
            ),

        "dynamic_classification":
            classify(
                f_real,
                library
            ),
    })


orbit_ild_corr = float(
    np.corrcoef(
        expected_ild,
        actual_ild
    )[0, 1]
)

orbit_median_distance = float(
    np.median(
        paired_distances
    )
)

orbit_pass = bool(
    wrapped_crossings == 1
    and max_circular_step < 1.0
    and orbit_ild_corr > 0.80
    and orbit_median_distance < 1.50
)


# ============================================================
# TEST 2 — EXPLICIT +180/-180 CROSSING
# ============================================================

print(
    "[2/3] Explicit +180/-180 crossing"
)

CROSS_PRE = 1.0
CROSS_DURATION = 4.0
CROSS_TOTAL = 6.0

tone = continuous_multitone(
    CROSS_TOTAL
)

cross_source = {
    "gain_db": 0.0,

    "home": {
        "distance_m": 1.0
    },

    "growth_reference_distance_m":
        1.0,

    "keyframes": [
        key(
            0.0,
            150,
            0,
            "Warm-up"
        ),

        key(
            CROSS_PRE,
            150,
            0,
            "Crossing start"
        ),

        key(
            CROSS_PRE
            + CROSS_DURATION,
            210,
            0,
            "Crossing end"
        ),

        key(
            CROSS_TOTAL,
            210,
            0,
            "Hold"
        ),
    ],

    "distance_keyframes":
        distance_keys(
            CROSS_TOTAL,
            1.0
        ),
}

cross_full, _, _ = render(
    tone,
    cross_source
)

cross = cross_full[
    :,
    round(CROSS_PRE * RATE):
    round(
        (
            CROSS_PRE
            + CROSS_DURATION
        )
        * RATE
    )
]

cross_path = (
    RENDERS
    / "TUK2_T005B_180_crossing.wav"
)

write24(
    cross_path,
    cross
)


cross_times = (
    CROSS_PRE
    + np.arange(
        0,
        cross.shape[1],
        BLOCK
    )
    / RATE
)

cross_unwrapped = (
    150.0
    + (
        cross_times
        - CROSS_PRE
    )
    / CROSS_DURATION
    * 60.0
)

cross_wrapped = wrap_angle(
    cross_unwrapped
)

cross_steps = circular_steps(
    cross_wrapped
)

cross_wrapped_count = int(
    np.sum(
        np.abs(
            np.diff(
                cross_wrapped
            )
        )
        > 180
    )
)

cross_max_step = float(
    np.max(
        np.abs(
            cross_steps
        )
    )
)

# 180° occurs halfway through measured crossing.
theoretical_crossing_sample = round(
    (
        CROSS_DURATION
        / 2.0
    )
    * RATE
)

jump = boundary_jump_metrics(
    cross,
    theoretical_crossing_sample
)

cross_pass = bool(
    cross_wrapped_count == 1
    and cross_max_step < 1.0
    and jump[
        "crossing_vs_other_p99_ratio"
    ] < 3.0
    and jump[
        "crossing_vs_global_p999_ratio"
    ] < 3.0
)


# ============================================================
# TEST 3 — DYNAMIC ELEVATION SWEEP
# ============================================================

print(
    "[3/3] Dynamic elevation sweep"
)

ELEVATIONS = [
    -45,
    -20,
    0,
    20,
    45,
    60,
]

E_PRE = 1.0
STEP_SECONDS = 2.0
E_TOTAL = (
    E_PRE
    + STEP_SECONDS
    * (len(ELEVATIONS) - 1)
    + 1.0
)

e_audio = pink_reference(
    E_TOTAL,
    seed=5022
)

e_keys = [
    key(
        0.0,
        -60,
        ELEVATIONS[0],
        "Warm-up"
    )
]

for i, el in enumerate(
    ELEVATIONS
):
    e_keys.append(
        key(
            E_PRE
            + i * STEP_SECONDS,
            -60,
            el,
            f"Elevation {el}"
        )
    )

e_keys.append(
    key(
        E_TOTAL,
        -60,
        ELEVATIONS[-1],
        "Hold"
    )
)

e_source = {
    "gain_db": 0.0,

    "home": {
        "distance_m": 1.0
    },

    "growth_reference_distance_m":
        1.0,

    "keyframes":
        e_keys,

    "distance_keyframes":
        distance_keys(
            E_TOTAL,
            1.0
        ),
}

e_full, _, _ = render(
    e_audio,
    e_source
)

e_path = (
    RENDERS
    / "TUK2_T005B_elevation_sweep.wav"
)

write24(
    e_path,
    e_full
)


e_windows = []
e_distances = []
e_band_matches = []

for i, el in enumerate(
    ELEVATIONS
):
    center = (
        E_PRE
        + i * STEP_SECONDS
    )

    center = min(
        max(
            center,
            E_PRE + 0.30
        ),
        E_TOTAL - 0.30
    )

    start = center - 0.25
    end = center + 0.25

    a = round(
        start * RATE
    )

    b = round(
        end * RATE
    )

    real = e_full[:, a:b]
    raw = e_audio[:, a:b]

    static = same_content_static(
        raw,
        -60,
        el,
        1.0
    )

    count = min(
        real.shape[1],
        static.shape[1]
    )

    real = real[:, :count]
    static = static[:, :count]

    fr = features(real)
    fs = features(static)

    distance = feature_distance(
        fs,
        fr,
        library
    )

    cr = classify(
        fr,
        library
    )

    cs = classify(
        fs,
        library
    )

    band_match = (
        cr[
            "elevation_band"
        ]
        ==
        cs[
            "elevation_band"
        ]
    )

    e_distances.append(
        distance
    )

    e_band_matches.append(
        band_match
    )

    e_windows.append({
        "target_elevation_deg":
            el,

        "paired_signature_distance":
            float(distance),

        "dynamic_classification":
            cr,

        "static_classification":
            cs,

        "elevation_band_match":
            bool(band_match),
    })


e_median_distance = float(
    np.median(
        e_distances
    )
)

e_band_accuracy = float(
    np.mean(
        e_band_matches
    )
)

elevation_pass = bool(
    e_median_distance < 1.50
    and e_band_accuracy >= 0.80
)


# ============================================================
# FINAL DECISION
# ============================================================

status = (
    "PASS"
    if (
        orbit_pass
        and cross_pass
        and elevation_pass
    )
    else "FAIL"
)


report = {
    "schema":
        "LAISE TUK2 Dynamic Spatial Validation v1.0",

    "project":
        "tukana_02_a_mata_se_move",

    "test_id":
        "TUK2-T005B",

    "status":
        status,

    "reference_library":
        str(LIBRARY_PATH),

    "continuous_360": {
        "status":
            "PASS"
            if orbit_pass
            else "FAIL",

        "duration_seconds":
            ORBIT_DURATION,

        "unwrapped_range_deg":
            [
                float(
                    np.min(
                        unwrapped
                    )
                ),
                float(
                    np.max(
                        unwrapped
                    )
                ),
            ],

        "wrapped_crossings":
            wrapped_crossings,

        "max_circular_step_deg":
            max_circular_step,

        "ild_progression_correlation":
            orbit_ild_corr,

        "median_paired_signature_distance":
            orbit_median_distance,

        "windows":
            orbit_windows,

        "render":
            str(
                orbit_path
            ),
    },

    "plus_minus_180_crossing": {
        "status":
            "PASS"
            if cross_pass
            else "FAIL",

        "trajectory_unwrapped_deg":
            [
                150,
                210
            ],

        "wrapped_crossings":
            cross_wrapped_count,

        "max_circular_step_deg":
            cross_max_step,

        "boundary_continuity":
            jump,

        "render":
            str(
                cross_path
            ),
    },

    "elevation_sweep": {
        "status":
            "PASS"
            if elevation_pass
            else "FAIL",

        "tested_elevations_deg":
            ELEVATIONS,

        "median_paired_signature_distance":
            e_median_distance,

        "dynamic_vs_static_elevation_band_accuracy":
            e_band_accuracy,

        "windows":
            e_windows,

        "render":
            str(
                e_path
            ),
    },

    "gates": {
        "orbit_ild_correlation_min":
            0.80,

        "orbit_signature_distance_max":
            1.50,

        "max_circular_step_deg":
            1.0,

        "crossing_artifact_ratio_max":
            3.0,

        "elevation_band_accuracy_min":
            0.80,

        "elevation_signature_distance_max":
            1.50,
    },

    "limits": [
        (
            "These are technical controlled-signal "
            "measurements, not universal human "
            "localization probabilities."
        ),

        (
            "A successful technical 360 orbit does "
            "not require a full musical stem orbit "
            "in the final arrangement."
        ),

        (
            "Musical motion remains subordinate to "
            "clarity, transient preservation and "
            "lead-vocal audibility."
        ),
    ],
}


dump(
    REPORT,
    report
)


print()
print(
    "=================================================="
)
print(
    "TUK2-T005B RESULT"
)
print(
    "=================================================="
)

print()
print(
    "360 CONTINUOUS:"
)

print(
    f"Status                  : "
    f"{'PASS' if orbit_pass else 'FAIL'}"
)

print(
    f"Wrapped crossings       : "
    f"{wrapped_crossings}"
)

print(
    f"Max circular step       : "
    f"{max_circular_step:.4f} deg"
)

print(
    f"ILD progression corr    : "
    f"{orbit_ild_corr:.4f}"
)

print(
    f"Median signature dist   : "
    f"{orbit_median_distance:.4f}"
)


print()
print(
    "+/-180 CROSSING:"
)

print(
    f"Status                  : "
    f"{'PASS' if cross_pass else 'FAIL'}"
)

print(
    f"Wrapped crossings       : "
    f"{cross_wrapped_count}"
)

print(
    f"Max circular step       : "
    f"{cross_max_step:.4f} deg"
)

print(
    f"Cross/P99 boundary      : "
    f"{jump['crossing_vs_other_p99_ratio']:.4f}"
)

print(
    f"Cross/global P99.9      : "
    f"{jump['crossing_vs_global_p999_ratio']:.4f}"
)


print()
print(
    "ELEVATION:"
)

print(
    f"Status                  : "
    f"{'PASS' if elevation_pass else 'FAIL'}"
)

print(
    f"Band agreement          : "
    f"{e_band_accuracy:.4f}"
)

print(
    f"Median signature dist   : "
    f"{e_median_distance:.4f}"
)


print()
print(
    "FINAL:"
)

print(
    f"TUK2-T005B: {status}"
)

print()
print(
    "Report:"
)

print(REPORT)


if status != "PASS":
    raise RuntimeError(
        "TUK2-T005B failed. "
        "Do not generate musical candidates yet."
    )

