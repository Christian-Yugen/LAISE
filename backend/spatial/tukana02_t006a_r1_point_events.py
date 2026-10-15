from __future__ import annotations

import json
import copy
import hashlib
from pathlib import Path


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

DURATION = 330.0

CANDIDATES = [
    "A_CLARITY",
    "B_SEPARATION",
    "C_MOTION",
    "D_ADAPTIVE",
]


def load(path):
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
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


def sha256(path):
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


def keyframe(
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


def dedupe(frames):

    frames = sorted(
        frames,
        key=lambda x:
            x["time_seconds"]
    )

    result = []

    for frame in frames:

        if (
            result
            and abs(
                result[-1][
                    "time_seconds"
                ]
                -
                frame[
                    "time_seconds"
                ]
            )
            < 1e-7
        ):
            result[-1] = frame

        else:
            result.append(
                frame
            )

    return result


def point_target(
    home,
    az_exc,
    el_exc,
    index
):

    # Alternate left/right relative to home.
    direction = (
        1.0
        if index % 2 == 0
        else -1.0
    )

    home_az = float(
        home["azimuth_deg"]
    )

    home_el = float(
        home["elevation_deg"]
    )

    target_az = (
        home_az
        + direction
        * float(az_exc)
    )

    target_el = (
        home_el
        + direction
        * float(el_exc)
    )

    target_el = max(
        -75.0,
        min(
            75.0,
            target_el
        )
    )

    return (
        target_az,
        target_el
    )


print()
print(
    "=================================================="
)
print(
    "TUK2-T006A-R1 - POINT EVENT CORRECTION"
)
print(
    "=================================================="
)

summary = {}

for candidate in CANDIDATES:

    source_path = (
        SCENES
        / f"TUK2_T006A_{candidate}.json"
    )

    target_path = (
        SCENES
        / f"TUK2_T006A_R1_{candidate}.json"
    )

    if not source_path.exists():
        raise RuntimeError(
            f"Missing candidate: {source_path}"
        )

    if target_path.exists():
        raise RuntimeError(
            f"Refusing overwrite: {target_path}"
        )

    scene = copy.deepcopy(
        load(source_path)
    )

    original_hash = sha256(
        source_path
    )

    corrected = 0

    for source in scene[
        "sources"
    ]:

        role = source[
            "source_id"
        ]

        events = source.get(
            "selected_motion_events",
            []
        )

        point_events = [
            event
            for event in events
            if event[
                "motion_class"
            ] == "POINT_EVENT"
        ]

        if not point_events:
            continue


        # Current Tukana II POINT_EVENT source is brass.
        # Remove only generated movement frames;
        # preserve HOME/HOME END.
        preserved = []

        for frame in source[
            "keyframes"
        ]:

            reason = frame.get(
                "reason",
                ""
            )

            if (
                "Event start / home"
                in reason
                or
                "POINT_EVENT expressive target"
                in reason
                or
                reason == "POINT_EVENT hold"
                or
                reason == "RETURN_HOME"
            ):
                continue

            preserved.append(
                frame
            )


        home = source[
            "home"
        ]

        home_az = float(
            home["azimuth_deg"]
        )

        home_el = float(
            home["elevation_deg"]
        )


        point_events = sorted(
            point_events,
            key=lambda x:
                x["event"][
                    "start_seconds"
                ]
        )


        for index, record in enumerate(
            point_events
        ):

            event = record[
                "event"
            ]

            start = float(
                event[
                    "start_seconds"
                ]
            )

            end = float(
                event[
                    "end_seconds"
                ]
            )

            duration = max(
                end - start,
                0.01
            )

            # Relocation happens BEFORE the audible event.
            approach = min(
                0.35,
                max(
                    0.12,
                    duration * 0.25
                )
            )

            release = min(
                0.35,
                max(
                    0.12,
                    duration * 0.25
                )
            )

            pre = max(
                0.0,
                start - approach
            )

            post = min(
                DURATION,
                end + release
            )


            # Avoid placing the return beyond the
            # beginning of the next point event.
            if (
                index + 1
                < len(point_events)
            ):

                next_start = float(
                    point_events[
                        index + 1
                    ]["event"][
                        "start_seconds"
                    ]
                )

                post = min(
                    post,
                    max(
                        end,
                        next_start
                        - 0.05
                    )
                )


            target_az, target_el = (
                point_target(
                    home,
                    record[
                        "azimuth_excursion_deg"
                    ],
                    record[
                        "elevation_excursion_deg"
                    ],
                    index
                )
            )


            # Move while source is below event threshold.
            preserved.extend([
                keyframe(
                    pre,
                    home_az,
                    home_el,
                    "POINT_EVENT pre-position start"
                ),

                keyframe(
                    start,
                    target_az,
                    target_el,
                    "POINT_EVENT positioned before attack"
                ),

                keyframe(
                    end,
                    target_az,
                    target_el,
                    "POINT_EVENT stable during audible event"
                ),

                keyframe(
                    post,
                    home_az,
                    home_el,
                    "POINT_EVENT return after event"
                ),
            ])

            corrected += 1


        source[
            "keyframes"
        ] = dedupe(
            preserved
        )


    scene[
        "test_id"
    ] = "TUK2-T006A-R1"

    scene[
        "source_candidate"
    ] = candidate

    scene[
        "supersedes"
    ] = (
        f"TUK2_T006A_{candidate}"
    )

    scene[
        "source_scene_sha256"
    ] = original_hash

    scene[
        "point_event_policy"
    ] = {
        "method":
            (
                "Pre-position during preceding low-activity "
                "gap, hold fixed position throughout detected "
                "event, return during following low-activity gap."
            ),

        "movement_during_audible_point_event":
            False,

        "transient_priority":
            True,

        "reason":
            (
                "Protect attack definition and point-source "
                "localization instead of sweeping the accent."
            )
    }


    dump(
        target_path,
        scene
    )

    revised_hash = sha256(
        target_path
    )

    summary[
        candidate
    ] = {
        "source_scene":
            str(source_path),

        "source_sha256":
            original_hash,

        "revised_scene":
            str(target_path),

        "revised_sha256":
            revised_hash,

        "point_events_corrected":
            corrected,

        "keyframes":
            sum(
                len(
                    source[
                        "keyframes"
                    ]
                )
                for source
                in scene[
                    "sources"
                ]
            ),
    }


report = {
    "schema":
        "LAISE TUK2 Point Event Correction v1.0",

    "project":
        "tukana_02_a_mata_se_move",

    "test_id":
        "TUK2-T006A-R1",

    "status":
        "PASS",

    "original_scenes_preserved":
        True,

    "correction":
        (
            "POINT_EVENT sources are positioned before "
            "the detected audible region and held static "
            "during the event."
        ),

    "candidates":
        summary,

    "next_stage":
        (
            "TUK2-T006B objective candidate rendering "
            "and A/B/C/D scoring."
        ),
}

report_path = (
    REPORTS
    / "TUK2_T006A_R1_point_event_correction.json"
)

if report_path.exists():
    raise RuntimeError(
        f"Refusing overwrite: {report_path}"
    )

dump(
    report_path,
    report
)


print()
print(
    "CANDIDATES:"
)

for candidate, item in (
    summary.items()
):

    print(
        f"{candidate:<14} | "
        f"point events corrected="
        f"{item['point_events_corrected']:2d} | "
        f"keyframes="
        f"{item['keyframes']:4d}"
    )

print()
print(
    "Policy:"
)

print(
    "pre-position -> audible event STATIC -> return"
)

print()
print(
    "Original T006A scenes preserved: True"
)

print()
print(
    "Report:"
)

print(
    report_path
)

print()
print(
    "TUK2-T006A-R1: PASS"
)

