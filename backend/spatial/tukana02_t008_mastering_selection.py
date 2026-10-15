from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np


ROOT = Path(r"C:\Projetos2026\LAISE")

sys.path.insert(
    0,
    str(
        ROOT
        / "backend"
        / "mastering"
    )
)


from music02_t005_common import (
    RATE,
    features,
    feature_distance,
    transient_proxy,
    envelope,
    rms,
    read_any,
    write24,
    file_metrics,
    ff,
    _sha256,
)

from tukana_transient_refinement import (
    render_loudnorm,
    drum_attack_frames,
    transient_analysis,
)


PROJECT = (
    ROOT
    / "projects"
    / "tukana_02_a_mata_se_move"
)

T007_REPORT = (
    PROJECT
    / "experiments"
    / "TUK2_T007"
    / "reports"
    / "TUK2_T007_final_spatial_qa.json"
)

LIBRARY_PATH = (
    PROJECT
    / "experiments"
    / "TUK2_T005"
    / "reports"
    / "probe_library_native256.json"
)

OUT = (
    PROJECT
    / "experiments"
    / "TUK2_T008"
)

MASTERING = (
    OUT
    / "mastering"
)

CODEC = (
    MASTERING
    / "codec"
)

REPORTS = (
    OUT
    / "reports"
)

FINAL = (
    OUT
    / "selected"
)

REPORT_PATH = (
    REPORTS
    / "TUK2_T008_mastering_selection.json"
)


FRAMES = 15_840_000
DURATION = FRAMES / RATE


MASTER_WEIGHTS = {
    "spatial_integrity":
        0.30,

    "clarity":
        0.20,

    "transients":
        0.20,

    "loudness":
        0.10,

    "true_peak":
        0.08,

    "dynamics":
        0.07,

    "codec":
        0.05,
}


def load(path):

    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def dump(path, data):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


def db(value):

    return float(
        20.0
        * np.log10(
            max(
                float(value),
                1e-15
            )
        )
    )


# ============================================================
# SPATIAL SIGNATURE INTEGRITY
# ============================================================

def signature_integrity(
    source,
    processed,
    library,
    step_seconds=2.0,
):

    windows = []


    for time in np.arange(
        0.0,
        DURATION - 1.0,
        step_seconds
    ):

        first = round(
            time * RATE
        )

        last = (
            first + RATE
        )


        dry = source[
            :,
            first:last
        ]

        wet = processed[
            :,
            first:last
        ]


        if rms(dry) < 1e-6:
            continue


        a = features(dry)
        b = features(wet)


        distance = feature_distance(
            a,
            b,
            library
        )


        windows.append({
            "time_seconds":
                float(time),

            "feature_distance":
                float(distance),

            "ild_delta_db":
                float(
                    b[
                        "ild_global_db"
                    ]
                    -
                    a[
                        "ild_global_db"
                    ]
                ),

            "itd_delta_us":
                float(
                    b[
                        "itd_us"
                    ]
                    -
                    a[
                        "itd_us"
                    ]
                ),

            "correlation_delta":
                float(
                    b[
                        "cross_correlation_lr"
                    ]
                    -
                    a[
                        "cross_correlation_lr"
                    ]
                ),

            "spectral_contrast_mean_delta_db":
                float(
                    np.mean(
                        np.abs(
                            np.asarray(
                                a[
                                    "spectral_difference_lr_db"
                                ]
                            )
                            -
                            np.asarray(
                                b[
                                    "spectral_difference_lr_db"
                                ]
                            )
                        )
                    )
                ),
        })


    if not windows:

        raise RuntimeError(
            "No active windows for spatial integrity."
        )


    distances = np.asarray(
        [
            x[
                "feature_distance"
            ]
            for x in windows
        ],
        dtype=np.float64
    )


    mean_distance = float(
        np.mean(
            distances
        )
    )


    score = float(
        100.0
        * np.exp(
            -mean_distance
            / 0.25
        )
    )


    return {
        "score":
            score,

        "mean_distance":
            mean_distance,

        "p95_distance":
            float(
                np.percentile(
                    distances,
                    95
                )
            ),

        "windows":
            windows,

        "definition":
            (
                "Gain-invariant binaural mix-feature "
                "fidelity relative to the approved "
                "TUK2-T007 spatial master."
            ),
    }


