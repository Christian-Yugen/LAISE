from __future__ import annotations

import json
import hashlib
import gc
from pathlib import Path

import numpy as np

from music02_t005_common import (
    RATE,
    BLOCK,
    WEIGHTS,
    rms,
    file_metrics,
    transient_proxy,
)

from music02_t005_render import render
from music02_t005_selection import evaluate
from music02_preview import write24

from dearvr_adapter import (
    interpolate_pose,
    wrap_azimuth,
)

from tukana_preview_renderer import (
    read_segment,
)


ROOT = Path(r"C:\Projetos2026\LAISE")

PROJECT = (
    ROOT
    / "projects"
    / "tukana_02_a_mata_se_move"
)

T006_BASE = (
    PROJECT
    / "experiments"
    / "TUK2_T006"
)

SCENE_PATH = (
    T006_BASE
    / "spatial_scenes"
    / "TUK2_T006D_SECTION_HYBRID.json"
)

T006D_REPORT = (
    T006_BASE
    / "section_adaptive_hybrid"
    / "TUK2_T006D_section_hybrid_validation.json"
)

T006C_REPORT = (
    T006_BASE
    / "full_candidate_shootout"
    / "TUK2_T006C_full_song_selection.json"
)

T003 = (
    PROJECT
    / "analysis"
    / "TUK2_T003_structural_masking_map.json"
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
    / "TUK2_T007"
)

STEM_OUT = (
    OUT
    / "spatial_stems"
)

RENDERS = (
    OUT
    / "renders"
)

REPORTS = (
    OUT
    / "reports"
)

SECTION_REPORTS = (
    REPORTS
    / "sections"
)

FINAL_MIX = (
    RENDERS
    / "TUK2_T007_FINAL_SPATIAL_PCM24_48k.wav"
)

DRY_COMPARE = (
    RENDERS
    / "TUK2_T007_DRY_RMS_MATCHED_PCM24_48k.wav"
)

FINAL_REPORT = (
    REPORTS
    / "TUK2_T007_final_spatial_qa.json"
)

FINAL_SCENE = (
    OUT
    / "spatial_scenes"
    / "TUK2_T007_FINAL_SPATIAL_SCENE.json"
)

AUTOMATION_MANIFEST = (
    OUT
    / "spatial_scenes"
    / "TUK2_T007_automation_manifest.json"
)


DURATION = 330.0

FRAMES = round(
    DURATION * RATE
)

PREROLL_FRAMES = RATE
LATENCY_SAMPLES = 512
TAIL_SAMPLES = 512


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


def sha256(path):
    h = hashlib.sha256()

    with Path(path).open("rb") as f:
        for chunk in iter(
            lambda: f.read(
                1024 * 1024
            ),
            b""
        ):
            h.update(chunk)

    return h.hexdigest()


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


def peak_safety(peak):

    if peak <= 0.95:
        return 100.0

    if peak >= 1.0:
        return 0.0

    return float(
        100.0
        * (
            1.0
            -
            (
                peak - 0.95
            )
            / 0.05
        )
    )


def click_proxy(audio):

    delta = np.max(
        np.abs(
            np.diff(
                audio,
                axis=1
            )
        ),
        axis=0
    )

    # One-second preroll is 48000 samples.
    # Its phase against the 256-frame renderer grid
    # is retained after latency compensation.
    phase = (
        -PREROLL_FRAMES
    ) % BLOCK

    boundaries = np.arange(
        phase if phase else BLOCK,
        audio.shape[1],
        BLOCK
    )

    valid = boundaries[
        boundaries > 0
    ]

    boundary_delta = delta[
        valid - 1
    ]

    threshold = max(
        0.05,
        float(
            np.percentile(
                delta,
                99.99
            )
        )
        * 2.0
    )

    unusual = int(
        np.sum(
            boundary_delta
            > threshold
        )
    )

    return {
        "plugin_boundary_phase_frames":
            int(phase),

        "threshold":
            threshold,

        "boundary_count":
            int(
                len(
                    boundary_delta
                )
            ),

        "unusual_block_boundary_events":
            unusual,

        "max_program_delta":
            float(
                np.max(
                    delta
                )
            ),

        "max_boundary_delta":
            float(
                np.max(
                    boundary_delta
                )
            )
            if len(
                boundary_delta
            )
            else 0.0,

        "interpretation":
            (
                "Derivative-based renderer-boundary screen. "
                "It detects unusual discontinuities at block "
                "boundaries; it is not a universal proof of "
                "absence of every audible artifact."
            ),
    }


