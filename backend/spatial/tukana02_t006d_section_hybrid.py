from __future__ import annotations

import json
import math
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

SCENES = BASE / "spatial_scenes"

T006C = (
    BASE
    / "full_candidate_shootout"
    / "TUK2_T006C_full_song_selection.json"
)

LIBRARY = (
    PROJECT
    / "experiments"
    / "TUK2_T005"
    / "reports"
    / "probe_library_native256.json"
)

OUT = (
    BASE
    / "section_adaptive_hybrid"
)

HYBRID_SCENE = (
    SCENES
    / "TUK2_T006D_SECTION_HYBRID.json"
)

REPORT = (
    OUT
    / "TUK2_T006D_section_hybrid_validation.json"
)

MIX_PATH = (
    OUT
    / "TUK2_T006D_SECTION_HYBRID_full_PCM24.wav"
)


CANDIDATES = [
    "A_CLARITY",
    "B_SEPARATION",
    "C_MOTION",
    "D_ADAPTIVE",
]

DURATION = 330.0
FRAMES = round(DURATION * RATE)

PREROLL = RATE
LATENCY = 512
TAIL = 512


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
            lambda: f.read(1024 * 1024),
            b""
        ):
            h.update(chunk)

    return h.hexdigest()


def db(v):
    return float(
        20 * np.log10(
            max(float(v), 1e-15)
        )
    )


def peak_score(peak):

    if peak <= 0.95:
        return 100.0

    if peak >= 1.0:
        return 0.0

    return float(
        100
        * (
            1
            - (peak - 0.95) / 0.05
        )
    )


def circular_difference(a, b):

    return abs(
        ((b - a + 180) % 360)
        - 180
    )


# ============================================================
# LOAD
# ============================================================

if OUT.exists():
    raise RuntimeError(
        "TUK2-T006D namespace already exists."
    )

if HYBRID_SCENE.exists():
    raise RuntimeError(
        "Hybrid scene already exists."
    )

selection = load(T006C)
library = load(LIBRARY)


# ============================================================
# T006C ORBIT-INTEGRITY INHERITANCE
# ============================================================

orbit_values = {
    name: float(
        selection["candidates"][name]["components"]["orbit_integrity"]
    )
    for name in CANDIDATES
}

orbit_spread = (
    max(orbit_values.values())
    - min(orbit_values.values())
)

if orbit_spread > 1e-6:
    raise RuntimeError(
        "T006C candidates do not share the same "
        f"orbit_integrity: {orbit_values}"
    )

orbit_score = float(
    sum(orbit_values.values())
    / len(orbit_values)
)



if selection["status"] != "PASS":
    raise RuntimeError(
        "T006C did not PASS."
    )


scenes = {}

for name in CANDIDATES:

    path = (
        SCENES
        / f"TUK2_T006A_R1_{name}.json"
    )

    scenes[name] = load(path)


# ============================================================
# EXACT SECTION WINNERS FROM T006C
# ============================================================

section_winners = {
    x["section_id"]:
        x["winner"]

    for x in selection[
        "section_winners"
    ]
}


sections = (
    selection[
        "candidates"
    ][
        selection[
            "full_song_winner"
        ]
    ][
        "sections"
    ]
)


print()
print(
    "=================================================="
)
print(
    "TUK2-T006D - SECTION-ADAPTIVE HYBRID"
)
print(
    "=================================================="
)

print()
print(
    "SECTION SOURCE MAP:"
)

for s in sections:

    sid = s["section_id"]

    print(
        f"{sid} -> "
        f"{section_winners[sid]}"
    )


# ============================================================
# STATIC SOURCE CONSISTENCY
# ============================================================

canonical = {
    source["source_id"]:
        source

    for source in scenes[
        "A_CLARITY"
    ]["sources"]
}


for name in CANDIDATES:

    check = {
        source["source_id"]:
            source

        for source in scenes[
            name
        ]["sources"]
    }

    if set(check) != set(canonical):
        raise RuntimeError(
            f"Role mismatch in {name}"
        )

    for role in canonical:

        a = canonical[role]
        b = check[role]

        for field in (
            "input_file",
            "input_sha256",
            "class",
            "home",
            "gain_db",
            "distance_keyframes",
            "growth_reference_distance_m",
        ):

            if a.get(field) != b.get(field):

                raise RuntimeError(
                    f"Non-motion source difference: "
                    f"{name}/{role}/{field}"
                )


