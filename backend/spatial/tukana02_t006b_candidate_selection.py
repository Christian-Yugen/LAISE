from __future__ import annotations

import json
import math
import hashlib
from pathlib import Path

import numpy as np

from music02_t005_common import (
    RATE,
    BLOCK,
    WEIGHTS,
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

BASE = (
    PROJECT
    / "experiments"
    / "TUK2_T006"
)

SCENES = (
    BASE
    / "spatial_scenes"
)

REPORTS = (
    BASE
    / "reports"
)

RENDERS = (
    BASE
    / "renders"
    / "objective_candidates"
)

T001 = (
    PROJECT
    / "analysis"
    / "TUK2_T001_immutable_intake.json"
)

T005B = (
    PROJECT
    / "experiments"
    / "TUK2_T005"
    / "reports"
    / "TUK2_T005B_dynamic_spatial_validation.json"
)

LIBRARY = (
    PROJECT
    / "experiments"
    / "TUK2_T005"
    / "reports"
    / "probe_library_native256.json"
)

T006A = (
    REPORTS
    / "TUK2_T006A_summary.json"
)

R1 = (
    REPORTS
    / "TUK2_T006A_R1_point_event_correction.json"
)

FINAL_REPORT = (
    REPORTS
    / "TUK2_T006B_objective_selection.json"
)


CANDIDATES = [
    "A_CLARITY",
    "B_SEPARATION",
    "C_MOTION",
    "D_ADAPTIVE",
]


PREROLL_SECONDS = 1.0

# Conservative common staging.
# Same gain for every candidate/window.
WORST_CASE_DRY_SUM_TARGET = 0.20


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


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:

        for chunk in iter(
            lambda: f.read(
                1024 * 1024
            ),
            b""
        ):
            h.update(chunk)

    return h.hexdigest()


def db(x):
    return float(
        20.0
        * np.log10(
            max(
                float(x),
                1e-15
            )
        )
    )


# ============================================================
# PREREQUISITES
# ============================================================

for path in (
    T001,
    T005B,
    LIBRARY,
    T006A,
    R1,
):
    if not path.exists():
        raise RuntimeError(
            f"Missing prerequisite: {path}"
        )


if FINAL_REPORT.exists():
    raise RuntimeError(
        f"Refusing overwrite: {FINAL_REPORT}"
    )


if RENDERS.exists():
    raise RuntimeError(
        "TUK2-T006B render namespace already exists."
    )


t001 = load(T001)
t005b = load(T005B)
library = load(LIBRARY)
t006a = load(T006A)
r1 = load(R1)


if t001["status"] != "PASS":
    raise RuntimeError(
        "T001 did not PASS."
    )

if t005b["status"] != "PASS":
    raise RuntimeError(
        "T005B did not PASS."
    )

if library["validation"]["status"] != "PASS":
    raise RuntimeError(
        "T005A probe library did not PASS."
    )

if t006a["status"] != "PASS":
    raise RuntimeError(
        "T006A did not PASS."
    )

if r1["status"] != "PASS":
    raise RuntimeError(
        "T006A-R1 did not PASS."
    )


preview_windows = (
    t006a[
        "preview_windows"
    ]
)


if len(preview_windows) != 4:
    raise RuntimeError(
        "Expected exactly four objective preview windows."
    )


# ============================================================
# LOAD SCENES
# ============================================================

scenes = {}

for candidate in CANDIDATES:

    path = (
        SCENES
        / f"TUK2_T006A_R1_{candidate}.json"
    )

    if not path.exists():
        raise RuntimeError(
            f"Missing scene: {path}"
        )

    scene = load(path)

    if scene["test_id"] != "TUK2-T006A-R1":
        raise RuntimeError(
            f"Unexpected scene version: {path}"
        )

    scenes[candidate] = {
        "path":
            path,

        "sha256":
            sha256_file(path),

        "scene":
            scene,
    }


# ============================================================
# SCENE CONSISTENCY
# ============================================================

role_sets = []

for item in scenes.values():

    roles = {
        s["source_id"]
        for s in item[
            "scene"
        ]["sources"]
    }

    role_sets.append(
        roles
    )


if any(
    roles != role_sets[0]
    for roles in role_sets[1:]
):
    raise RuntimeError(
        "Candidate role sets differ."
    )


roles = sorted(
    role_sets[0]
)


if len(roles) != 12:
    raise RuntimeError(
        f"Expected 12 stems, got {len(roles)}"
    )


# ============================================================
# ORIGINAL STEM HASH VERIFICATION
# ============================================================

reference_scene = (
    scenes[
        "A_CLARITY"
    ]["scene"]
)

for source in reference_scene[
    "sources"
]:

    path = Path(
        source["input_file"]
    )

    if not path.exists():
        raise RuntimeError(
            f"Missing source: {path}"
        )

    current = sha256_file(
        path
    )

    if (
        current
        != source[
            "input_sha256"
        ]
    ):
        raise RuntimeError(
            f"Input hash failure: "
            f"{source['source_id']}"
        )


# ============================================================
# COMMON INPUT GAIN
# ============================================================

# Use T001 full-song peak bounds instead of
# candidate-specific normalization.

linear_peaks = []

for filename, stem in (
    t001["stems"].items()
):

    peak_db = float(
        stem[
            "metrics"
        ]["peak_dbfs"]
    )

    linear_peaks.append(
        10.0 ** (
            peak_db / 20.0
        )
    )


worst_case_peak_sum = float(
    np.sum(
        linear_peaks
    )
)


common_input_gain = min(
    1.0,
    WORST_CASE_DRY_SUM_TARGET
    / max(
        worst_case_peak_sum,
        1e-12
    )
)

common_input_gain_db = db(
    common_input_gain
)


# ============================================================
# TECHNICAL TRAJECTORY SCORE
# ============================================================

orbit = t005b[
    "continuous_360"
]

orbit_corr = float(
    orbit[
        "ild_progression_correlation"
    ]
)

orbit_distance = float(
    orbit[
        "median_paired_signature_distance"
    ]
)

# Same general tracking principle used in previous
# LAISE spatial validation:
# strong progression correlation + low signature distance.

technical_trajectory_score = float(
    np.clip(
        100.0 * (
            0.70
            * max(
                orbit_corr,
                0.0
            )
            +
            0.30
            * math.exp(
                -orbit_distance
                / 1.5
            )
        ),
        0.0,
        100.0
    )
)


# ============================================================
# GEOMETRY AUDIT
# ============================================================

def geometry_audit(scene):

    result = {}

    duration = float(
        scene[
            "duration_seconds"
        ]
    )

    times = np.arange(
        0.0,
        duration,
        BLOCK / RATE,
        dtype=np.float64
    )

    all_pass = True

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

        elevation_steps = np.diff(
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
                        elevation_steps
                    )
                )
            )
            if len(elevation_steps)
            else 0.0
        )

        crossings = int(
            np.sum(
                np.abs(
                    np.diff(
                        wrapped
                    )
                )
                > 180.0
            )
        )

        role_pass = bool(
            max_az_step < 5.0
            and
            max_el_step < 5.0
        )

        all_pass = (
            all_pass
            and role_pass
        )

        result[role] = {
            "status":
                (
                    "PASS"
                    if role_pass
                    else "FAIL"
                ),

            "max_circular_step_deg":
                max_az_step,

            "max_elevation_step_deg":
                max_el_step,

            "wrapped_crossings":
                crossings,

            "unwrapped_azimuth_range_deg":
                [
                    float(
                        np.min(az)
                    ),
                    float(
                        np.max(az)
                    ),
                ],

            "elevation_range_deg":
                [
                    float(
                        np.min(el)
                    ),
                    float(
                        np.max(el)
                    ),
                ],
        }

    return {
        "status":
            (
                "PASS"
                if all_pass
                else "FAIL"
            ),

        "sources":
            result,
    }


