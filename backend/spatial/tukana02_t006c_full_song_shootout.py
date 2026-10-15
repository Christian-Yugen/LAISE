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
)

from music02_t005_render import render
from music02_t005_selection import evaluate
from music02_preview import write24
from tukana_preview_renderer import read_segment


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

SCENES = BASE / "spatial_scenes"
REPORTS = BASE / "reports"

OUT = (
    BASE
    / "full_candidate_shootout"
)

MIXES = (
    OUT
    / "renders"
)

SECTION_REPORTS = (
    OUT
    / "sections"
)

FINAL_REPORT = (
    OUT
    / "TUK2_T006C_full_song_selection.json"
)

T003 = (
    PROJECT
    / "analysis"
    / "TUK2_T003_structural_masking_map.json"
)

T005_LIBRARY = (
    PROJECT
    / "experiments"
    / "TUK2_T005"
    / "reports"
    / "probe_library_native256.json"
)

T006B = (
    REPORTS
    / "TUK2_T006B_objective_selection.json"
)


CANDIDATES = [
    "A_CLARITY",
    "B_SEPARATION",
    "C_MOTION",
    "D_ADAPTIVE",
]

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


def peak_safety_score(peak):

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


# ============================================================
# PREREQUISITES
# ============================================================

for path in (
    T003,
    T005_LIBRARY,
    T006B,
):
    if not path.exists():
        raise RuntimeError(
            f"Missing prerequisite: {path}"
        )


if OUT.exists():
    raise RuntimeError(
        "TUK2-T006C namespace already exists. "
        "Preserving evidence."
    )


t003 = load(T003)
library = load(T005_LIBRARY)
t006b = load(T006B)


if t003["status"] != "PASS":
    raise RuntimeError(
        "T003 did not PASS."
    )

if (
    library[
        "validation"
    ]["status"]
    != "PASS"
):
    raise RuntimeError(
        "Probe library did not PASS."
    )

if t006b["status"] != "PASS":
    raise RuntimeError(
        "T006B did not PASS."
    )


common_input_gain = float(
    t006b[
        "common_input_gain"
    ]["linear"]
)

orbit_score = float(
    t006b[
        "trajectory_component"
    ]["score"]
)


OUT.mkdir(
    parents=True,
    exist_ok=False
)

MIXES.mkdir(
    parents=True,
    exist_ok=False
)