# ============================================================
# BOUNDARY POSE AUDIT
# ============================================================

boundary_audit = []

boundaries = sorted(
    {
        float(s["start_seconds"])
        for s in sections
    }
    |
    {
        float(s["end_seconds"])
        for s in sections
    }
)


for t in boundaries:

    for role in canonical:

        poses = {}

        for name in CANDIDATES:

            source = next(
                s
                for s in scenes[
                    name
                ]["sources"]
                if s["source_id"] == role
            )

            poses[name] = (
                interpolate_pose(
                    source[
                        "keyframes"
                    ],
                    t
                )
            )


        az = [
            p[0]
            for p in poses.values()
        ]

        el = [
            p[1]
            for p in poses.values()
        ]


        max_az_diff = max(
            circular_difference(a, b)

            for a in az
            for b in az
        )

        max_el_diff = (
            max(el) - min(el)
        )


        # Boundaries should effectively return
        # to the common source lane.
        boundary_pass = bool(
            max_az_diff <= 2.0
            and
            max_el_diff <= 2.0
        )


        boundary_audit.append({
            "time_seconds":
                t,

            "role":
                role,

            "max_candidate_azimuth_difference_deg":
                max_az_diff,

            "max_candidate_elevation_difference_deg":
                max_el_diff,

            "status":
                (
                    "PASS"
                    if boundary_pass
                    else "FAIL"
                ),
        })


bad = [
    x
    for x in boundary_audit
    if x["status"] != "PASS"
]


if bad:

    print()
    print(
        "BOUNDARY POSE DIFFERENCES DETECTED:"
    )

    for item in bad[:20]:
        print(item)

    raise RuntimeError(
        "Hybrid cannot be safely assembled "
        "until candidate boundary poses agree."
    )


print()
print(
    "Boundary pose audit: PASS"
)


# ============================================================
# SPLICE KEYFRAMES BY SECTION
# ============================================================

hybrid_sources = []


for role, base_source in (
    canonical.items()
):

    frames = []

    selected_events = []


    for index, section in enumerate(
        sections
    ):

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

        winner = (
            section_winners[
                sid
            ]
        )


        source = next(
            s
            for s in scenes[
                winner
            ]["sources"]
            if s[
                "source_id"
            ] == role
        )


        # Exact winner pose at structural
        # boundaries.
        start_pose = (
            interpolate_pose(
                source[
                    "keyframes"
                ],
                start
            )
        )

        end_pose = (
            interpolate_pose(
                source[
                    "keyframes"
                ],
                end
            )
        )


        frames.append({
            "time_seconds":
                start,

            "azimuth_deg_unwrapped":
                float(
                    start_pose[0]
                ),

            "elevation_deg":
                float(
                    start_pose[1]
                ),

            "gain_db":
                0.0,

            "reason":
                (
                    f"{sid} START "
                    f"from {winner}"
                ),
        })


        # Preserve all winner automation
        # strictly inside its own section.
        for frame in source[
            "keyframes"
        ]:

            t = float(
                frame[
                    "time_seconds"
                ]
            )

            if (
                t > start + 1e-7
                and
                t < end - 1e-7
            ):

                copied = dict(frame)

                copied[
                    "reason"
                ] = (
                    f"{sid}/{winner}: "
                    + copied.get(
                        "reason",
                        ""
                    )
                )

                frames.append(
                    copied
                )


        frames.append({
            "time_seconds":
                end,

            "azimuth_deg_unwrapped":
                float(
                    end_pose[0]
                ),

            "elevation_deg":
                float(
                    end_pose[1]
                ),

            "gain_db":
                0.0,

            "reason":
                (
                    f"{sid} END "
                    f"from {winner}"
                ),
        })


        for event in source.get(
            "selected_motion_events",
            []
        ):

            if event.get(
                "section_id"
            ) == sid:

                record = dict(event)

                record[
                    "architecture"
                ] = winner

                selected_events.append(
                    record
                )


    # Deterministic same-time resolution.
    frames.sort(
        key=lambda x:
            x["time_seconds"]
    )


    deduped = []

    for frame in frames:

        if (
            deduped
            and abs(
                deduped[-1][
                    "time_seconds"
                ]
                -
                frame[
                    "time_seconds"
                ]
            )
            < 1e-7
        ):

            deduped[-1] = frame

        else:

            deduped.append(
                frame
            )


    hybrid = dict(
        base_source
    )

    hybrid[
        "keyframes"
    ] = deduped

    hybrid[
        "selected_motion_events"
    ] = selected_events

    hybrid[
        "hybrid_section_sources"
    ] = {
        sid:
            section_winners[
                sid
            ]
        for sid
        in section_winners
    }


    hybrid_sources.append(
        hybrid
    )