geometry = {}

for candidate in CANDIDATES:

    geometry[
        candidate
    ] = geometry_audit(
        scenes[
            candidate
        ]["scene"]
    )

    if (
        geometry[
            candidate
        ]["status"]
        != "PASS"
    ):
        raise RuntimeError(
            f"Geometry audit failed: "
            f"{candidate}"
        )


# ============================================================
# AUDIO WINDOW WITH 1 SECOND PRE-ROLL
# ============================================================

def read_with_preroll(
    path,
    start,
    duration
):

    if start >= PREROLL_SECONDS:

        read_start = (
            start
            - PREROLL_SECONDS
        )

        read_duration = (
            duration
            + PREROLL_SECONDS
        )

        raw, sr = read_segment(
            path,
            read_start,
            read_duration
        )

        return (
            raw,
            sr,
            read_start,
            round(
                PREROLL_SECONDS
                * sr
            )
        )


    # For music beginning at zero:
    # prepend deterministic digital silence.

    raw, sr = read_segment(
        path,
        0.0,
        duration
    )

    pre_frames = round(
        PREROLL_SECONDS
        * sr
    )

    zeros = np.zeros(
        (
            2,
            pre_frames
        ),
        dtype=np.float32
    )

    padded = np.concatenate(
        (
            zeros,
            raw
        ),
        axis=1
    )

    return (
        padded,
        sr,
        -PREROLL_SECONDS,
        pre_frames
    )