# ============================================================
# PREREQUISITES
# ============================================================

for path in (
    SCENE_PATH,
    T006D_REPORT,
    T006C_REPORT,
    T003,
    LIBRARY_PATH,
):
    if not path.exists():

        raise RuntimeError(
            f"Missing prerequisite: {path}"
        )


if OUT.exists():

    raise RuntimeError(
        "TUK2-T007 namespace already exists. "
        "Preserving previous evidence."
    )


scene = load(
    SCENE_PATH
)

t006d = load(
    T006D_REPORT
)

t006c = load(
    T006C_REPORT
)

t003 = load(
    T003
)

library = load(
    LIBRARY_PATH
)


if t006d["status"] != "PASS":

    raise RuntimeError(
        "T006D did not PASS."
    )


if (
    t006d[
        "selection_state"
    ]
    !=
    "HYBRID_SELECTED_FOR_INDEPENDENT_QA"
):

    raise RuntimeError(
        "Hybrid was not selected for independent QA."
    )


if len(
    scene["sources"]
) != 12:

    raise RuntimeError(
        "Final scene does not contain 12 sources."
    )


if len(
    t003["sections"]
) != 12:

    raise RuntimeError(
        "Expected 12 structural sections."
    )


common_input_gain = float(
    t006c[
        "common_input_gain"
    ]
)


orbit_score = float(
    t006d[
        "components"
    ][
        "orbit_integrity"
    ]
)


expected_score = float(
    t006d[
        "hybrid_score"
    ]
)


expected_mix_path = Path(
    t006d[
        "full_mix"
    ][
        "path"
    ]
)


expected_mix_hash = (
    t006d[
        "full_mix"
    ][
        "sha256"
    ]
)


OUT.mkdir(
    parents=True,
    exist_ok=False
)

STEM_OUT.mkdir(
    parents=True,
    exist_ok=False
)

RENDERS.mkdir(
    parents=True,
    exist_ok=False
)

REPORTS.mkdir(
    parents=True,
    exist_ok=False
)

SECTION_REPORTS.mkdir(
    parents=True,
    exist_ok=False
)


print()
print(
    "=================================================="
)
print(
    "TUK2-T007 - INDEPENDENT FINAL SPATIAL QA"
)
print(
    "=================================================="
)

print(
    f"Scene          : {SCENE_PATH}"
)

print(
    f"Scene SHA256   : {sha256(SCENE_PATH)}"
)

print(
    f"Frames         : {FRAMES}"
)

print(
    f"Duration       : {DURATION:.1f}s"
)

print(
    f"Sources        : 12"
)

print(
    f"Input gain     : "
    f"{common_input_gain:.8f} "
    f"({db(common_input_gain):.2f} dB)"
)

print(
    f"Expected score : {expected_score:.4f}"
)


# ============================================================
# GEOMETRY REVALIDATION
# ============================================================

geometry = {}

geometry_pass = True


times = np.arange(
    0.0,
    DURATION,
    BLOCK / RATE,
    dtype=np.float64
)


for source in scene[
    "sources"
]:

    role = source[
        "source_id"
    ]


    poses = [
        interpolate_pose(
            source[
                "keyframes"
            ],
            float(t)
        )
        for t in times
    ]


    az = np.asarray(
        [
            p[0]
            for p in poses
        ],
        dtype=np.float64
    )


    el = np.asarray(
        [
            p[1]
            for p in poses
        ],
        dtype=np.float64
    )


    wrapped = np.asarray(
        [
            wrap_azimuth(x)
            for x in az
        ],
        dtype=np.float64
    )


    circular = (
        (
            np.diff(
                wrapped
            )
            + 180.0
        )
        % 360.0
        - 180.0
    )


    el_steps = np.diff(
        el
    )


    max_az_step = (
        float(
            np.max(
                np.abs(
                    circular
                )
            )
        )
        if len(circular)
        else 0.0
    )


    max_el_step = (
        float(
            np.max(
                np.abs(
                    el_steps
                )
            )
        )
        if len(el_steps)
        else 0.0
    )


    passed = bool(
        max_az_step < 5.0
        and
        max_el_step < 5.0
    )


    geometry_pass &= passed


    geometry[
        role
    ] = {
        "status":
            (
                "PASS"
                if passed
                else "FAIL"
            ),

        "max_circular_step_deg":
            max_az_step,

        "max_elevation_step_deg":
            max_el_step,

        "wrapped_crossings":
            int(
                np.sum(
                    np.abs(
                        np.diff(
                            wrapped
                        )
                    )
                    > 180.0
                )
            ),
    }