# ============================================================
# SPECTRAL CODEC DELTA
# ============================================================

def spectral_distribution_delta(
    source,
    processed
):

    values = []


    for time in np.arange(
        0.0,
        DURATION - 1.0,
        4.0
    ):

        first = round(
            time * RATE
        )

        last = first + RATE


        a = source[
            :,
            first:last
        ]

        b = processed[
            :,
            first:last
        ]


        if rms(a) < 1e-6:
            continue


        fa = features(a)
        fb = features(b)


        da = np.asarray(
            fa[
                "band_distribution"
            ],
            dtype=np.float64
        )

        dband = np.asarray(
            fb[
                "band_distribution"
            ],
            dtype=np.float64
        )


        delta = float(
            np.mean(
                np.abs(
                    10.0
                    * np.log10(
                        (
                            dband
                            + 1e-20
                        )
                        /
                        (
                            da
                            + 1e-20
                        )
                    )
                )
            )
        )


        values.append(
            delta
        )


    if not values:

        return 0.0


    return float(
        np.mean(
            values
        )
    )


# ============================================================
# GAIN INTERVENTION PROXY
# ============================================================

def intervention(
    source,
    processed,
    target_gain_db
):

    a = envelope(
        source,
        480
    )

    b = envelope(
        processed,
        480
    )


    active = (
        a
        >
        max(
            float(
                a.max()
            )
            * 0.001,
            1e-8
        )
    )


    if not np.any(
        active
    ):

        return {
            "status":
                "NO_ACTIVE_WINDOWS"
        }


    actual = (
        20.0
        * np.log10(
            np.maximum(
                b[active],
                1e-15
            )
            /
            np.maximum(
                a[active],
                1e-15
            )
        )
    )


    deficit = np.maximum(
        target_gain_db
        - actual,
        0.0
    )


    return {
        "unconstrained_integrated_gain_db":
            float(
                target_gain_db
            ),

        "observed_gain_db": {
            "minimum":
                float(
                    np.min(
                        actual
                    )
                ),

            "median":
                float(
                    np.median(
                        actual
                    )
                ),

            "maximum":
                float(
                    np.max(
                        actual
                    )
                ),
        },

        "normalization_or_limiting_deficit_db": {
            "median":
                float(
                    np.median(
                        deficit
                    )
                ),

            "p95":
                float(
                    np.percentile(
                        deficit,
                        95
                    )
                ),

            "maximum":
                float(
                    np.max(
                        deficit
                    )
                ),
        },

        "fraction_active_windows_below_unconstrained_gain_by_05db":
            float(
                np.mean(
                    deficit
                    > 0.5
                )
            ),

        "caution":
            (
                "Gain deficit includes normalization "
                "behavior and must not be interpreted "
                "as a dedicated limiter GR trace."
            ),
    }


# ============================================================
# AAC 320 ROUND-TRIP
# ============================================================

