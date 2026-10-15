from __future__ import annotations

import json
import math
import hashlib
from pathlib import Path

import numpy as np

from stem_importer import iter_blocks, _sha256


ROOT = Path(r"C:\Projetos2026\LAISE")

PROJECT = (
    ROOT
    / "projects"
    / "tukana_02_a_mata_se_move"
)

STEMS = PROJECT / "stems_original"

T001 = (
    PROJECT
    / "analysis"
    / "TUK2_T001_immutable_intake.json"
)

T003 = (
    PROJECT
    / "analysis"
    / "TUK2_T003_structural_masking_map.json"
)

BLUEPRINT_PATH = (
    PROJECT
    / "spatial_scenes"
    / "TUK2_T004R1_blueprint.json"
)

T005B = (
    PROJECT
    / "experiments"
    / "TUK2_T005"
    / "reports"
    / "TUK2_T005B_dynamic_spatial_validation.json"
)

OUT = (
    PROJECT
    / "experiments"
    / "TUK2_T006"
)

REPORTS = OUT / "reports"
SCENES = OUT / "spatial_scenes"
ANALYSIS = OUT / "analysis"


RATE = 48000

HOP = 2400              # 50 ms
HOP_SECONDS = HOP / RATE

SMOOTH_SECONDS = 0.20
SMOOTH_BLOCKS = round(
    SMOOTH_SECONDS
    / HOP_SECONDS
)

MIN_EVENT_SECONDS = 0.30
MERGE_GAP_SECONDS = 0.40
MIN_EVENT_BLOCKS = round(
    MIN_EVENT_SECONDS
    / HOP_SECONDS
)

MERGE_GAP_BLOCKS = round(
    MERGE_GAP_SECONDS
    / HOP_SECONDS
)

DURATION = 330.0