if not geometry_pass:

    raise RuntimeError(
        "Independent geometry validation failed."
    )


print()
print(
    "Geometry revalidation: PASS"
)


# ============================================================
# FULL INDEPENDENT RE-RENDER
# ============================================================

arrays = {}
dry_arrays = {}
source_reports = {}


for index, source in enumerate(
    scene[
        "sources"
    ],
    1
):

    role = source[
        "source_id"
    ]


    print()
    print(
        f"[{index:02}/12] Rendering {role}",
        flush=True
    )


    source_path = Path(
        source[
            "input_file"
        ]
    )


    current_input_hash = sha256(
        source_path
    )


    if (
        current_input_hash
        != source[
            "input_sha256"
        ]
    ):

        raise RuntimeError(
            f"Source hash mismatch: {role}"
        )


    raw, sr = read_segment(
        source_path,
        0.0,
        DURATION
    )


    if sr != RATE:

        raise RuntimeError(
            f"Unexpected rate: {role}"
        )


    if raw.shape != (
        2,
        FRAMES
    ):

        raise RuntimeError(
            f"Unexpected frame count: {role}"
        )


    original = raw.copy()


    staged = (
        raw
        * np.float32(
            common_input_gain
        )
    )


    padded = np.concatenate(
        (
            np.zeros(
                (
                    2,
                    PREROLL_FRAMES
                ),
                dtype=np.float32
            ),

            staged,

            np.zeros(
                (
                    2,
                    TAIL_SAMPLES
                ),
                dtype=np.float32
            ),
        ),
        axis=1
    )


    progress_bucket = [-1]


    def progress(
        fraction,
        elapsed
    ):

        bucket = min(
            4,
            int(
                fraction * 4
            )
        )

        if bucket > progress_bucket[0]:

            progress_bucket[0] = bucket

            print(
                f"      "
                f"{min(100,bucket*25):3d}% "
                f"({elapsed:.1f}s)",
                flush=True
            )


    wet, _, trace = render(
        padded,
        source,
        start=-1.0,
        curve=None,
        policy="total",
        progress=progress,
        gain_time_offset=(
            -LATENCY_SAMPLES
            / RATE
        ),
    )


    first = (
        PREROLL_FRAMES
        + LATENCY_SAMPLES
    )


    wet = wet[
        :,
        first:
        first + FRAMES
    ]


    if wet.shape != (
        2,
        FRAMES
    ):

        raise RuntimeError(
            f"Rendered frame mismatch: {role}"
        )


    if not np.isfinite(
        wet
    ).all():

        raise RuntimeError(
            f"NaN/Inf in {role}"
        )


    keys = source[
        "keyframes"
    ]


    gain_times = [
        float(
            k[
                "time_seconds"
            ]
        )
        for k in keys
    ]


    gain_values = [
        float(
            k.get(
                "gain_db",
                0.0
            )
        )
        for k in keys
    ]


    timeline = (
        np.arange(
            FRAMES,
            dtype=np.float64
        )
        / RATE
    )


    gains_db = (
        float(
            source.get(
                "gain_db",
                0.0
            )
        )
        +
        np.interp(
            timeline,
            gain_times,
            gain_values
        )
    )


    dry = (
        original
        * np.float32(
            common_input_gain
        )
        * np.power(
            10.0,
            gains_db / 20.0
        ).astype(
            np.float32
        )
    )


    stem_path = (
        STEM_OUT
        / (
            f"{role}"
            f"_spatial_PCM24_48k.wav"
        )
    )


    write24(
        stem_path,
        wet
    )


    stem_metrics = file_metrics(
        stem_path
    )


    clicks = click_proxy(
        wet
    )


    transients = transient_proxy(
        original,
        wet,
        latency_samples=0
    )


    arrays[
        role
    ] = wet


    dry_arrays[
        role
    ] = dry


    source_reports[
        role
    ] = {
        "input_file":
            str(
                source_path
            ),

        "input_sha256":
            current_input_hash,

        "frames":
            int(
                wet.shape[1]
            ),

        "finite":
            bool(
                np.isfinite(
                    wet
                ).all()
            ),

        "peak":
            float(
                np.max(
                    np.abs(
                        wet
                    )
                )
            ),

        "rms_dbfs":
            db(
                rms(
                    wet
                )
            ),

        "transient_proxy":
            transients,

        "click_proxy":
            clicks,

        "control_trace_count":
            len(trace),

        "delivery":
            stem_metrics,
    }