def codec_test(
    master_path,
    label,
    master_audio,
    library
):

    aac = (
        CODEC
        / f"{label}_AAC_320k.m4a"
    )

    roundtrip = (
        CODEC
        / (
            f"{label}_AAC_320k_"
            f"roundtrip_PCM24.wav"
        )
    )


    if (
        aac.exists()
        or roundtrip.exists()
    ):

        raise RuntimeError(
            f"Codec artifact already exists: {label}"
        )


    ff([
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(
            master_path
        ),
        "-c:a",
        "aac",
        "-b:a",
        "320k",
        "-ar",
        str(
            RATE
        ),
        "-movflags",
        "+faststart",
        str(
            aac
        ),
    ])


    decoded = read_any(
        aac
    )


    if (
        decoded.shape[1]
        < FRAMES
    ):

        raise RuntimeError(
            f"AAC decode too short: {label}"
        )


    extra = (
        decoded.shape[1]
        - FRAMES
    )


    aligned = decoded[
        :,
        :FRAMES
    ]


    write24(
        roundtrip,
        aligned
    )


    metrics = file_metrics(
        roundtrip
    )


    spatial = signature_integrity(
        master_audio,
        aligned,
        library,
        step_seconds=4.0,
    )


    transient = transient_proxy(
        master_audio,
        aligned,
        latency_samples=0
    )


    spectral_delta = (
        spectral_distribution_delta(
            master_audio,
            aligned
        )
    )


    spectral_score = max(
        0.0,
        100.0
        - spectral_delta
        * 10.0
    )


    codec_score = float(
        0.60
        * spatial[
            "score"
        ]
        +
        0.30
        * transient[
            "score"
        ]
        +
        0.10
        * spectral_score
    )


    safety = bool(
        metrics[
            "signal"
        ][
            "finite"
        ]
        and
        metrics[
            "signal"
        ][
            "sample_peak"
        ]
        < 1.0
        and
        metrics[
            "loudness"
        ][
            "true_peak_dbtp"
        ]
        <= -1.0
    )


    return {
        "path":
            str(
                aac
            ),

        "sha256":
            _sha256(
                aac
            ),

        "requested_bitrate_bps":
            320000,

        "roundtrip":
            metrics,

        "decoded_frames_before_padding_removal":
            int(
                decoded.shape[1]
            ),

        "codec_end_padding_removed_frames":
            int(
                extra
            ),

        "aligned_frames":
            FRAMES,

        "spatial_integrity":
            spatial,

        "transients":
            transient,

        "spectral_distribution_mean_delta_db":
            spectral_delta,

        "safety_pass":
            safety,

        "codec_score":
            codec_score,
    }


# ============================================================
# PREREQUISITES
# ============================================================

for path in (
    T007_REPORT,
    LIBRARY_PATH,
):

    if not path.exists():

        raise RuntimeError(
            f"Missing prerequisite: {path}"
        )


if OUT.exists():

    raise RuntimeError(
        "TUK2-T008 namespace already exists. "
        "Preserving prior evidence."
    )


t007 = load(
    T007_REPORT
)

library = load(
    LIBRARY_PATH
)


if t007[
    "status"
] != "PASS":

    raise RuntimeError(
        "TUK2-T007 did not PASS."
    )


if not t007[
    "checks"
][
    "deterministic_pcm24_rerender"
]:

    raise RuntimeError(
        "T007 determinism gate did not PASS."
    )


source = Path(
    t007[
        "outputs"
    ][
        "final_binaural"
    ][
        "path"
    ]
)


source_expected_hash = (
    t007[
        "outputs"
    ][
        "final_binaural"
    ][
        "sha256"
    ]
)


if (
    _sha256(
        source
    )
    != source_expected_hash
):

    raise RuntimeError(
        "T007 spatial source hash changed."
    )


OUT.mkdir(
    parents=True,
    exist_ok=False
)

MASTERING.mkdir(
    parents=True,
    exist_ok=False
)

CODEC.mkdir(
    parents=True,
    exist_ok=False
)

REPORTS.mkdir(
    parents=True,
    exist_ok=False
)

FINAL.mkdir(
    parents=True,
    exist_ok=False
)


# ============================================================
# SOURCE
# ============================================================

source_audio = read_any(
    source
)


if source_audio.shape != (
    2,
    FRAMES
):

    raise RuntimeError(
        f"Unexpected source shape: "
        f"{source_audio.shape}"
    )


source_metrics = file_metrics(
    source
)


source_signal = (
    source_metrics[
        "signal"
    ]
)

source_ebu = (
    source_metrics[
        "loudness"
    ]
)


source_lufs = float(
    source_ebu[
        "integrated_lufs"
    ]
)

source_tp = float(
    source_ebu[
        "true_peak_dbtp"
    ]
)

source_lra = float(
    source_ebu[
        "loudness_range_lu"
    ]
)

source_crest = float(
    source_signal[
        "crest_factor_db"
    ]
)


# ============================================================
# PROGRAM-ADAPTIVE TARGET
# ============================================================

if (
    source_crest < 18.0
    and
    source_lra < 10.0
):

    target_i = -16.0

elif source_crest < 22.0:

    target_i = -17.0

else:

    target_i = -18.0


target_tp = -2.0