hybrid_scene = {
    "schema":
        "LAISE TUK2 Section Adaptive Scene v1.0",

    "project":
        "tukana_02_a_mata_se_move",

    "test_id":
        "TUK2-T006D",

    "candidate":
        "SECTION_ADAPTIVE_HYBRID",

    "status":
        "GENERATED_NOT_YET_VALIDATED",

    "duration_seconds":
        DURATION,

    "selection_source":
        str(T006C),

    "section_architecture_map":
        section_winners,

    "principles": {
        "section_specific_objective_selection":
            True,

        "event_gated_motion":
            True,

        "return_home":
            True,

        "point_events_static_during_attack":
            True,

        "lead_is_protected_mobile_anchor":
            True,

        "no_forced_full_musical_orbit":
            True,

        "distance_nearfield_bonus":
            False,
    },

    "sources":
        hybrid_sources,
}


dump(
    HYBRID_SCENE,
    hybrid_scene
)


# ============================================================
# FINE-GRID GEOMETRY AUDIT
# ============================================================

geometry = {}


times = np.arange(
    0,
    DURATION,
    BLOCK / RATE
)


geometry_pass = True


for source in hybrid_sources:

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


    az = np.array(
        [
            x[0]
            for x in poses
        ]
    )

    el = np.array(
        [
            x[1]
            for x in poses
        ]
    )


    wrapped = np.array(
        [
            wrap_azimuth(x)
            for x in az
        ]
    )


    circular_steps = (
        (
            np.diff(
                wrapped
            )
            + 180
        )
        % 360
        - 180
    )


    max_az = float(
        np.max(
            np.abs(
                circular_steps
            )
        )
    )

    max_el = float(
        np.max(
            np.abs(
                np.diff(
                    el
                )
            )
        )
    )


    passed = bool(
        max_az < 5.0
        and
        max_el < 5.0
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
            max_az,

        "max_elevation_step_deg":
            max_el,
    }


if not geometry_pass:

    raise RuntimeError(
        "Hybrid geometry audit failed."
    )


print(
    "Fine-grid geometry audit: PASS"
)


# ============================================================
# RENDER FULL HYBRID
# ============================================================

common_gain = float(
    selection[
        "common_input_gain"
    ]
)


arrays = {}


print()
print(
    "FULL HYBRID RENDER:"
)


for index, source in enumerate(
    hybrid_sources,
    1
):

    role = source[
        "source_id"
    ]


    print(
        f"[{index:02}/12] "
        f"{role}"
    )


    raw, sr = read_segment(
        source[
            "input_file"
        ],
        0,
        DURATION
    )


    if sr != RATE:
        raise RuntimeError(
            f"Invalid rate: {role}"
        )


    staged = (
        raw
        * np.float32(
            common_gain
        )
    )


    padded = np.concatenate(
        (
            np.zeros(
                (2, PREROLL),
                dtype=np.float32
            ),

            staged,

            np.zeros(
                (2, TAIL),
                dtype=np.float32
            ),
        ),
        axis=1
    )


    wet, _, _ = render(
        padded,
        source,
        start=-1.0,
        curve=None,
        policy="total",
        gain_time_offset=(
            -LATENCY / RATE
        ),
    )


    first = (
        PREROLL
        + LATENCY
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
            f"Bad frames: {role}"
        )


    if not np.isfinite(
        wet
    ).all():

        raise RuntimeError(
            f"NaN/Inf: {role}"
        )


    arrays[
        role
    ] = wet.astype(
        np.float32,
        copy=False
    )


# ============================================================
# MIX
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


peak = float(
    np.max(
        np.abs(
            mix
        )
    )
)