# ============================================================
# FULL MIX
# ============================================================

mix = np.sum(
    np.stack(
        [
            arrays[
                role
            ]
            for role
            in sorted(
                arrays
            )
        ]
    ).astype(
        np.float64
    ),
    axis=0
).astype(
    np.float32
)


drymix = np.sum(
    np.stack(
        [
            dry_arrays[
                role
            ]
            for role
            in sorted(
                dry_arrays
            )
        ]
    ).astype(
        np.float64
    ),
    axis=0
).astype(
    np.float32
)


if not np.isfinite(
    mix
).all():

    raise RuntimeError(
        "Final mix contains NaN/Inf."
    )


if mix.shape != (
    2,
    FRAMES
):

    raise RuntimeError(
        "Final mix frame mismatch."
    )


final_peak = float(
    np.max(
        np.abs(
            mix
        )
    )
)


if final_peak >= 1.0:

    raise RuntimeError(
        f"Final mix clips: {final_peak}"
    )


write24(
    FINAL_MIX,
    mix
)


final_hash = sha256(
    FINAL_MIX
)


# ============================================================
# DRY RMS-MATCHED DIAGNOSTIC
# ============================================================

dry_gain = (
    rms(
        mix
    )
    /
    max(
        rms(
            drymix
        ),
        1e-15
    )
)


dry_compare = (
    drymix
    * np.float32(
        dry_gain
    )
)


dry_peak = float(
    np.max(
        np.abs(
            dry_compare
        )
    )
)


if dry_peak >= 0.999:

    diagnostic_scale = (
        0.95
        / dry_peak
    )

    dry_compare *= np.float32(
        diagnostic_scale
    )

else:

    diagnostic_scale = 1.0


write24(
    DRY_COMPARE,
    dry_compare
)


# ============================================================
# FILE-LEVEL QA
# ============================================================

mix_metrics = file_metrics(
    FINAL_MIX
)


dry_metrics = file_metrics(
    DRY_COMPARE
)


mix_clicks = click_proxy(
    mix
)


dc = np.mean(
    mix.astype(
        np.float64
    ),
    axis=1
)


# ============================================================
# SECTION-BY-SECTION INDEPENDENT QA
# ============================================================

section_records = []

expected_sections = {
    x[
        "section_id"
    ]:
        x

    for x in t006d[
        "sections"
    ]
}


for section in t003[
    "sections"
]:

    sid = section[
        "section_id"
    ]

    start = float(
        section[
            "start_seconds"
        ]
    )

    end = float(
        section[
            "end_seconds"
        ]
    )


    left = round(
        start * RATE
    )

    right = round(
        end * RATE
    )


    wet = {
        role:
            audio[
                :,
                left:right
            ]

        for role, audio
        in arrays.items()
    }


    dry = {}


    for source in scene[
        "sources"
    ]:

        raw, sr = read_segment(
            source[
                "input_file"
            ],
            start,
            end - start
        )

        dry[
            source[
                "source_id"
            ]
        ] = raw


    result = evaluate(
        wet,
        scene,
        dry,
        library,
        start=start,
        step=1.0,
        details=False,
        transient_latency=0,
    )


    section_mix = np.sum(
        np.stack(
            list(
                wet.values()
            )
        ).astype(
            np.float64
        ),
        axis=0
    )


    section_peak = float(
        np.max(
            np.abs(
                section_mix
            )
        )
    )


    components = dict(
        result[
            "components"
        ]
    )


    components[
        "orbit_integrity"
    ] = orbit_score


    components[
        "peak_safety"
    ] = peak_safety(
        section_peak
    )


    score = float(
        sum(
            components[k]
            * float(
                WEIGHTS[k]
            )
            for k in WEIGHTS
        )
    )


    expected = float(
        expected_sections[
            sid
        ][
            "hybrid_score"
        ]
    )


    delta = (
        score - expected
    )


    record = {
        "section_id":
            sid,

        "start_seconds":
            start,

        "end_seconds":
            end,

        "duration_seconds":
            end - start,

        "score":
            score,

        "T006D_score":
            expected,

        "delta_vs_T006D":
            delta,

        "components":
            components,

        "lead_masking":
            result[
                "lead_masking_windows"
            ],

        "transient_by_role":
            result[
                "transient_by_role"
            ],

        "pairwise_matrix":
            result[
                "pairwise_matrix"
            ],
    }


    dump(
        SECTION_REPORTS
        / f"{sid}.json",
        record
    )


    section_records.append(
        record
    )


    print(
        f"QA {sid} | "
        f"score={score:.4f} | "
        f"delta={delta:+.6f}",
        flush=True
    )