SECTION_REPORTS.mkdir(
    parents=True,
    exist_ok=False
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

    if len(
        scene["sources"]
    ) != 12:
        raise RuntimeError(
            f"{candidate}: expected 12 sources."
        )

    scenes[candidate] = {
        "scene":
            scene,

        "path":
            path,

        "sha256":
            sha256_file(path),
    }


# ============================================================
# SECTION MAP
# ============================================================

sections = t003[
    "sections"
]

if len(sections) != 12:
    raise RuntimeError(
        f"Expected 12 sections, got {len(sections)}"
    )


# ============================================================
# FULL-STEM RENDER
# ============================================================

def render_full_source(
    candidate,
    source,
    index
):

    role = source[
        "source_id"
    ]

    raw, sr = read_segment(
        source[
            "input_file"
        ],
        0.0,
        DURATION
    )

    if sr != RATE:
        raise RuntimeError(
            f"{role}: unexpected sample rate {sr}"
        )

    if raw.shape != (
        2,
        FRAMES
    ):
        raise RuntimeError(
            f"{role}: unexpected source frames "
            f"{raw.shape}"
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


    progress_state = [-1]

    def progress(
        fraction,
        elapsed
    ):

        bucket = int(
            fraction * 5
        )

        if bucket > progress_state[0]:

            progress_state[0] = bucket

            percent = min(
                100,
                bucket * 20
            )

            print(
                f"      {role:<18} "
                f"{percent:3d}% "
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
            f"{candidate}/{role}: "
            f"bad rendered geometry {wet.shape}"
        )


    if not np.isfinite(
        wet
    ).all():
        raise RuntimeError(
            f"{candidate}/{role}: NaN/Inf"
        )


    return (
        wet.astype(
            np.float32,
            copy=False
        ),
        {
            "role":
                role,

            "frames":
                int(
                    wet.shape[1]
                ),

            "peak":
                float(
                    np.max(
                        np.abs(
                            wet
                        )
                    )
                ),

            "input_sha256":
                sha256_file(
                    Path(
                        source[
                            "input_file"
                        ]
                    )
                ),

            "control_trace_count":
                len(trace),

            "plugin_latency_compensated_samples":
                LATENCY_SAMPLES,
        }
    )


# ============================================================
# SECTION QA
# ============================================================

def evaluate_sections(
    candidate,
    scene,
    arrays
):

    records = []

    for section in sections:

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

            role = source[
                "source_id"
            ]

            raw, sr = read_segment(
                source[
                    "input_file"
                ],
                start,
                end - start
            )

            if sr != RATE:
                raise RuntimeError(
                    f"{role}: unexpected rate"
                )

            dry[role] = raw


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
        ] = peak_safety_score(
            section_peak
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


        lead_values = [
            float(
                item[
                    "clarity_proxy"
                ]
            )
            for item
            in result[
                "lead_masking_windows"
            ]
        ]


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

            "components":
                components,

            "section_mix_peak":
                section_peak,

            "section_mix_peak_dbfs":
                db(
                    section_peak
                ),

            "lead_intelligibility_proxy":
                (
                    float(
                        np.mean(
                            lead_values
                        )
                    )
                    if lead_values
                    else None
                ),

            "pairwise_matrix":
                result[
                    "pairwise_matrix"
                ],

            "transient_by_role":
                result[
                    "transient_by_role"
                ],

            "technical_proxy_notice":
                result[
                    "interpretation"
                ],
        }


        dump(
            SECTION_REPORTS
            / candidate
            / f"{sid}.json",
            record
        )


        records.append(
            record
        )


        print(
            f"      QA {sid} "
            f"score={score:.3f}",
            flush=True
        )


    return records


# ============================================================
# FULL CANDIDATE LOOP
# ============================================================

candidate_results = {}


print()
print(
    "=================================================="
)
print(
    "TUK2-T006C - FULL-SONG CANDIDATE SHOOTOUT"
)
print(
    "=================================================="
)

print(
    f"Frames per source       : {FRAMES}"
)

print(
    f"Duration                : {DURATION:.1f}s"
)

print(
    f"Candidates              : {len(CANDIDATES)}"
)

print(
    f"Sources per candidate   : 12"
)

print(
    f"Common input gain       : "
    f"{common_input_gain:.8f} "
    f"({db(common_input_gain):.2f} dB)"
)

print(
    f"Orbit integrity         : "
    f"{orbit_score:.3f}"
)


for candidate_index, candidate in enumerate(
    CANDIDATES,
    1
):

    print()
    print(
        "=================================================="
    )

    print(
        f"[{candidate_index}/4] {candidate}"
    )

    print(
        "=================================================="
    )


    scene = scenes[
        candidate
    ]["scene"]


    arrays = {}

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

        print(
            f"   [{index:02}/12] Rendering {role}",
            flush=True
        )


        wet, source_report = (
            render_full_source(
                candidate,
                source,
                index
            )
        )


        arrays[
            role
        ] = wet

        source_reports[
            role
        ] = source_report


    # --------------------------------------------------------
    # FULL MIX
    # --------------------------------------------------------

    mix = np.sum(
        np.stack(
            [
                arrays[role]
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


    if not np.isfinite(
        mix
    ).all():
        raise RuntimeError(
            f"{candidate}: invalid full mix"
        )


    full_peak = float(
        np.max(
            np.abs(
                mix
            )
        )
    )

    full_rms = float(
        np.sqrt(
            np.mean(
                mix.astype(
                    np.float64
                ) ** 2
            )
        )
    )


    if full_peak >= 1.0:

        raise RuntimeError(
            f"{candidate}: clipping "
            f"{full_peak:.6f}"
        )


    mix_path = (
        MIXES
        / f"TUK2_T006C_{candidate}_full_PCM24.wav"
    )


    write24(
        mix_path,
        mix
    )


    # --------------------------------------------------------
    # ALL 12 SECTIONS
    # --------------------------------------------------------

    section_records = (
        evaluate_sections(
            candidate,
            scene,
            arrays
        )
    )


    durations = np.asarray(
        [
            item[
                "duration_seconds"
            ]
            for item
            in section_records
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
                item[
                    "components"
                ][component]
                for item
                in section_records
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


    # Full programme peak overrides averaged
    # section peak safety.
    overall[
        "peak_safety"
    ] = peak_safety_score(
        full_peak
    )


    overall_score = float(
        sum(
            float(
                overall[key]
            )
            * float(
                WEIGHTS[key]
            )
            for key
            in WEIGHTS
        )
    )


    candidate_results[
        candidate
    ] = {
        "score":
            overall_score,

        "components":
            overall,

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

        "full_mix": {
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
                full_peak,

            "peak_dbfs":
                db(
                    full_peak
                ),

            "rms_dbfs":
                db(
                    full_rms
                ),
        },

        "source_reports":
            source_reports,

        "sections":
            section_records,
    }


    print()
    print(
        f"   FULL SCORE : "
        f"{overall_score:.4f}"
    )

    print(
        f"   PEAK       : "
        f"{db(full_peak):.2f} dBFS"
    )


    # release several GB before next candidate
    del arrays
    del mix

    gc.collect()


# ============================================================
# FULL-SONG RANKING
# ============================================================

ranking = sorted(
    CANDIDATES,
    key=lambda name:
        candidate_results[
            name
        ]["score"],
    reverse=True
)


winner = ranking[0]
runner_up = ranking[1]


margin = float(
    candidate_results[
        winner
    ]["score"]
    -
    candidate_results[
        runner_up
    ]["score"]
)


confidence = (
    "CLEAR"
    if margin >= 0.50
    else (
        "MODERATE"
        if margin >= 0.20
        else "CLOSE"
    )
)


# ============================================================
# SECTION WINNERS
# ============================================================

section_winners = []

win_count = {
    candidate: 0
    for candidate
    in CANDIDATES
}


for index, section in enumerate(
    sections
):

    local = max(
        CANDIDATES,
        key=lambda name:
            candidate_results[
                name
            ][
                "sections"
            ][index][
                "score"
            ]
    )


    local_score = (
        candidate_results[
            local
        ][
            "sections"
        ][index][
            "score"
        ]
    )


    win_count[
        local
    ] += 1


    section_winners.append({
        "section_id":
            section[
                "section_id"
            ],

        "winner":
            local,

        "score":
            local_score,
    })


# ============================================================
# PREVIEW VS FULL COMPARISON
# ============================================================

preview_winner = (
    t006b[
        "provisional_winner"
    ]
)


ranking_consistent = (
    preview_winner
    == winner
)


# ============================================================
# REPORT
# ============================================================

report = {
    "schema":
        "LAISE TUK2 Full-Song Candidate Shootout v1.0",

    "project":
        "tukana_02_a_mata_se_move",

    "test_id":
        "TUK2-T006C",

    "status":
        "PASS",

    "scope":
        (
            "All four candidate architectures rendered "
            "over the complete 330-second, 12-stem timeline. "
            "All twelve structural sections independently "
            "evaluated from actual binaural outputs."
        ),

    "frames":
        FRAMES,

    "duration_seconds":
        DURATION,

    "candidate_count":
        4,

    "sources_per_candidate":
        12,

    "full_source_renders":
        48,

    "weights":
        WEIGHTS,

    "common_input_gain":
        common_input_gain,

    "plugin_latency_compensation": {
        "preroll_seconds":
            1.0,

        "latency_samples":
            LATENCY_SAMPLES,

        "tail_samples":
            TAIL_SAMPLES,

        "gain_time_offset_samples":
            -LATENCY_SAMPLES,
    },

    "ranking":
        [
            {
                "rank":
                    rank + 1,

                "candidate":
                    name,

                "score":
                    candidate_results[
                        name
                    ]["score"],
            }

            for rank, name
            in enumerate(
                ranking
            )
        ],

    "full_song_winner":
        winner,

    "runner_up":
        runner_up,

    "winner_margin":
        margin,

    "selection_confidence":
        confidence,

    "preview_winner":
        preview_winner,

    "preview_full_ranking_consistent":
        ranking_consistent,

    "section_win_count":
        win_count,

    "section_winners":
        section_winners,

    "candidates":
        candidate_results,

    "decision_policy":
        (
            "Highest duration-weighted full-song objective "
            "score from actual binaural section outputs. "
            "No subjective promotion, no recency bonus, "
            "and no forced 360 musical motion."
        ),

    "selection_state":
        (
            "READY_FOR_INDEPENDENT_WINNER_QA"
            if confidence
            in (
                "CLEAR",
                "MODERATE"
            )
            else
            "FULL_SONG_RESULT_STILL_CLOSE"
        ),

    "epistemic_limits": [
        (
            "Scores remain engineering proxies rather than "
            "human perceptual probabilities."
        ),

        (
            "Front/back and elevation classification on "
            "musical native-stereo stems are domain-shifted "
            "relative to controlled probe calibration."
        ),

        (
            "The full-song winner is still not a mastered "
            "or release-approved file. Independent winner "
            "QA is required next."
        ),
    ],
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
    "TUK2-T006C RESULT"
)
print(
    "=================================================="
)


for rank, name in enumerate(
    ranking,
    1
):

    result = candidate_results[
        name
    ]

    print()
    print(
        f"#{rank} {name}"
    )

    print(
        f"   SCORE                    : "
        f"{result['score']:.4f}"
    )

    for component in WEIGHTS:

        print(
            f"   {component:<25}: "
            f"{result['components'][component]:.3f}"
        )


print()
print(
    "--------------------------------------------------"
)

print(
    f"FULL-SONG WINNER : {winner}"
)

print(
    f"RUNNER-UP        : {runner_up}"
)

print(
    f"MARGIN           : {margin:.4f}"
)

print(
    f"CONFIDENCE       : {confidence}"
)

print(
    f"PREVIEW WINNER   : {preview_winner}"
)

print(
    f"CONSISTENT       : {ranking_consistent}"
)

print(
    "--------------------------------------------------"
)


print()
print(
    "SECTION WIN COUNTS:"
)

for candidate in CANDIDATES:

    print(
        f"{candidate:<14} : "
        f"{win_count[candidate]}"
    )


print()
print(
    "SECTION WINNERS:"
)

for item in section_winners:

    print(
        f"{item['section_id']} | "
        f"{item['winner']:<14} | "
        f"{item['score']:.4f}"
    )


print()
print(
    "Selection state:"
)

print(
    report[
        "selection_state"
    ]
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
    "TUK2-T006C: PASS"
)

