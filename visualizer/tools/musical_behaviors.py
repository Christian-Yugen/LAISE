from __future__ import annotations

import math
from collections import Counter
from typing import Any, Iterable

SCHEMA = "laise-musical-behaviors-v1"
VERSION = "1.3C.0-lab"

TREND_TYPES = {"CRESCENDO", "DECRESCENDO"}

SEQUENCE_TYPES = {
    "REPEATED_PULSE",
    "REPEATED_PULSE_SEQUENCE",
    "ACCELERATING_SEQUENCE",
    "DECELERATING_SEQUENCE",
}

SUSTAIN_TYPES = {
    "SUSTAINED_TONE",
    "SUSTAINED_TEXTURE",
}

CONTEXT_ONLY_TYPES = {"PHRASE"}


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    return number if math.isfinite(number) else default


def _bounded_ratio(value: float) -> float:
    value = max(0.0, _finite(value))
    return value / (1.0 + value)


def _unique_sorted(values: Iterable[Any]) -> list[Any]:
    return sorted(set(values))


def _trajectory_from_gestures(
    gestures: list[dict[str, Any]],
    start: float,
    end: float,
) -> list[dict[str, float]]:

    by_time: dict[float, dict[str, float]] = {}

    for gesture in gestures:
        for point in gesture.get("trajectory") or []:

            t = _finite(point.get("time"), float("nan"))

            if (
                not math.isfinite(t)
                or t < start - 1e-6
                or t > end + 1e-6
            ):
                continue

            by_time[round(t, 6)] = {
                "time": round(t, 6),
                "x": round(_finite(point.get("x")), 6),
                "z": round(_finite(point.get("z")), 6),
                "azimuth": round(
                    _finite(point.get("azimuth")),
                    6,
                ),
                "elevation": round(
                    _finite(point.get("elevation")),
                    6,
                ),
                "distance": round(
                    _finite(point.get("distance")),
                    6,
                ),
            }

    return [
        by_time[key]
        for key in sorted(by_time)
    ]


def _trajectory_from_cues(
    cues: list[dict[str, Any]],
) -> list[dict[str, float]]:

    by_time: dict[float, dict[str, float]] = {}

    for cue in cues:
        t = round(_finite(cue.get("time")), 6)

        by_time[t] = {
            "time": t,
            "x": round(_finite(cue.get("x")), 6),
            "z": round(_finite(cue.get("z")), 6),
        }

    return [
        by_time[key]
        for key in sorted(by_time)
    ]


def _max_planar_displacement(
    points: list[dict[str, float]],
) -> float:

    if len(points) < 2:
        return 0.0

    x0 = points[0]["x"]
    z0 = points[0]["z"]

    return max(
        math.hypot(
            point["x"] - x0,
            point["z"] - z0,
        )
        for point in points[1:]
    )


def _primitive(
    temporal: str,
    gesture_types: set[str],
) -> str:

    if "TREMOLO_OR_ROLL" in gesture_types:
        return "ROLL_RESONANCE"

    if (
        temporal == "repeated"
        or gesture_types.intersection(SEQUENCE_TYPES)
    ):
        return "PULSE_SEQUENCE"

    if (
        temporal == "sustained"
        or gesture_types.intersection(SUSTAIN_TYPES)
    ):
        return "SUSTAINED_EXCITATION"

    return "IMPULSE"