target_lra = float(
    np.clip(
        source_lra,
        7.0,
        14.0
    )
)


print()
print(
    "=================================================="
)
print(
    "TUK2-T008 - AUTOMATED MASTERING SELECTION"
)
print(
    "=================================================="
)

print()
print(
    "SOURCE:"
)

print(
    f"LUFS integrated : "
    f"{source_lufs:.2f}"
)

print(
    f"True peak       : "
    f"{source_tp:.2f} dBTP"
)

print(
    f"LRA             : "
    f"{source_lra:.2f} LU"
)

print(
    f"Crest           : "
    f"{source_crest:.2f} dB"
)


print()
print(
    "AUTOMATIC TARGET:"
)

print(
    f"Integrated LUFS : "
    f"{target_i:.2f}"
)

print(
    f"True peak       : "
    f"{target_tp:.2f} dBTP"
)

print(
    f"LRA reference   : "
    f"{target_lra:.2f} LU"
)


# ============================================================
# A — TRANSPARENT LINKED GAIN
# ============================================================

A = (
    MASTERING
    / "A_TRANSPARENT_PCM24_48k.wav"
)


transparent_gain = min(
    target_i
    - source_lufs,

    target_tp
    - source_tp,
)


ff([
    "ffmpeg",
    "-v",
    "error",
    "-i",
    str(
        source
    ),
    "-af",
    f"volume={transparent_gain:.8f}dB",
    "-ar",
    str(
        RATE
    ),
    "-c:a",
    "pcm_s24le",
    str(
        A
    ),
])


# ============================================================
# B — OPTIMIZED
# ============================================================

B = (
    MASTERING
    / "B_OPTIMIZED_PCM24_48k.wav"
)


b_first_pass = render_loudnorm(
    source,
    B,
    target_i,
    target_tp,
    target_lra,
)


# ============================================================
# DETERMINE C RELAXATION FROM B TRANSIENT EFFECT
# ============================================================

b_audio = read_any(
    B
)


b_transient_precheck = transient_proxy(
    source_audio,
    b_audio,
    latency_samples=0
)


attack_delta = (
    b_transient_precheck[
        "median_attack_crest_delta_db"
    ]
)


relaxation = (
    0.6
    if attack_delta < -0.5
    else 0.3
)


refined_target_i = (
    target_i
    - relaxation
)


# ============================================================
# C — REFINED
# ============================================================

C = (
    MASTERING
    / "C_REFINED_PCM24_48k.wav"
)


c_first_pass = render_loudnorm(
    source,
    C,
    refined_target_i,
    target_tp,
    target_lra,
)


print()
print(
    f"Transient delta B : "
    f"{attack_delta:+.3f} dB"
)

print(
    f"C relaxation      : "
    f"{relaxation:.1f} LU"
)

print(
    f"C target          : "
    f"{refined_target_i:.2f} LUFS"
)


# ============================================================
# ATTACK TIMING FROM APPROVED T007 STEMS
# ============================================================

attacks = {}


for role, count in (
    ("drums", 180),
    ("percussion", 120),
    ("brass", 100),
):

    stem_path = Path(
        t007[
            "source_reports"
        ][role][
            "delivery"
        ][
            "path"
        ]
    )


    stem_audio = read_any(
        stem_path
    )


    attacks[
        role
    ] = drum_attack_frames(
        stem_audio.T,
        count=count
    )


# ============================================================
# CANDIDATE QA
# ============================================================

paths = {
    "A_TRANSPARENT":
        A,

    "B_OPTIMIZED":
        B,

    "C_REFINED":
        C,
}


records = {}