ROLE_FILES = {
    "lead_vocal":
        "0 Lead Vocals.wav",

    "backing_vocals":
        "1 Backing Vocals.wav",

    "drums":
        "2 Drums.wav",

    "bass":
        "3 Bass.wav",

    "guitar":
        "4 Guitar.wav",

    "keyboards":
        "5 Keyboard.wav",

    "percussion":
        "6 Percussion.wav",

    "strings":
        "7 Strings.wav",

    "synth":
        "8 Synth.wav",

    "other":
        "9 Other.wav",

    "brass":
        "10 Brass.wav",

    "woodwinds":
        "11 Woodwinds.wav",
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


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(
            lambda: f.read(
                1024 * 1024
            ),
            b""
        ):
            h.update(block)

    return h.hexdigest()


def envelope(path):

    values = []

    for block in iter_blocks(
        path,
        HOP
    ):

        x = block.astype(
            np.float64
        )

        rms = float(
            np.sqrt(
                np.mean(
                    x * x
                )
            )
        )

        values.append(rms)

    values = np.asarray(
        values,
        dtype=np.float64
    )

    if SMOOTH_BLOCKS > 1:

        kernel = (
            np.ones(
                SMOOTH_BLOCKS,
                dtype=np.float64
            )
            / SMOOTH_BLOCKS
        )

        values = np.convolve(
            values,
            kernel,
            mode="same"
        )

    return values


def close_small_gaps(mask, maximum):

    mask = mask.copy()

    i = 0
    n = len(mask)

    while i < n:

        if mask[i]:
            i += 1
            continue

        start = i

        while (
            i < n
            and not mask[i]
        ):
            i += 1

        end = i

        if (
            start > 0
            and end < n
            and mask[start - 1]
            and mask[end]
            and (
                end - start
                <= maximum
            )
        ):
            mask[start:end] = True

    return mask


def boolean_regions(mask):

    regions = []

    start = None

    for i, state in enumerate(mask):

        if state and start is None:
            start = i

        elif (
            not state
            and start is not None
        ):
            regions.append(
                (start, i)
            )

            start = None

    if start is not None:
        regions.append(
            (
                start,
                len(mask)
            )
        )

    return regions


def role_activity_threshold(
    values,
    first,
    last
):
    section = values[
        first:last
    ]

    positive = section[
        section > 1e-12
    ]

    if len(positive) == 0:
        return float("inf")

    p95 = float(
        np.percentile(
            positive,
            95
        )
    )

    absolute_floor = (
        10 ** (-60 / 20)
    )

    return max(
        absolute_floor,
        p95 * 0.10
    )


def global_lead_mask(
    lead
):
    positive = lead[
        lead > 1e-12
    ]

    if len(positive) == 0:
        return np.zeros(
            len(lead),
            dtype=bool
        )

    p95 = float(
        np.percentile(
            positive,
            95
        )
    )

    threshold = max(
        10 ** (-60 / 20),
        p95 * 0.10
    )

    return (
        lead >= threshold
    )


def find_events(
    role,
    values,
    section,
    lead_mask
):

    first = max(
        0,
        round(
            section["start_seconds"]
            / HOP_SECONDS
        )
    )

    last = min(
        len(values),
        round(
            section["end_seconds"]
            / HOP_SECONDS
        )
    )

    threshold = (
        role_activity_threshold(
            values,
            first,
            last
        )
    )

    if not np.isfinite(
        threshold
    ):
        return []

    local = values[
        first:last
    ]

    active = (
        local >= threshold
    )

    active = close_small_gaps(
        active,
        MERGE_GAP_BLOCKS
    )

    regions = [
        region
        for region
        in boolean_regions(active)

        if (
            region[1]
            - region[0]
            >= MIN_EVENT_BLOCKS
        )
    ]

    if not regions:
        return []

    p95 = max(
        float(
            np.percentile(
                local,
                95
            )
        ),
        1e-12
    )

    events = []

    for r0, r1 in regions:

        a = first + r0
        b = first + r1

        segment = values[
            a:b
        ]

        if len(segment) == 0:
            continue

        peak = float(
            np.max(segment)
        )

        mean = float(
            np.mean(segment)
        )

        diff = np.maximum(
            0.0,
            np.diff(
                segment,
                prepend=segment[0]
            )
        )

        onset = float(
            np.max(diff)
        )

        lead_overlap = float(
            np.mean(
                lead_mask[
                    a:b
                ]
            )
        )

        duration = (
            (b - a)
            * HOP_SECONDS
        )

        peak_score = min(
            peak / p95,
            2.0
        )

        mean_score = min(
            mean / p95,
            1.5
        )

        onset_score = min(
            onset
            / p95
            * 8.0,
            1.5
        )

        duration_score = min(
            duration / 3.0,
            1.0
        )

        score = (
            0.40 * peak_score
            + 0.25 * mean_score
            + 0.20 * onset_score
            + 0.15 * duration_score
        )

        # Protect vocal intelligibility from
        # strong movement of competing sources.
        if role in (
            "woodwinds",
            "backing_vocals"
        ):
            score *= (
                1.0
                - 0.30
                * lead_overlap
            )

        events.append({
            "role":
                role,

            "start_seconds":
                round(
                    a
                    * HOP_SECONDS,
                    3
                ),

            "end_seconds":
                round(
                    b
                    * HOP_SECONDS,
                    3
                ),

            "duration_seconds":
                round(
                    duration,
                    3
                ),

            "peak_relative_to_section_p95":
                float(
                    peak / p95
                ),

            "mean_relative_to_section_p95":
                float(
                    mean / p95
                ),

            "lead_active_fraction":
                lead_overlap,

            "salience_score":
                float(score),
        })

    events.sort(
        key=lambda x:
            x["salience_score"],
        reverse=True
    )

    # Prevent several almost identical adjacent
    # movements from being chosen.
    chosen = []

    for event in events:

        center = (
            event["start_seconds"]
            + event["end_seconds"]
        ) / 2

        if all(
            abs(
                center
                - (
                    e["start_seconds"]
                    + e["end_seconds"]
                ) / 2
            )
            >= 1.0
            for e in chosen
        ):
            chosen.append(event)

    return chosen


def limit_events(
    events,
    section_duration
):

    if section_duration <= 12:
        maximum = 1

    elif section_duration <= 35:
        maximum = 2

    else:
        maximum = 3

    return events[:maximum]


def home_keyframe(
    t,
    az,
    el,
    reason
):
    return {
        "time_seconds":
            float(t),

        "azimuth_deg_unwrapped":
            float(az),

        "elevation_deg":
            float(el),

        "gain_db":
            0.0,

        "reason":
            reason,
    }


def candidate_parameters(
    name,
    section,
    event
):

    density = float(
        section[
            "mean_active_stem_count"
        ]
    )

    lead_overlap = float(
        event.get(
            "lead_active_fraction",
            0.0
        )
    )

    salience = float(
        event[
            "salience_score"
        ]
    )

    if name == "A_CLARITY":

        return {
            "motion_scale": 0.55,
            "event_keep_fraction": 0.40,
            "lead_scale": 0.20,
        }

    if name == "B_SEPARATION":

        return {
            "motion_scale": 0.80,
            "event_keep_fraction": 0.70,
            "lead_scale": 0.35,
        }

    if name == "C_MOTION":

        return {
            "motion_scale": 1.00,
            "event_keep_fraction": 1.00,
            "lead_scale": 0.60,
        }

    # D_ADAPTIVE
    if density <= 5:
        scale = 1.00

    elif density <= 7:
        scale = 0.88

    elif density <= 9:
        scale = 0.72

    else:
        scale = 0.60

    # Competing movement shrinks while lead is active.
    scale *= (
        1.0
        - 0.18
        * lead_overlap
    )

    # Strong isolated events retain more motion.
    scale *= min(
        1.08,
        0.85
        + 0.15
        * salience
    )

    return {
        "motion_scale":
            float(
                np.clip(
                    scale,
                    0.50,
                    1.00
                )
            ),

        "event_keep_fraction":
            0.85,

        "lead_scale":
            (
                0.55
                if density <= 5
                else (
                    0.42
                    if density <= 8
                    else 0.28
                )
            ),
    }


def movement_target(
    role,
    motion,
    home_az,
    home_el,
    az_exc,
    el_exc,
    event_index,
):

    direction = (
        1.0
        if event_index % 2 == 0
        else -1.0
    )

    target_az = home_az
    target_el = home_el

    if motion == "ELEVATION_SWEEP":

        target_az = (
            home_az
            + direction
            * min(
                az_exc,
                12.0
            )
        )

        target_el = (
            home_el
            + direction
            * el_exc
        )

    elif motion == "HIGH_SIDE_ARC":

        candidate = (
            home_az
            + direction
            * az_exc
        )

        # Never push woodwinds through
        # the frontal vocal anchor.
        if abs(candidate) < 35:
            candidate = (
                home_az
                - direction
                * az_exc
            )

        target_az = candidate

        target_el = (
            home_el
            + direction
            * min(
                el_exc,
                8.0
            )
        )

    elif motion in (
        "ARC",
        "SLOW_ARC",
        "ORBIT_SEGMENT",
        "CALL_RESPONSE",
        "SHORT_ARC",
    ):

        target_az = (
            home_az
            + direction
            * az_exc
        )

        target_el = (
            home_el
            + direction
            * min(
                el_exc,
                8.0
            )
        )

    elif motion == "POINT_EVENT":

        target_az = (
            home_az
            + direction
            * az_exc
        )

        target_el = (
            home_el
            + direction
            * el_exc
        )

    return (
        float(target_az),
        float(
            np.clip(
                target_el,
                -75,
                75
            )
        )
    )


def event_keyframes(
    role,
    motion,
    event,
    home,
    az_exc,
    el_exc,
    event_index,
):

    start = float(
        event["start_seconds"]
    )

    end = float(
        event["end_seconds"]
    )

    duration = max(
        end - start,
        0.30
    )

    attack = (
        start
        + duration * 0.30
    )

    release = (
        start
        + duration * 0.72
    )

    home_az = float(
        home["azimuth_deg"]
    )

    home_el = float(
        home["elevation_deg"]
    )

    target_az, target_el = (
        movement_target(
            role,
            motion,
            home_az,
            home_el,
            az_exc,
            el_exc,
            event_index
        )
    )

    return [
        home_keyframe(
            start,
            home_az,
            home_el,
            "Event start / home"
        ),

        home_keyframe(
            attack,
            target_az,
            target_el,
            (
                f"{motion} expressive target"
            )
        ),

        home_keyframe(
            release,
            target_az,
            target_el,
            (
                f"{motion} hold"
            )
        ),

        home_keyframe(
            end,
            home_az,
            home_el,
            "RETURN_HOME"
        ),
    ]


def lead_events_for_section(
    lead_values,
    section,
    lead_mask
):

    pseudo = {
        "start_seconds":
            section[
                "start_seconds"
            ],

        "end_seconds":
            section[
                "end_seconds"
            ]
    }

    events = find_events(
        "lead_vocal",
        lead_values,
        pseudo,
        lead_mask
    )

    return limit_events(
        events,
        float(
            section[
                "end_seconds"
            ]
            - section[
                "start_seconds"
            ]
        )
    )


def dedupe_keyframes(
    keyframes
):

    ordered = sorted(
        keyframes,
        key=lambda x:
            x["time_seconds"]
    )

    result = []

    for item in ordered:

        if (
            result
            and abs(
                result[-1][
                    "time_seconds"
                ]
                - item[
                    "time_seconds"
                ]
            )
            < 1e-6
        ):
            # Event keyframe takes precedence over
            # an earlier static one at same time.
            result[-1] = item

        else:
            result.append(item)

    return result


# ============================================================
# PREREQUISITES
# ============================================================

if OUT.exists():
    raise RuntimeError(
        "TUK2_T006 already exists. "
        "Preserving previous evidence."
    )

for path in (
    T001,
    T003,
    BLUEPRINT_PATH,
    T005B,
):
    if not path.exists():
        raise RuntimeError(
            f"Missing prerequisite: {path}"
        )

t001 = load(T001)
t003 = load(T003)
blueprint = load(
    BLUEPRINT_PATH
)
t005b = load(T005B)

if (
    t001["status"] != "PASS"
    or
    t003["status"] != "PASS"
    or
    blueprint["status"] != "PASS"
    or
    t005b["status"] != "PASS"
):
    raise RuntimeError(
        "Previous validation did not PASS."
    )


REPORTS.mkdir(
    parents=True,
    exist_ok=False
)

SCENES.mkdir(
    parents=True,
    exist_ok=False
)

ANALYSIS.mkdir(
    parents=True,
    exist_ok=False
)


print()
print(
    "=================================================="
)
print(
    "TUK2-T006A - MUSICAL EVENT MAP & CANDIDATE SCENES"
)
print(
    "=================================================="
)


# ============================================================
# VERIFY ORIGINAL STEMS
# ============================================================

for role, filename in ROLE_FILES.items():

    path = STEMS / filename

    expected = (
        t001["stems"][
            filename
        ]["sha256"]
    )

    current = _sha256(path)

    if current != expected:
        raise RuntimeError(
            f"Stem integrity failure: {role}"
        )


# ============================================================
# ENVELOPES
# ============================================================

envelopes = {}

for i, (
    role,
    filename
) in enumerate(
    ROLE_FILES.items(),
    1
):

    print(
        f"[{i:02}/12] Envelope: {role}"
    )

    envelopes[role] = envelope(
        STEMS / filename
    )


lengths = {
    len(v)
    for v in envelopes.values()
}

if len(lengths) != 1:
    raise RuntimeError(
        "Envelope lengths differ."
    )

lead_mask = global_lead_mask(
    envelopes["lead_vocal"]
)


# ============================================================
# EVENT POOL FROM BLUEPRINT
# ============================================================

sections_by_id = {
    s["section_id"]: s
    for s in t003["sections"]
}

event_map = []

for assignment in blueprint[
    "sections"
]:

    section = sections_by_id[
        assignment["section_id"]
    ]

    duration = (
        float(
            section["end_seconds"]
        )
        - float(
            section["start_seconds"]
        )
    )

    movement_entries = []

    for movement in assignment[
        "large_motion_objects"
    ]:

        role = movement["role"]

        events = find_events(
            role,
            envelopes[role],
            section,
            lead_mask
        )

        events = limit_events(
            events,
            duration
        )

        movement_entries.append({
            "role":
                role,

            "motion_class":
                movement[
                    "motion_class"
                ],

            "azimuth_excursion_deg":
                movement[
                    "azimuth_excursion_deg"
                ],

            "elevation_excursion_deg":
                movement.get(
                    "elevation_excursion_deg",
                    0.0
                ),

            "events":
                events,
        })

    lead_events = (
        lead_events_for_section(
            envelopes[
                "lead_vocal"
            ],
            section,
            lead_mask
        )
    )

    event_map.append({
        "section_id":
            section[
                "section_id"
            ],

        "start_seconds":
            section[
                "start_seconds"
            ],

        "end_seconds":
            section[
                "end_seconds"
            ],

        "mean_density":
            section[
                "mean_active_stem_count"
            ],

        "large_motion_budget":
            assignment[
                "large_motion_budget"
            ],

        "movement_entries":
            movement_entries,

        "lead_behavior":
            assignment[
                "lead_behavior"
            ],

        "lead_phrase_events":
            lead_events,
    })


# ============================================================
# CANDIDATE SCENES
# ============================================================

CANDIDATES = [
    "A_CLARITY",
    "B_SEPARATION",
    "C_MOTION",
    "D_ADAPTIVE",
]

candidate_reports = {}


for candidate_name in CANDIDATES:

    sources = []

    selected_event_count = 0

    for role, filename in (
        ROLE_FILES.items()
    ):

        policy = blueprint[
            "roles"
        ][role]

        home = policy["home"]

        keyframes = [
            home_keyframe(
                0.0,
                home["azimuth_deg"],
                home["elevation_deg"],
                "HOME"
            ),

            home_keyframe(
                DURATION,
                home["azimuth_deg"],
                home["elevation_deg"],
                "HOME END"
            ),
        ]

        role_events = []

        # ----------------------------------------------------
        # LARGE-MOTION OBJECT EVENTS
        # ----------------------------------------------------

        for section_record in event_map:

            section = sections_by_id[
                section_record[
                    "section_id"
                ]
            ]

            for entry in section_record[
                "movement_entries"
            ]:

                if entry["role"] != role:
                    continue

                all_events = entry[
                    "events"
                ]

                if not all_events:
                    continue

                params = (
                    candidate_parameters(
                        candidate_name,
                        section,
                        all_events[0]
                    )
                )

                keep = max(
                    1,
                    round(
                        len(all_events)
                        * params[
                            "event_keep_fraction"
                        ]
                    )
                )

                selected = (
                    all_events[:keep]
                )

                for event_index, event in enumerate(
                    selected
                ):

                    params = (
                        candidate_parameters(
                            candidate_name,
                            section,
                            event
                        )
                    )

                    az = (
                        float(
                            entry[
                                "azimuth_excursion_deg"
                            ]
                        )
                        * params[
                            "motion_scale"
                        ]
                    )

                    el = (
                        float(
                            entry[
                                "elevation_excursion_deg"
                            ]
                        )
                        * params[
                            "motion_scale"
                        ]
                    )

                    # Never exceed role policy.
                    az = min(
                        az,
                        float(
                            policy.get(
                                "max_azimuth_excursion_deg",
                                az
                            )
                        )
                    )

                    el = min(
                        el,
                        float(
                            policy.get(
                                "max_elevation_excursion_deg",
                                el
                            )
                        )
                    )

                    keys = event_keyframes(
                        role,
                        entry[
                            "motion_class"
                        ],
                        event,
                        home,
                        az,
                        el,
                        event_index
                    )

                    keyframes.extend(
                        keys
                    )

                    selected_event_count += 1

                    role_events.append({
                        "section_id":
                            section_record[
                                "section_id"
                            ],

                        "motion_class":
                            entry[
                                "motion_class"
                            ],

                        "event":
                            event,

                        "azimuth_excursion_deg":
                            az,

                        "elevation_excursion_deg":
                            el,
                    })


        # ----------------------------------------------------
        # LEAD VOCAL — PROTECTED MOBILE ANCHOR
        # ----------------------------------------------------

        if role == "lead_vocal":

            lead_event_index = 0

            for section_record in event_map:

                behavior = (
                    section_record[
                        "lead_behavior"
                    ]
                )

                if not behavior:
                    continue

                section = sections_by_id[
                    section_record[
                        "section_id"
                    ]
                ]

                events = (
                    section_record[
                        "lead_phrase_events"
                    ]
                )

                if not events:
                    continue

                # One controlled lead phrase movement
                # per structural section is enough.
                event = events[0]

                params = (
                    candidate_parameters(
                        candidate_name,
                        section,
                        event
                    )
                )

                az = (
                    float(
                        behavior[
                            "azimuth_excursion_deg"
                        ]
                    )
                    * params[
                        "lead_scale"
                    ]
                )

                az = min(
                    az,
                    18.0
                )

                el = min(
                    float(
                        behavior[
                            "elevation_excursion_deg"
                        ]
                    )
                    * params[
                        "lead_scale"
                    ],
                    6.0
                )

                keys = event_keyframes(
                    role,
                    "ARC",
                    event,
                    home,
                    az,
                    el,
                    lead_event_index
                )

                keyframes.extend(
                    keys
                )

                lead_event_index += 1

                role_events.append({
                    "section_id":
                        section_record[
                            "section_id"
                        ],

                    "motion_class":
                        "PROTECTED_SMALL_ARC",

                    "event":
                        event,

                    "azimuth_excursion_deg":
                        az,

                    "elevation_excursion_deg":
                        el,
                })


        keyframes = dedupe_keyframes(
            keyframes
        )

        sources.append({
            "source_id":
                role,

            "input_file":
                str(
                    STEMS
                    / filename
                ),

            "input_sha256":
                t001["stems"][
                    filename
                ]["sha256"],

            "class":
                policy["class"],

            "home":
                home,

            "gain_db":
                0.0,

            "keyframes":
                keyframes,

            # Keep depth ordering fixed for candidate
            # comparison. No near-field score bonus.
            "distance_keyframes": [
                {
                    "time_seconds":
                        0.0,

                    "distance_m":
                        float(
                            home[
                                "distance_m"
                            ]
                        ),
                },

                {
                    "time_seconds":
                        DURATION,

                    "distance_m":
                        float(
                            home[
                                "distance_m"
                            ]
                        ),
                },
            ],

            "growth_reference_distance_m":
                float(
                    home[
                        "distance_m"
                    ]
                ),

            "selected_motion_events":
                role_events,
        })


    scene = {
        "schema":
            "LAISE TUK2 Candidate Scene v1.0",

        "project":
            "tukana_02_a_mata_se_move",

        "test_id":
            "TUK2-T006A",

        "candidate":
            candidate_name,

        "duration_seconds":
            DURATION,

        "status":
            "GENERATED_NOT_YET_VALIDATED",

        "source_blueprint":
            str(
                BLUEPRINT_PATH
            ),

        "source_blueprint_sha256":
            sha256_file(
                BLUEPRINT_PATH
            ),

        "technical_360_validation":
            "TUK2-T005B PASS",

        "principles": {
            "event_gated_motion":
                True,

            "return_home":
                True,

            "lead_is_protected_mobile_anchor":
                True,

            "lead_rear_motion":
                False,

            "fixed_candidate_depth_order":
                True,

            "distance_nearfield_bonus":
                False,

            "reflection":
                False,

            "reverb":
                False,

            "T018_logic":
                False,
        },

        "sources":
            sources,
    }

    path = (
        SCENES
        / f"TUK2_T006A_{candidate_name}.json"
    )

    dump(
        path,
        scene
    )

    candidate_reports[
        candidate_name
    ] = {
        "scene":
            str(path),

        "scene_sha256":
            sha256_file(path),

        "selected_large_motion_event_count":
            selected_event_count,

        "keyframe_count":
            sum(
                len(
                    source[
                        "keyframes"
                    ]
                )
                for source in sources
            ),
    }


# ============================================================
# OBJECTIVE PREVIEW WINDOW SELECTION
# ============================================================

all_motion_events = []

for section in event_map:

    for entry in section[
        "movement_entries"
    ]:

        for event in entry[
            "events"
        ]:

            all_motion_events.append({
                **event,

                "section_id":
                    section[
                        "section_id"
                    ],

                "mean_density":
                    section[
                        "mean_density"
                    ],

                "motion_class":
                    entry[
                        "motion_class"
                    ],
            })


preview_candidates = []


# Strongest event
if all_motion_events:

    strongest = max(
        all_motion_events,
        key=lambda x:
            x[
                "salience_score"
            ]
    )

    preview_candidates.append({
        "reason":
            "strongest_spatial_event",

        "center":
            (
                strongest[
                    "start_seconds"
                ]
                + strongest[
                    "end_seconds"
                ]
            ) / 2
    })


# Lowest-density section
lowest = min(
    event_map,
    key=lambda x:
        x["mean_density"]
)

preview_candidates.append({
    "reason":
        "lowest_density",

    "center":
        (
            lowest[
                "start_seconds"
            ]
            + lowest[
                "end_seconds"
            ]
        ) / 2
})


# Highest-density section
highest = max(
    event_map,
    key=lambda x:
        x["mean_density"]
)

preview_candidates.append({
    "reason":
        "highest_density",

    "center":
        (
            highest[
                "start_seconds"
            ]
            + highest[
                "end_seconds"
            ]
        ) / 2
})


# Strongest brass event if available
brass_events = [
    x
    for x in all_motion_events
    if x["role"] == "brass"
]

if brass_events:

    brass = max(
        brass_events,
        key=lambda x:
            x[
                "salience_score"
            ]
    )

    preview_candidates.append({
        "reason":
            "sparse_brass_point_event",

        "center":
            (
                brass[
                    "start_seconds"
                ]
                + brass[
                    "end_seconds"
                ]
            ) / 2
    })


# Late-song / dissolution behavior
preview_candidates.append({
    "reason":
        "late_song_behavior",

    "center":
        310.0
})


PREVIEW_DURATION = 20.0

preview_windows = []

for candidate in preview_candidates:

    center = float(
        candidate["center"]
    )

    start = max(
        0.0,
        min(
            center
            - PREVIEW_DURATION / 2,
            DURATION
            - PREVIEW_DURATION
        )
    )

    end = (
        start
        + PREVIEW_DURATION
    )

    # Avoid redundant overlapping windows.
    if any(
        min(
            end,
            w["end_seconds"]
        )
        - max(
            start,
            w["start_seconds"]
        )
        > PREVIEW_DURATION * 0.60
        for w in preview_windows
    ):
        continue

    preview_windows.append({
        "window_id":
            f"preview_{len(preview_windows)+1:02}",

        "reason":
            candidate[
                "reason"
            ],

        "start_seconds":
            round(
                start,
                3
            ),

        "end_seconds":
            round(
                end,
                3
            ),

        "duration_seconds":
            PREVIEW_DURATION,
    })

    if len(
        preview_windows
    ) >= 4:
        break


# ============================================================
# REPORTS
# ============================================================

event_report = {
    "schema":
        "LAISE TUK2 Musical Event Map v1.0",

    "project":
        "tukana_02_a_mata_se_move",

    "test_id":
        "TUK2-T006A-EVENTS",

    "status":
        "PASS",

    "hop_seconds":
        HOP_SECONDS,

    "smoothing_seconds":
        SMOOTH_SECONDS,

    "minimum_event_seconds":
        MIN_EVENT_SECONDS,

    "merge_gap_seconds":
        MERGE_GAP_SECONDS,

    "event_detection_policy":
        (
            "Section-relative RMS activity, "
            "gap merging, minimum duration, "
            "salience ranking and lead-overlap "
            "protection for competing movers."
        ),

    "sections":
        event_map,

    "preview_windows":
        preview_windows,

    "limits": [
        (
            "Events are objective signal regions, "
            "not semantic claims about specific "
            "notes, words or instruments."
        ),

        (
            "Separator role labels are retained "
            "without assuming exact source identity."
        ),

        (
            "Movement eligibility does not imply "
            "continuous movement."
        ),
    ],
}

dump(
    ANALYSIS
    / "TUK2_T006A_musical_event_map.json",
    event_report
)


summary = {
    "schema":
        "LAISE TUK2 Candidate Scene Generation v1.0",

    "project":
        "tukana_02_a_mata_se_move",

    "test_id":
        "TUK2-T006A",

    "status":
        "PASS",

    "candidate_count":
        4,

    "candidates":
        candidate_reports,

    "preview_windows":
        preview_windows,

    "next_stage":
        (
            "Render identical windows from all "
            "four candidates and score objective "
            "spatial discriminability, clarity, "
            "orbit/trajectory integrity, front/back, "
            "elevation, transient preservation, "
            "peak safety and mono stability."
        ),
}

dump(
    REPORTS
    / "TUK2_T006A_summary.json",
    summary
)


# ============================================================
# TERMINAL SUMMARY
# ============================================================

print()
print(
    "=================================================="
)
print(
    "EVENT-GATED MOTION MAP"
)
print(
    "=================================================="
)

for section in event_map:

    texts = []

    for entry in section[
        "movement_entries"
    ]:

        texts.append(
            f"{entry['role']}:"
            f"{len(entry['events'])}"
        )

    print(
        f"{section['section_id']} "
        f"{section['start_seconds']:6.1f}-"
        f"{section['end_seconds']:6.1f}s | "
        f"{', '.join(texts) if texts else 'no mover'} | "
        f"lead phrases="
        f"{len(section['lead_phrase_events'])}"
    )


print()
print(
    "=================================================="
)
print(
    "CANDIDATE SCENES"
)
print(
    "=================================================="
)

for name, item in (
    candidate_reports.items()
):

    print(
        f"{name:<14} | "
        f"events="
        f"{item['selected_large_motion_event_count']:3d} | "
        f"keyframes="
        f"{item['keyframe_count']:4d}"
    )


print()
print(
    "=================================================="
)
print(
    "OBJECTIVE PREVIEW WINDOWS"
)
print(
    "=================================================="
)

for window in preview_windows:

    print(
        f"{window['window_id']} | "
        f"{window['start_seconds']:6.1f}-"
        f"{window['end_seconds']:6.1f}s | "
        f"{window['reason']}"
    )


print()
print(
    "Event map:"
)
print(
    ANALYSIS
    / "TUK2_T006A_musical_event_map.json"
)

print()
print(
    "Summary:"
)
print(
    REPORTS
    / "TUK2_T006A_summary.json"
)

print()
print(
    "TUK2-T006A: PASS"
)