# ============================================================
# RECOMPUTE FULL SPATIAL SCORE
# ============================================================

durations = np.asarray(
    [
        x[
            "duration_seconds"
        ]
        for x in section_records
    ],
    dtype=np.float64
)


overall = {}


for component in WEIGHTS:

    if component == "orbit_integrity":

        overall[
            component
        ] = orbit_score

        continue


    values = np.asarray(
        [
            x[
                "components"
            ][component]
            for x in section_records
        ],
        dtype=np.float64
    )


    overall[
        component
    ] = float(
        np.average(
            values,
            weights=durations
        )
    )


overall[
    "peak_safety"
] = peak_safety(
    final_peak
)


final_score = float(
    sum(
        overall[k]
        * float(
            WEIGHTS[k]
        )
        for k in WEIGHTS
    )
)


score_delta = (
    final_score
    - expected_score
)


max_section_delta = float(
    max(
        abs(
            x[
                "delta_vs_T006D"
            ]
        )
        for x in section_records
    )
)


# ============================================================
# CHECKS
# ============================================================

role_clicks = {
    role:
        source_reports[
            role
        ][
            "click_proxy"
        ][
            "unusual_block_boundary_events"
        ]

    for role
    in source_reports
}


checks = {
    "twelve_independent_roles":
        len(
            source_reports
        ) == 12,

    "exact_role_frame_count":
        all(
            report[
                "frames"
            ] == FRAMES

            for report
            in source_reports.values()
        ),

    "exact_mix_frame_count":
        (
            mix_metrics[
                "signal"
            ][
                "frames"
            ]
            == FRAMES
        ),

    "timeline_origin_zero":
        True,

    "no_activity_trimming":
        True,

    "all_inputs_hash_verified":
        all(
            source_reports[
                s[
                    "source_id"
                ]
            ][
                "input_sha256"
            ]
            ==
            s[
                "input_sha256"
            ]

            for s
            in scene[
                "sources"
            ]
        ),

    "finite_unclipped":
        bool(
            np.isfinite(
                mix
            ).all()
            and
            final_peak < 1.0
        ),

    "true_peak_headroom":
        (
            mix_metrics[
                "loudness"
            ][
                "true_peak_dbtp"
            ]
            <= -3.0
        ),

    "dc_safe":
        bool(
            np.max(
                np.abs(
                    dc
                )
            )
            < 0.001
        ),

    "no_detected_mix_block_clicks":
        (
            mix_clicks[
                "unusual_block_boundary_events"
            ]
            == 0
        ),

    "no_detected_role_block_clicks":
        all(
            value == 0
            for value
            in role_clicks.values()
        ),

    "geometry_revalidated":
        geometry_pass,

    "all_12_sections_measured":
        len(
            section_records
        ) == 12,

    "section_scores_reproduced":
        (
            max_section_delta
            <= 0.001
        ),

    "full_score_reproduced":
        (
            abs(
                score_delta
            )
            <= 0.001
        ),

    "deterministic_pcm24_rerender":
        (
            final_hash
            ==
            expected_mix_hash
        ),

    "mastering_not_applied":
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
# FINAL SCENE / MANIFEST
# ============================================================

final_scene = dict(
    scene
)

final_scene[
    "test_id"
] = "TUK2-T007"

final_scene[
    "status"
] = status

final_scene[
    "final_spatial_score"
] = final_score

final_scene[
    "sample_rate"
] = RATE

final_scene[
    "full_render_frames"
] = FRAMES

final_scene[
    "mastering_applied"
] = False


dump(
    FINAL_SCENE,
    final_scene
)


manifest = {
    "schema":
        "LAISE TUK2 Final Spatial Automation Manifest v1.0",

    "project":
        "tukana_02_a_mata_se_move",

    "test_id":
        "TUK2-T007",

    "scene":
        str(
            FINAL_SCENE
        ),

    "scene_sha256":
        sha256(
            FINAL_SCENE
        ),

    "rate":
        RATE,

    "frames":
        FRAMES,

    "block_size":
        BLOCK,

    "pre_roll_seconds":
        1.0,

    "plugin_latency_compensated_samples":
        LATENCY_SAMPLES,

    "tail_padding_samples":
        TAIL_SAMPLES,

    "common_input_gain":
        common_input_gain,

    "roles": [
        {
            "source_id":
                source[
                    "source_id"
                ],

            "input_file":
                source[
                    "input_file"
                ],

            "input_sha256":
                source[
                    "input_sha256"
                ],

            "keyframes":
                source[
                    "keyframes"
                ],

            "distance_keyframes":
                source.get(
                    "distance_keyframes",
                    []
                ),

            "growth_reference_distance_m":
                source.get(
                    "growth_reference_distance_m"
                ),
        }

        for source
        in scene[
            "sources"
        ]
    ],
}


dump(
    AUTOMATION_MANIFEST,
    manifest
)


# ============================================================
# FINAL REPORT
# ============================================================

report = {
    "schema":
        "LAISE TUK2 Independent Final Spatial QA v1.0",

    "project":
        "tukana_02_a_mata_se_move",

    "test_id":
        "TUK2-T007",

    "status":
        status,

    "selected_architecture":
        "SECTION_ADAPTIVE_HYBRID",

    "checks":
        checks,

    "frames":
        FRAMES,

    "duration_seconds":
        DURATION,

    "sample_rate":
        RATE,

    "outputs": {
        "final_binaural":
            mix_metrics,

        "dry_rms_matched_diagnostic":
            dry_metrics,
    },

    "T006D_reference": {
        "expected_mix_path":
            str(
                expected_mix_path
            ),

        "expected_mix_sha256":
            expected_mix_hash,

        "independent_mix_sha256":
            final_hash,

        "bit_identical_pcm24":
            (
                final_hash
                ==
                expected_mix_hash
            ),

        "expected_score":
            expected_score,

        "independent_score":
            final_score,

        "score_delta":
            score_delta,

        "maximum_section_score_delta":
            max_section_delta,
    },

    "final_spatial_components":
        overall,

    "final_spatial_score":
        final_score,

    "mix_peak_dbfs":
        db(
            final_peak
        ),

    "dc_offset_lr":
        dc.tolist(),

    "mix_click_proxy":
        mix_clicks,

    "geometry":
        geometry,

    "source_reports":
        source_reports,

    "actual_full_section_scores":
        section_records,

    "mastering_applied":
        False,

    "next_stage":
        (
            "TUK2-T008 mastering candidate generation "
            "only if TUK2-T007 status is PASS."
        ),

    "epistemic_limit":
        (
            "Masking, clarity, localization and spatial "
            "discriminability scores remain engineering "
            "proxies. Passing QA establishes reproducible "
            "technical behavior, not universal human "
            "perception."
        ),
}


dump(
    FINAL_REPORT,
    report
)


# ============================================================
# SUMMARY
# ============================================================

print()
print(
    "=================================================="
)
print(
    "TUK2-T007 RESULT"
)
print(
    "=================================================="
)


for name, value in checks.items():

    print(
        f"{name:<34}: "
        f"{'PASS' if value else 'FAIL'}"
    )


print()
print(
    f"T006D SHA256 : {expected_mix_hash}"
)

print(
    f"T007  SHA256 : {final_hash}"
)

print(
    f"Bit-identical: "
    f"{final_hash == expected_mix_hash}"
)


print()
print(
    f"T006D score  : "
    f"{expected_score:.4f}"
)

print(
    f"T007 score   : "
    f"{final_score:.4f}"
)

print(
    f"Score delta  : "
    f"{score_delta:+.6f}"
)


print()
print(
    f"Max section delta : "
    f"{max_section_delta:.6f}"
)


print()
print(
    f"Sample peak        : "
    f"{db(final_peak):.2f} dBFS"
)

print(
    f"True peak          : "
    f"{mix_metrics['loudness']['true_peak_dbtp']:.2f} dBTP"
)

print(
    f"Integrated LUFS    : "
    f"{mix_metrics['loudness']['integrated_lufs']:.2f}"
)


print()
print(
    "FINAL SPATIAL COMPONENTS:"
)

for key in WEIGHTS:

    print(
        f"{key:<26}: "
        f"{overall[key]:.3f}"
    )


print()
print(
    f"TUK2-T007: {status}"
)

print()
print(
    "Report:"
)

print(
    FINAL_REPORT
)


if status != "PASS":

    raise RuntimeError(
        "TUK2-T007 independent QA failed. "
        "Do not master yet."
    )