def _trend_modifiers(
    gestures: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    result = []

    for gesture in gestures:

        kind = gesture.get("gestureType")

        if kind not in TREND_TYPES:
            continue

        evidence = gesture.get("evidence") or {}

        result.append({
            "gestureId": gesture.get("gestureId"),
            "type": kind,
            "startTime": _finite(
                gesture.get("startTime")
            ),
            "peakTime": _finite(
                gesture.get("peakTime")
            ),
            "endTime": _finite(
                gesture.get("endTime")
            ),
            "energyChangeDb": _finite(
                evidence.get("energyChangeDb"),
                _finite(gesture.get("trend")),
            ),
            "energyTimeCorrelation": _finite(
                evidence.get(
                    "energyTimeCorrelation"
                )
            ),
            "application":
                "MEASURED_EVIDENCE_MODIFIER",
        })

    return result


def _rhythm_modifiers(
    gestures: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    result = []

    for gesture in gestures:

        kind = gesture.get("gestureType")

        if (
            kind not in SEQUENCE_TYPES
            and kind != "TREMOLO_OR_ROLL"
        ):
            continue

        evidence = gesture.get("evidence") or {}

        result.append({
            "gestureId": gesture.get("gestureId"),
            "type": kind,
            "startTime": _finite(
                gesture.get("startTime")
            ),
            "endTime": _finite(
                gesture.get("endTime")
            ),
            "rateHz": _finite(
                evidence.get("rateHz"),
                _finite(
                    gesture.get("repetitionRate")
                ),
            ),
            "ioiSeconds": [
                _finite(value)
                for value in (
                    evidence.get("ioiSeconds")
                    or []
                )
            ],
            "ioiTrendCorrelation": _finite(
                evidence.get(
                    "ioiTrendCorrelation"
                ),
                _finite(gesture.get("trend")),
            ),
            "application":
                "PRESERVE_MEASURED_ATTACK_TIMING",
        })

    return result


def _drive_components(
    intent: dict[str, Any],
    gestures: list[dict[str, Any]],
    primitive: str,
) -> dict[str, float]:

    absolute = max(
        0.0,
        _finite(
            intent.get("absoluteIntensity")
        ),
    )

    track_relative = max(
        0.0,
        _finite(
            intent.get("trackRelativeIntensity")
        ),
    )

    local_context = max(
        0.0,
        _finite(
            intent.get("localContextIntensity")
        ),
    )

    salience = max(
        0.0,
        _finite(
            intent.get("musicalSalience")
        ),
    )

    attack_strength = max(
        [
            max(
                0.0,
                _finite(
                    gesture.get("attackStrength")
                ),
            )
            for gesture in gestures
        ]
        or [0.0]
    )

    sustain_strength = max(
        [
            max(
                0.0,
                _finite(
                    gesture.get("sustainStrength")
                ),
            )
            for gesture in gestures
        ]
        or [0.0]
    )

    if primitive in {
        "IMPULSE",
        "PULSE_SEQUENCE",
        "ROLL_RESONANCE",
    }:
        evidence_intensity = max(
            absolute,
            attack_strength,
        )
    else:
        evidence_intensity = max(
            absolute,
            sustain_strength,
        )

    # Absolute musical evidence remains the amplitude anchor.
    # These modifiers are bounded and continuous.
    # roleCode is intentionally excluded.

    salience_factor = (
        1.0
        + 0.25 * _bounded_ratio(salience)
    )

    context_factor = (
        1.0
        + 0.10 * _bounded_ratio(
            local_context
        )
    )

    track_factor = (
        1.0
        + 0.10 * _bounded_ratio(
            track_relative
        )
    )

    physical_drive = (
        evidence_intensity
        * salience_factor
        * context_factor
        * track_factor
    )

    return {
        "absoluteIntensity": absolute,
        "attackStrength": attack_strength,
        "sustainStrength": sustain_strength,
        "trackRelativeIntensity":
            track_relative,
        "localContextIntensity":
            local_context,
        "musicalSalience": salience,
        "evidenceIntensity":
            evidence_intensity,
        "salienceFactor":
            salience_factor,
        "localContextFactor":
            context_factor,
        "trackContextFactor":
            track_factor,
        "physicalDrive":
            physical_drive,
    }


def build_behaviors(
    gestures_payload: dict[str, Any],
    intents_payload: dict[str, Any],
    cues_payload: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
]:

    gestures = gestures_payload["gestures"]
    intents = intents_payload["intents"]
    cues = cues_payload["events"]

    gesture_by_id = {
        gesture["gestureId"]: gesture
        for gesture in gestures
    }

    behaviors = []

    missing_gesture_refs = []
    invalid_attack_refs = []

    for ordinal, intent in enumerate(intents):

        intent_id = intent["intentId"]
        source = intent["source"]

        start = _finite(
            intent.get("startTime")
        )

        end = _finite(
            intent.get("endTime"),
            start,
        )

        duration = max(
            0.0,
            end - start,
        )

        refs = list(
            intent.get("gestureRefs")
            or []
        )

        linked_gestures = []

        for ref in refs:

            gesture = gesture_by_id.get(ref)

            if gesture is None:
                missing_gesture_refs.append(
                    (intent_id, ref)
                )
                continue

            linked_gestures.append(
                gesture
            )

        gesture_types = {
            gesture.get("gestureType")
            for gesture in linked_gestures
            if gesture.get("gestureType")
        }

        primitive = _primitive(
            str(
                intent.get(
                    "temporalBehavior"
                )
                or ""
            ),
            gesture_types,
        )

        attack_events = []
        linked_cues = []

        for ref in (
            intent.get("attackRefs")
            or []
        ):

            if (
                not isinstance(ref, int)
                or ref < 0
                or ref >= len(cues)
            ):
                invalid_attack_refs.append(
                    (intent_id, ref)
                )
                continue

            cue = cues[ref]

            linked_cues.append(cue)

            attack_events.append({
                "attackRef": ref,
                "time": _finite(
                    cue.get("time")
                ),
                "x": _finite(
                    cue.get("x")
                ),
                "z": _finite(
                    cue.get("z")
                ),
                "strength": _finite(
                    cue.get("strength")
                ),
                "width": _finite(
                    cue.get("width")
                ),
            })

        trajectory = (
            _trajectory_from_gestures(
                linked_gestures,
                start,
                end,
            )
        )

        trajectory_source = (
            "V1.3A_GESTURE_T007"
        )

        if (
            not trajectory
            and linked_cues
        ):
            trajectory = (
                _trajectory_from_cues(
                    linked_cues
                )
            )

            trajectory_source = (
                "V1.2_CUE_T007_FALLBACK"
            )

        if not trajectory:
            trajectory_source = (
                "NO_SPATIAL_SAMPLES"
            )

        displacement = (
            _max_planar_displacement(
                trajectory
            )
        )

        has_motion_gesture = (
            "CONTINUOUS_MOTION"
            in gesture_types
        )

        spatial_mode = (
            "MOVING_SOURCE"
            if (
                has_motion_gesture
                or displacement > 0.01
            )
            else "STATIC_SOURCE"
        )

        drive = _drive_components(
            intent,
            linked_gestures,
            primitive,
        )

        physical_drive = (
            drive["physicalDrive"]
        )

        if (
            primitive
            == "SUSTAINED_EXCITATION"
        ):
            feed_mode = (
                "CONTINUOUS_WHILE_CAUSAL"
            )

        elif (
            primitive
            == "ROLL_RESONANCE"
        ):
            feed_mode = (
                "COHERENT_RAPID_REINFORCEMENT"
            )

        elif (
            primitive
            == "PULSE_SEQUENCE"
        ):
            feed_mode = (
                "ATTACK_TIMED_REINFORCEMENT"
            )

        else:
            feed_mode = "SINGLE_ATTACK"

        context_gestures = sorted(
            gesture["gestureId"]
            for gesture in linked_gestures
            if (
                gesture.get("gestureType")
                in CONTEXT_ONLY_TYPES
            )
        )

        behaviors.append({
            "behaviorId":
                f"b{ordinal:05d}",

            "intentId":
                intent_id,

            "source":
                source,

            "startTime":
                start,

            "endTime":
                end,

            "duration":
                duration,

            "primitive":
                primitive,

            "feedMode":
                feed_mode,

            "temporalBehavior":
                intent.get(
                    "temporalBehavior"
                ),

            "spatialBehavior": {
                "mode":
                    spatial_mode,

                "trajectorySource":
                    trajectory_source,

                "maxPlanarDisplacement":
                    displacement,

                "trajectory":
                    trajectory,

                "elevationPolicy":
                    "METADATA_ONLY_NOT_MESH_Y",
            },

            "drive": {
                **drive,

                "feedDurationSeconds":
                    duration
                    if primitive in {
                        "SUSTAINED_EXCITATION",
                        "ROLL_RESONANCE",
                    }
                    else 0.0,

                "integratedDriveCandidate":
                    physical_drive * duration
                    if primitive in {
                        "SUSTAINED_EXCITATION",
                        "ROLL_RESONANCE",
                    }
                    else physical_drive,

                "roleCodeUsedAsGain":
                    False,

                "visualEnergyCandidateUsedAsMeshHeight":
                    False,

                "calibration":
                    "PROVISIONAL_ABSOLUTE_PRESERVING_NO_HEADROOM_MAPPING",
            },

            "attackEvents":
                attack_events,

            "modifiers": {
                "trend":
                    _trend_modifiers(
                        linked_gestures
                    ),

                "rhythm":
                    _rhythm_modifiers(
                        linked_gestures
                    ),

                "contextOnlyGestureRefs":
                    context_gestures,

                "gestureTypes":
                    _unique_sorted(
                        gesture_types
                    ),
            },

            "evidence": {
                "gestureRefs":
                    refs,

                "attackRefs":
                    list(
                        intent.get(
                            "attackRefs"
                        )
                        or []
                    ),

                "rhythmicStructures":
                    list(
                        intent.get(
                            "rhythmicStructures"
                        )
                        or []
                    ),

                "roleCode":
                    intent.get("role"),

                "visualEnergyCandidate":
                    _finite(
                        intent.get(
                            "visualEnergyCandidate"
                        )
                    ),

                "reason":
                    "V1.3B causal intent owns this behavior; V1.3A gestures and T007 spatial evidence shape it.",
            },
        })

    primitive_counts = Counter(
        behavior["primitive"]
        for behavior in behaviors
    )

    zero_attack_counts = Counter(
        behavior["primitive"]
        for behavior in behaviors
        if not behavior["attackEvents"]
    )

    moving_count = sum(
        behavior["spatialBehavior"]["mode"]
        == "MOVING_SOURCE"
        for behavior in behaviors
    )

    summary = {
        "behaviorCount":
            len(behaviors),

        "primitiveCounts":
            dict(
                sorted(
                    primitive_counts.items()
                )
            ),

        "zeroAttackBehaviorCount":
            sum(
                zero_attack_counts.values()
            ),

        "zeroAttackPrimitiveCounts":
            dict(
                sorted(
                    zero_attack_counts.items()
                )
            ),

        "movingSourceBehaviorCount":
            moving_count,

        "staticSourceBehaviorCount":
            len(behaviors)
            - moving_count,

        "missingGestureRefCount":
            len(missing_gesture_refs),

        "invalidAttackRefCount":
            len(invalid_attack_refs),

        "totalAttackEvents":
            sum(
                len(
                    behavior["attackEvents"]
                )
                for behavior in behaviors
            ),
    }

    if missing_gesture_refs:
        summary["missingGestureRefs"] = (
            missing_gesture_refs[:20]
        )

    if invalid_attack_refs:
        summary["invalidAttackRefs"] = (
            invalid_attack_refs[:20]
        )

    return behaviors, summary