for label, path in (
    paths.items()
):

    print()
    print(
        f"QA {label}..."
    )


    audio = read_any(
        path
    )


    if audio.shape != (
        2,
        FRAMES
    ):

        raise RuntimeError(
            f"{label}: frame mismatch "
            f"{audio.shape}"
        )


    metrics = file_metrics(
        path
    )


    spatial = signature_integrity(
        source_audio,
        audio,
        library,
    )


    transients = transient_proxy(
        source_audio,
        audio,
        latency_samples=0
    )


    timed = {
        role:
            transient_analysis(
                audio.T,
                indices
            )

        for role, indices
        in attacks.items()
    }


    timed_source = {
        role:
            transient_analysis(
                source_audio.T,
                indices
            )

        for role, indices
        in attacks.items()
    }


    candidate_target = (
        refined_target_i
        if label
        == "C_REFINED"
        else target_i
    )


    target_gain_db = (
        candidate_target
        - source_lufs
    )


    gain_intervention = intervention(
        source_audio,
        audio,
        target_gain_db,
    )


    codec = codec_test(
        path,
        label,
        audio,
        library,
    )


    clarity_integrity = float(
        100.0
        * math.exp(
            -spatial[
                "mean_distance"
            ]
            / 0.5
        )
    )


    eligible_base = bool(
        metrics[
            "signal"
        ][
            "frames"
        ]
        == FRAMES

        and
        metrics[
            "signal"
        ][
            "finite"
        ]

        and
        metrics[
            "signal"
        ][
            "sample_peak"
        ]
        < 1.0

        and
        metrics[
            "loudness"
        ][
            "true_peak_dbtp"
        ]
        <= -1.5

        and
        codec[
            "safety_pass"
        ]
    )


    records[
        label
    ] = {
        **metrics,

        "spatial_integrity":
            spatial,

        "clarity_integrity":
            clarity_integrity,

        "transient_fidelity":
            transients,

        "role_timed_attacks":
            timed,

        "role_timed_source_attacks":
            timed_source,

        "gain_intervention":
            gain_intervention,

        "codec":
            codec,

        "eligible_base":
            eligible_base,
    }


# ============================================================
# C REFINEMENT GATE
# ============================================================

b = records[
    "B_OPTIMIZED"
]

c = records[
    "C_REFINED"
]


refinement_gate = {
    "spatial_integrity_not_worse":
        (
            c[
                "spatial_integrity"
            ][
                "score"
            ]
            >=
            b[
                "spatial_integrity"
            ][
                "score"
            ]
            - 0.10
        ),

    "transient_score_not_worse":
        (
            c[
                "transient_fidelity"
            ][
                "score"
            ]
            >=
            b[
                "transient_fidelity"
            ][
                "score"
            ]
            - 0.01
        ),

    "clarity_not_worse":
        (
            c[
                "clarity_integrity"
            ]
            >=
            b[
                "clarity_integrity"
            ]
            - 0.10
        ),

    "codec_spatial_not_worse":
        (
            c[
                "codec"
            ][
                "spatial_integrity"
            ][
                "score"
            ]
            >=
            b[
                "codec"
            ][
                "spatial_integrity"
            ][
                "score"
            ]
            - 0.20
        ),

    "safety":
        c[
            "eligible_base"
        ],
}


for label in (
    "A_TRANSPARENT",
    "B_OPTIMIZED",
):

    records[
        label
    ][
        "eligible"
    ] = records[
        label
    ][
        "eligible_base"
    ]


records[
    "C_REFINED"
][
    "eligible"
] = bool(
    c[
        "eligible_base"
    ]
    and
    all(
        refinement_gate.values()
    )
)


# ============================================================
# OBJECTIVE MASTER SCORE
# ============================================================

for label, record in (
    records.items()
):

    loudness_score = max(
        0.0,
        100.0
        -
        abs(
            record[
                "loudness"
            ][
                "integrated_lufs"
            ]
            -
            target_i
        )
        * 12.0
    )


    dynamics_score = max(
        0.0,
        100.0
        -
        abs(
            record[
                "signal"
            ][
                "crest_factor_db"
            ]
            -
            source_crest
        )
        * 5.0
    )


    true_peak_score = (
        100.0
        if record[
            "loudness"
        ][
            "true_peak_dbtp"
        ]
        <= -1.5
        else 0.0
    )


    components = {
        "spatial_integrity":
            float(
                record[
                    "spatial_integrity"
                ][
                    "score"
                ]
            ),

        "clarity":
            float(
                record[
                    "clarity_integrity"
                ]
            ),

        "transients":
            float(
                record[
                    "transient_fidelity"
                ][
                    "score"
                ]
            ),

        "loudness":
            float(
                loudness_score
            ),

        "true_peak":
            float(
                true_peak_score
            ),

        "dynamics":
            float(
                dynamics_score
            ),

        "codec":
            float(
                record[
                    "codec"
                ][
                    "codec_score"
                ]
            ),
    }


    master_score = float(
        sum(
            components[key]
            * MASTER_WEIGHTS[
                key
            ]

            for key
            in MASTER_WEIGHTS
        )
    )


    record[
        "master_score_components"
    ] = components


    record[
        "master_score"
    ] = master_score