# ============================================================
# RENDER ONE CANDIDATE / ONE WINDOW
# ============================================================

def render_window(
    candidate,
    scene,
    window
):

    start = float(
        window[
            "start_seconds"
        ]
    )

    duration = float(
        window[
            "duration_seconds"
        ]
    )

    wet_by_role = {}
    dry_by_role = {}

    role_reports = {}

    for index, source in enumerate(
        scene[
            "sources"
        ],
        1
    ):

        role = source[
            "source_id"
        ]

        raw, sr, render_start, crop = (
            read_with_preroll(
                source[
                    "input_file"
                ],
                start,
                duration
            )
        )

        if sr != RATE:
            raise RuntimeError(
                f"Unexpected rate: {role}"
            )

        staged = (
            raw.astype(
                np.float32,
                copy=False
            )
            * np.float32(
                common_input_gain
            )
        )

        wet, dry, controls = render(
            staged,
            source,
            start=render_start,
            curve=None,
            policy="total",
        )

        wet = wet[
            :,
            crop:
        ]

        dry = dry[
            :,
            crop:
        ]

        expected_frames = round(
            duration
            * RATE
        )

        wet = wet[
            :,
            :expected_frames
        ]

        dry = dry[
            :,
            :expected_frames
        ]

        if (
            wet.shape
            != (
                2,
                expected_frames
            )
        ):
            raise RuntimeError(
                f"Unexpected wet geometry: "
                f"{candidate}/{role}"
            )

        if not np.isfinite(
            wet
        ).all():
            raise RuntimeError(
                f"NaN/Inf: "
                f"{candidate}/{role}"
            )

        wet_by_role[
            role
        ] = wet

        dry_by_role[
            role
        ] = dry

        role_reports[
            role
        ] = {
            "wet_peak":
                float(
                    np.max(
                        np.abs(
                            wet
                        )
                    )
                ),

            "dry_peak":
                float(
                    np.max(
                        np.abs(
                            dry
                        )
                    )
                ),

            "control_trace_count":
                len(
                    controls
                ),
        }


    evaluation = evaluate(
        wet_by_role,
        scene,
        dry_by_role,
        library,
        start=start,
        step=1.0,
        details=False,
        transient_latency=512,
    )


    mix = np.sum(
        np.stack(
            [
                wet_by_role[
                    role
                ]
                for role
                in sorted(
                    wet_by_role
                )
            ]
        ).astype(
            np.float64
        ),
        axis=0
    ).astype(
        np.float32
    )


    mix_peak = float(
        np.max(
            np.abs(
                mix
            )
        )
    )

    mix_rms = float(
        np.sqrt(
            np.mean(
                mix.astype(
                    np.float64
                ) ** 2
            )
        )
    )


    if not np.isfinite(
        mix
    ).all():
        raise RuntimeError(
            f"Invalid mix: {candidate}"
        )


    if mix_peak >= 1.0:
        raise RuntimeError(
            f"Unsafe peak {mix_peak:.6f}: "
            f"{candidate} / "
            f"{window['window_id']}"
        )


    components = dict(
        evaluation[
            "components"
        ]
    )


    # T005B technically proves trajectory integrity.
    # It remains constant across candidates because no
    # musical full-360 orbit is being forced.
    components[
        "orbit_integrity"
    ] = (
        technical_trajectory_score
    )


    # Override original boolean-style peak check with
    # actual candidate mix headroom.
    if mix_peak <= 0.95:
        peak_safety = 100.0

    else:
        peak_safety = max(
            0.0,
            100.0
            * (
                1.0
                -
                (
                    mix_peak
                    - 0.95
                )
                / 0.05
            )
        )


    components[
        "peak_safety"
    ] = peak_safety


    missing = (
        set(
            WEIGHTS
        )
        -
        set(
            components
        )
    )

    if missing:
        raise RuntimeError(
            f"Missing scoring components: "
            f"{missing}"
        )


    score = float(
        sum(
            float(
                components[key]
            )
            * float(
                WEIGHTS[key]
            )
            for key
            in WEIGHTS
        )
    )


    output_dir = (
        RENDERS
        / candidate
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    mix_path = (
        output_dir
        / (
            f"{window['window_id']}"
            f"_{start:.1f}_"
            f"{start+duration:.1f}.wav"
        )
    )

    write24(
        mix_path,
        mix
    )


    return {
        "candidate":
            candidate,

        "window":
            window,

        "score":
            score,

        "components":
            components,

        "mix": {
            "path":
                str(
                    mix_path
                ),

            "sha256":
                sha256_file(
                    mix_path
                ),

            "frames":
                int(
                    mix.shape[1]
                ),

            "peak":
                mix_peak,

            "peak_dbfs":
                db(
                    mix_peak
                ),

            "rms_dbfs":
                db(
                    mix_rms
                ),
        },

        "roles":
            role_reports,

        "lead_masking_windows":
            evaluation[
                "lead_masking_windows"
            ],

        "transient_by_role":
            evaluation[
                "transient_by_role"
            ],

        "pairwise_matrix":
            evaluation[
                "pairwise_matrix"
            ],

        "interpretation":
            evaluation[
                "interpretation"
            ],
    }


# ============================================================
# RUN
# ============================================================

RENDERS.mkdir(
    parents=True,
    exist_ok=False
)


print()
print(
    "=================================================="
)
print(
    "TUK2-T006B - OBJECTIVE CANDIDATE SELECTION"
)
print(
    "=================================================="
)

print()
print(
    f"Common input gain        : "
    f"{common_input_gain:.8f} "
    f"({common_input_gain_db:.2f} dB)"
)

print(
    f"Worst-case dry peak sum : "
    f"{worst_case_peak_sum:.4f}"
)

print(
    f"Trajectory score        : "
    f"{technical_trajectory_score:.3f}"
)

print()
print(
    "Weights:"
)

for key, value in (
    WEIGHTS.items()
):
    print(
        f"  {key:<26} "
        f"{value:.2f}"
    )


# ============================================================
# RENDER ALL 16 CANDIDATE/WINDOW COMBINATIONS
# ============================================================

results = {
    candidate: []
    for candidate
    in CANDIDATES
}


total = (
    len(CANDIDATES)
    * len(
        preview_windows
    )
)

counter = 0


for window in preview_windows:

    print()
    print(
        "--------------------------------------------------"
    )

    print(
        f"{window['window_id']} | "
        f"{window['start_seconds']:.1f}-"
        f"{window['end_seconds']:.1f}s | "
        f"{window['reason']}"
    )

    print(
        "--------------------------------------------------"
    )

    for candidate in CANDIDATES:

        counter += 1

        print(
            f"[{counter:02}/{total}] "
            f"Rendering {candidate}..."
        )

        record = render_window(
            candidate,
            scenes[
                candidate
            ]["scene"],
            window
        )

        results[
            candidate
        ].append(
            record
        )

        print(
            f"      score="
            f"{record['score']:.3f}  "
            f"peak="
            f"{record['mix']['peak_dbfs']:.2f} dBFS"
        )


# ============================================================
# AGGREGATE — EQUAL REPRESENTATIVE-WINDOW WEIGHT
# ============================================================

candidate_scores = {}

for candidate in CANDIDATES:

    records = results[
        candidate
    ]

    aggregate_components = {}

    for component in WEIGHTS:

        aggregate_components[
            component
        ] = float(
            np.mean(
                [
                    r[
                        "components"
                    ][component]
                    for r
                    in records
                ]
            )
        )


    final_score = float(
        sum(
            aggregate_components[key]
            * float(
                WEIGHTS[key]
            )
            for key
            in WEIGHTS
        )
    )


    window_scores = {
        r[
            "window"
        ][
            "window_id"
        ]:
            r[
                "score"
            ]
        for r
        in records
    }


    candidate_scores[
        candidate
    ] = {
        "score":
            final_score,

        "components":
            aggregate_components,

        "window_scores":
            window_scores,

        "scene":
            str(
                scenes[
                    candidate
                ]["path"]
            ),

        "scene_sha256":
            scenes[
                candidate
            ]["sha256"],

        "geometry":
            geometry[
                candidate
            ],

        "windows":
            records,
    }


# ============================================================
# RANKING
# ============================================================

ranking = sorted(
    CANDIDATES,
    key=lambda name:
        candidate_scores[
            name
        ]["score"],
    reverse=True
)


winner = ranking[0]

runner_up = ranking[1]

margin = float(
    candidate_scores[
        winner
    ]["score"]
    -
    candidate_scores[
        runner_up
    ]["score"]
)


selection_confidence = (
    "CLEAR"
    if margin >= 0.50
    else (
        "MODERATE"
        if margin >= 0.20
        else "CLOSE"
    )
)


# ============================================================
# COMPONENT WINNERS
# ============================================================

component_winners = {}

for component in WEIGHTS:

    best = max(
        CANDIDATES,
        key=lambda name:
            candidate_scores[
                name
            ][
                "components"
            ][component]
    )

    component_winners[
        component
    ] = {
        "candidate":
            best,

        "value":
            candidate_scores[
                best
            ][
                "components"
            ][component],
    }


# ============================================================
# REPORT
# ============================================================

report = {
    "schema":
        "LAISE TUK2 Objective Candidate Selection v1.0",

    "project":
        "tukana_02_a_mata_se_move",

    "test_id":
        "TUK2-T006B",

    "status":
        "PASS",

    "selection_scope":
        (
            "Four objective representative 20-second "
            "windows rendered from all 12 stems through "
            "dearVR PRO 2 using identical staging."
        ),

    "candidate_count":
        len(
            CANDIDATES
        ),

    "window_count":
        len(
            preview_windows
        ),

    "actual_candidate_renders":
        len(
            CANDIDATES
        )
        * len(
            preview_windows
        ),

    "stems_per_render":
        12,

    "common_input_gain": {
        "linear":
            common_input_gain,

        "db":
            common_input_gain_db,

        "policy":
            (
                "Identical conservative staging for all "
                "candidates; no candidate-specific "
                "normalization or loudness advantage."
            ),
    },

    "weights":
        WEIGHTS,

    "trajectory_component": {
        "score":
            technical_trajectory_score,

        "source":
            "TUK2-T005B",

        "candidate_discriminating":
            False,

        "reason":
            (
                "Full technical 360/180/elevation validation "
                "is inherited equally. No musical full orbit "
                "is forced solely to gain score."
            ),
    },

    "ranking":
        [
            {
                "rank":
                    i + 1,

                "candidate":
                    name,

                "score":
                    candidate_scores[
                        name
                    ]["score"],
            }
            for i, name
            in enumerate(
                ranking
            )
        ],

    "provisional_winner":
        winner,

    "runner_up":
        runner_up,

    "winner_margin":
        margin,

    "selection_confidence":
        selection_confidence,

    "component_winners":
        component_winners,

    "candidates":
        candidate_scores,

    "decision_policy":
        (
            "Highest locked weighted objective score. "
            "No subjective promotion and no recency bonus."
        ),

    "epistemic_limits": [
        (
            "Scores are engineering proxies and are not "
            "human perceptual probabilities."
        ),

        (
            "Front/back and elevation classification use "
            "controlled broadband reference models; musical "
            "stems are a domain shift."
        ),

        (
            "T006B selects a provisional architecture from "
            "representative actual binaural renders. The "
            "winner must still pass independent full-song QA."
        ),

        (
            "Distance remains a control parameter and is not "
            "treated as proof of perceived near-field depth."
        ),
    ],

    "next_stage":
        (
            "Render provisional winner for the entire "
            "330-second timeline and independently validate "
            "all sections before mastering."
        ),
}


dump(
    FINAL_REPORT,
    report
)


# ============================================================
# TERMINAL SUMMARY
# ============================================================

print()
print(
    "=================================================="
)
print(
    "TUK2-T006B RESULT"
)
print(
    "=================================================="
)

for index, name in enumerate(
    ranking,
    1
):

    item = candidate_scores[
        name
    ]

    print()
    print(
        f"#{index} {name}"
    )

    print(
        f"   SCORE          : "
        f"{item['score']:.4f}"
    )

    for component in WEIGHTS:

        print(
            f"   "
            f"{component:<23}: "
            f"{item['components'][component]:.3f}"
        )


print()
print(
    "--------------------------------------------------"
)

print(
    f"PROVISIONAL WINNER : {winner}"
)

print(
    f"RUNNER-UP          : {runner_up}"
)

print(
    f"MARGIN             : {margin:.4f}"
)

print(
    f"CONFIDENCE         : {selection_confidence}"
)

print(
    "--------------------------------------------------"
)


print()
print(
    "WINDOW WINNERS:"
)

for window in preview_windows:

    wid = window[
        "window_id"
    ]

    local = max(
        CANDIDATES,
        key=lambda name:
            candidate_scores[
                name
            ][
                "window_scores"
            ][wid]
    )

    value = candidate_scores[
        local
    ][
        "window_scores"
    ][wid]

    print(
        f"{wid} | "
        f"{local:<14} | "
        f"{value:.4f} | "
        f"{window['reason']}"
    )


print()
print(
    "Report:"
)

print(
    FINAL_REPORT
)

print()
print(
    "TUK2-T006B: PASS"
)