if peak >= 1.0:

    raise RuntimeError(
        f"Hybrid clipped: {peak}"
    )


write24(
    MIX_PATH,
    mix
)


# ============================================================
# SECTION QA
# ============================================================

hybrid_sections = []


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

    for source in hybrid_sources:

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
        hybrid_scene,
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


    s_peak = float(
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
    ] = peak_score(
        s_peak
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


    original_winner = (
        section_winners[
            sid
        ]
    )


    original_winner_record = (
        selection[
            "candidates"
        ][
            original_winner
        ][
            "sections"
        ][
            next(
                i
                for i, s
                in enumerate(
                    sections
                )
                if s[
                    "section_id"
                ] == sid
            )
        ]
    )


    hybrid_sections.append({
        "section_id":
            sid,

        "source_architecture":
            original_winner,

        "hybrid_score":
            score,

        "original_winner_score":
            float(
                original_winner_record[
                    "score"
                ]
            ),

        "delta_vs_original_winner":
            score
            - float(
                original_winner_record[
                    "score"
                ]
            ),

        "components":
            components,
    })


    print(
        f"{sid} | "
        f"{original_winner:<14} | "
        f"hybrid={score:.4f}"
    )


# ============================================================
# DURATION-WEIGHTED FINAL SCORE
# ============================================================

durations = np.array(
    [
        float(
            s[
                "end_seconds"
            ]
            -
            s[
                "start_seconds"
            ]
        )
        for s in sections
    ]
)


overall = {}


for component in WEIGHTS:

    if component == "orbit_integrity":

        overall[
            component
        ] = orbit_score

        continue


    values = np.array(
        [
            s[
                "components"
            ][component]
            for s in hybrid_sections
        ]
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
] = peak_score(
    peak
)


hybrid_score = float(
    sum(
        overall[k]
        * float(
            WEIGHTS[k]
        )
        for k in WEIGHTS
    )
)


single_winner = (
    selection[
        "full_song_winner"
    ]
)


single_score = float(
    selection[
        "candidates"
    ][
        single_winner
    ][
        "score"
    ]
)


improvement = (
    hybrid_score
    -
    single_score
)


status = (
    "PASS"
    if improvement > 0
    else "FAIL"
)


report = {
    "schema":
        "LAISE TUK2 Section-Adaptive Hybrid Validation v1.0",

    "project":
        "tukana_02_a_mata_se_move",

    "test_id":
        "TUK2-T006D",

    "status":
        status,

    "section_architecture_map":
        section_winners,

    "boundary_audit":
        boundary_audit,

    "geometry":
        geometry,

    "full_mix": {
        "path":
            str(
                MIX_PATH
            ),

        "sha256":
            sha256(
                MIX_PATH
            ),

        "frames":
            FRAMES,

        "peak_dbfs":
            db(
                peak
            ),
    },

    "components":
        overall,

    "hybrid_score":
        hybrid_score,

    "best_single_architecture":
        single_winner,

    "best_single_score":
        single_score,

    "improvement":
        improvement,

    "sections":
        hybrid_sections,

    "selection_state":
        (
            "HYBRID_SELECTED_FOR_INDEPENDENT_QA"
            if status == "PASS"
            else
            "RETAIN_BEST_SINGLE_ARCHITECTURE"
        ),

    "epistemic_limit":
        (
            "Selection is based on measured technical "
            "proxies, not universal human perception."
        ),
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
    "TUK2-T006D RESULT"
)
print(
    "=================================================="
)

print(
    f"Hybrid score       : "
    f"{hybrid_score:.4f}"
)

print(
    f"Best single        : "
    f"{single_winner}"
)

print(
    f"Single score       : "
    f"{single_score:.4f}"
)

print(
    f"Improvement        : "
    f"{improvement:+.4f}"
)

print(
    f"Peak               : "
    f"{db(peak):.2f} dBFS"
)

print()
print(
    "COMPONENTS:"
)

for key in WEIGHTS:

    print(
        f"{key:<26}: "
        f"{overall[key]:.3f}"
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
    REPORT
)

print()
print(
    f"TUK2-T006D: {status}"
)

if status != "PASS":

    raise RuntimeError(
        "Section hybrid did not outperform "
        "the best complete architecture."
    )