# ============================================================
# SELECT
# ============================================================

eligible = [
    label

    for label, record
    in records.items()

    if record[
        "eligible"
    ]
]


if not eligible:

    raise RuntimeError(
        "No technically eligible master candidate."
    )


winner = max(
    eligible,

    key=lambda label:
        records[
            label
        ][
            "master_score"
        ]
)


selected = records[
    winner
]


# ============================================================
# FINAL SELECTED ARTIFACTS
# ============================================================

final_wav = (
    FINAL
    / "TUKANA02_SELECTED_MASTER_PCM24_48k.wav"
)

final_aac = (
    FINAL
    / "TUKANA02_SELECTED_MASTER_AAC_320k.m4a"
)


shutil.copyfile(
    Path(
        selected[
            "path"
        ]
    ),
    final_wav
)


shutil.copyfile(
    Path(
        selected[
            "codec"
        ][
            "path"
        ]
    ),
    final_aac
)


# ============================================================
# CHECKS
# ============================================================

checks = {
    "T007_spatial_QA_passed":
        True,

    "T007_spatial_source_unchanged":
        (
            _sha256(
                source
            )
            ==
            source_expected_hash
        ),

    "selected_exact_frames":
        (
            selected[
                "signal"
            ][
                "frames"
            ]
            ==
            FRAMES
        ),

    "selected_finite":
        selected[
            "signal"
        ][
            "finite"
        ],

    "selected_no_sample_clipping":
        (
            selected[
                "signal"
            ][
                "sample_peak"
            ]
            < 1.0
        ),

    "selected_true_peak_safe":
        (
            selected[
                "loudness"
            ][
                "true_peak_dbtp"
            ]
            <= -1.5
        ),

    "selected_codec_safe":
        selected[
            "codec"
        ][
            "safety_pass"
        ],

    "selected_spatial_integrity":
        (
            selected[
                "spatial_integrity"
            ][
                "score"
            ]
            >= 95.0
        ),

    "selected_codec_spatial_signature":
        (
            selected[
                "codec"
            ][
                "spatial_integrity"
            ][
                "score"
            ]
            >= 90.0
        ),

    "no_widening":
        True,

    "no_mid_side":
        True,

    "no_channel_independent_gain":
        True,

    "no_respatialization":
        True,

    "no_EQ_added":
        True,
}


status = (
    "PASS"
    if all(
        checks.values()
    )
    else "FAIL"
)


# ============================================================
# REPORT
# ============================================================

report = {
    "schema":
        "LAISE TUK2 Automated Mastering Selection v1.0",

    "project":
        "tukana_02_a_mata_se_move",

    "test_id":
        "TUK2-T008",

    "status":
        status,

    "source": {
        "path":
            str(
                source
            ),

        "sha256":
            source_expected_hash,

        "spatial_QA":
            "TUK2-T007 PASS",

        "integrated_lufs":
            source_lufs,

        "true_peak_dbtp":
            source_tp,

        "lra_lu":
            source_lra,

        "crest_factor_db":
            source_crest,
    },

    "targets": {
        "optimized_integrated_lufs":
            target_i,

        "true_peak_dbtp":
            target_tp,

        "target_lra_lu":
            target_lra,

        "refined_integrated_lufs":
            refined_target_i,

        "refinement_relaxation_lu":
            relaxation,

        "rationale":
            (
                "Target derived from Tukana II measured "
                "crest factor and LRA; not copied from "
                "another song."
            ),
    },

    "processing": {
        "A_TRANSPARENT":
            (
                "Stereo-linked uniform gain only."
            ),

        "B_OPTIMIZED":
            (
                "Two-pass EBU R128 normalization with "
                "stereo-linked true-peak control."
            ),

        "C_REFINED":
            (
                "B method with objectively selected "
                "lower loudness target to reduce "
                "transient intervention."
            ),

        "excluded": [
            "EQ",
            "stereo widening",
            "Mid/Side processing",
            "channel-independent gain",
            "new binaural processing",
            "new spatialization",
            "stem remixing",
        ],
    },

    "A_transparent_gain_db":
        transparent_gain,

    "B_first_pass":
        b_first_pass,

    "C_first_pass":
        c_first_pass,

    "B_transient_precheck":
        b_transient_precheck,

    "refinement_gate":
        refinement_gate,

    "master_weights":
        MASTER_WEIGHTS,

    "candidates":
        records,

    "eligible_candidates":
        eligible,

    "selected_master":
        winner,

    "selected_master_score":
        selected[
            "master_score"
        ],

    "checks":
        checks,

    "final_artifacts": {
        "wav":
            file_metrics(
                final_wav
            ),

        "aac_320":
            {
                "path":
                    str(
                        final_aac
                    ),

                "sha256":
                    _sha256(
                        final_aac
                    ),
            },
    },

    "next_stage":
        (
            "TUK2-T009 lossless/lossy delivery "
            "validation if TUK2-T008 PASS."
        ),

    "limitations": [
        (
            "Spatial-integrity, transient and codec "
            "scores are technical fidelity proxies, "
            "not universal human audibility claims."
        ),

        (
            "Role-timed attack windows use stems only "
            "as timing references; attack measurements "
            "are made on the full mastered mix."
        ),
    ],
}


dump(
    REPORT_PATH,
    report
)


# ============================================================
# TERMINAL RESULT
# ============================================================

ranking = sorted(
    records,

    key=lambda label:
        records[
            label
        ][
            "master_score"
        ],

    reverse=True
)


print()
print(
    "=================================================="
)
print(
    "TUK2-T008 RESULT"
)
print(
    "=================================================="
)


for index, label in enumerate(
    ranking,
    1
):

    r = records[
        label
    ]


    print()
    print(
        f"#{index} {label}"
    )

    print(
        f"   MASTER SCORE      : "
        f"{r['master_score']:.4f}"
    )

    print(
        f"   Eligible          : "
        f"{r['eligible']}"
    )

    print(
        f"   LUFS              : "
        f"{r['loudness']['integrated_lufs']:.2f}"
    )

    print(
        f"   True peak         : "
        f"{r['loudness']['true_peak_dbtp']:.2f} dBTP"
    )

    print(
        f"   Crest             : "
        f"{r['signal']['crest_factor_db']:.2f} dB"
    )

    print(
        f"   Spatial integrity : "
        f"{r['spatial_integrity']['score']:.3f}"
    )

    print(
        f"   Transients        : "
        f"{r['transient_fidelity']['score']:.3f}"
    )

    print(
        f"   Codec score       : "
        f"{r['codec']['codec_score']:.3f}"
    )


print()
print(
    "--------------------------------------------------"
)

print(
    f"SELECTED MASTER : {winner}"
)

print(
    f"MASTER SCORE    : "
    f"{selected['master_score']:.4f}"
)

print(
    f"LUFS            : "
    f"{selected['loudness']['integrated_lufs']:.2f}"
)

print(
    f"TRUE PEAK       : "
    f"{selected['loudness']['true_peak_dbtp']:.2f} dBTP"
)

print(
    f"SPATIAL         : "
    f"{selected['spatial_integrity']['score']:.3f}"
)

print(
    f"TRANSIENTS      : "
    f"{selected['transient_fidelity']['score']:.3f}"
)

print(
    f"AAC320 SCORE    : "
    f"{selected['codec']['codec_score']:.3f}"
)

print(
    "--------------------------------------------------"
)


print()
print(
    f"TUK2-T008: {status}"
)

print()
print(
    "Selected WAV:"
)

print(
    final_wav
)

print()
print(
    "Report:"
)

print(
    REPORT_PATH
)


if status != "PASS":

    raise RuntimeError(
        "TUK2-T008 mastering selection failed. "
        "Do not create delivery formats yet."
    )

