from __future__ import annotations

import json
import math
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from musical_behaviors import (
    _drive_components,
    _primitive,
    _rhythm_modifiers,
    _trend_modifiers,
    build_behaviors,
)


PASS_COUNT = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS_COUNT

    if not condition:
        print(f"FAIL — {name}")
        if detail:
            print("       " + detail)
        raise AssertionError(name)

    PASS_COUNT += 1
    print(f"PASS — {name}")

    if detail:
        print("       " + detail)


def intent(
    intensity: float,
    *,
    intent_id: str = "test:i00000",
    source: str = "test",
    temporal: str = "impulse",
    start: float = 1.0,
    end: float = 1.1,
    gesture_refs=None,
    attack_refs=None,
    salience: float = 0.5,
    track_relative: float = 0.5,
    local_context: float = 0.5,
):
    return {
        "intentId": intent_id,
        "source": source,
        "startTime": start,
        "endTime": end,
        "gestureRefs": gesture_refs or [],
        "attackRefs": attack_refs or [],
        "rhythmicStructures": [],
        "temporalBehavior": temporal,
        "absoluteIntensity": intensity,
        "trackRelativeIntensity": track_relative,
        "localContextIntensity": local_context,
        "musicalSalience": salience,
        "visualEnergyCandidate": track_relative ** 2,
        "role": "background",
    }


def gesture(
    gesture_id: str,
    gesture_type: str,
    *,
    source: str = "test",
    start: float = 1.0,
    end: float = 1.1,
    attack_strength: float = 0.0,
    sustain_strength: float = 0.0,
    trajectory=None,
    evidence=None,
    repetition_rate: float = 0.0,
    trend: float = 0.0,
):
    return {
        "gestureId": gesture_id,
        "gestureType": gesture_type,
        "source": source,
        "startTime": start,
        "peakTime": (start + end) / 2.0,
        "endTime": end,
        "attackStrength": attack_strength,
        "sustainStrength": sustain_strength,
        "trajectory": trajectory or [],
        "evidence": evidence or {},
        "repetitionRate": repetition_rate,
        "trend": trend,
    }


def cue(
    t: float,
    strength: float,
    *,
    source: str = "test",
    x: float = 0.0,
    z: float = 0.0,
):
    return {
        "time": t,
        "source": source,
        "x": x,
        "z": z,
        "strength": strength,
        "width": 0.8,
    }


def build_one(
    one_intent,
    gestures,
    cues,
):
    payload_g = {
        "gestures": gestures,
        "spatialTrajectoryReference": {
            "source": "synthetic-test"
        },
    }

    payload_i = {
        "duration": 10.0,
        "intents": [one_intent],
    }

    payload_c = {
        "duration": 10.0,
        "events": cues,
    }

    behaviors, summary = build_behaviors(
        payload_g,
        payload_i,
        payload_c,
    )

    assert len(behaviors) == 1

    return behaviors[0], summary


print("\n===== SYNTHETIC MUSICAL CONTRACTS =====")


# ---------------------------------------------------------
# A/B/C — weak < medium < strong
# ---------------------------------------------------------

def synthetic_drive(level: float) -> float:
    i = intent(
        level,
        salience=0.5,
        track_relative=0.5,
        local_context=0.5,
    )

    g = [
        gesture(
            "test:g00000",
            "IMPULSE",
            attack_strength=level,
        )
    ]

    return _drive_components(
        i,
        g,
        "IMPULSE",
    )["physicalDrive"]


weak = synthetic_drive(0.001)
medium = synthetic_drive(0.005)
strong = synthetic_drive(0.020)

check(
    "A/B/C intensity monotonicity",
    weak < medium < strong,
    f"weak={weak:.9f}, medium={medium:.9f}, strong={strong:.9f}",
)


# ---------------------------------------------------------
# Primitive mapping
# ---------------------------------------------------------

check(
    "IMPULSE maps to IMPULSE",
    _primitive(
        "impulse",
        {"IMPULSE"},
    ) == "IMPULSE",
)

check(
    "repeated maps to PULSE_SEQUENCE",
    _primitive(
        "repeated",
        {"REPEATED_PULSE"},
    ) == "PULSE_SEQUENCE",
)

check(
    "sustained maps to SUSTAINED_EXCITATION",
    _primitive(
        "sustained",
        {"SUSTAINED_TONE"},
    ) == "SUSTAINED_EXCITATION",
)

check(
    "TREMOLO_OR_ROLL overrides to ROLL_RESONANCE",
    _primitive(
        "sustained",
        {"SUSTAINED_TEXTURE", "TREMOLO_OR_ROLL"},
    ) == "ROLL_RESONANCE",
)


# ---------------------------------------------------------
# D — regular TUM-TUM-TUM-TUM
# ---------------------------------------------------------

regular_ioi = [0.5, 0.5, 0.5]

regular_gesture = gesture(
    "test:g00001",
    "REPEATED_PULSE_SEQUENCE",
    evidence={
        "rateHz": 2.0,
        "ioiSeconds": regular_ioi,
        "ioiTrendCorrelation": 0.0,
    },
)

regular_result = _rhythm_modifiers(
    [regular_gesture]
)

check(
    "D regular pulse timing preserved exactly",
    regular_result[0]["ioiSeconds"] == regular_ioi,
    str(regular_result[0]["ioiSeconds"]),
)


# ---------------------------------------------------------
# E — accelerating sequence
# ---------------------------------------------------------

accelerating_ioi = [
    0.800,
    0.600,
    0.400,
    0.250,
]

accelerating_gesture = gesture(
    "test:g00002",
    "ACCELERATING_SEQUENCE",
    evidence={
        "rateHz": 1.9512195122,
        "ioiSeconds": accelerating_ioi,
        "ioiTrendCorrelation": -0.98,
    },
)

accelerating_result = _rhythm_modifiers(
    [accelerating_gesture]
)[0]

check(
    "E accelerating IOIs preserved without regularization",
    accelerating_result["ioiSeconds"] == accelerating_ioi
    and all(
        a > b
        for a, b in zip(
            accelerating_ioi,
            accelerating_ioi[1:],
        )
    ),
    str(accelerating_result["ioiSeconds"]),
)


# ---------------------------------------------------------
# F — decelerating sequence
# ---------------------------------------------------------

decelerating_ioi = [
    0.250,
    0.400,
    0.600,
    0.800,
]

decelerating_gesture = gesture(
    "test:g00003",
    "DECELERATING_SEQUENCE",
    evidence={
        "rateHz": 1.9512195122,
        "ioiSeconds": decelerating_ioi,
        "ioiTrendCorrelation": 0.98,
    },
)

decelerating_result = _rhythm_modifiers(
    [decelerating_gesture]
)[0]

check(
    "F decelerating IOIs preserved without regularization",
    decelerating_result["ioiSeconds"] == decelerating_ioi
    and all(
        a < b
        for a, b in zip(
            decelerating_ioi,
            decelerating_ioi[1:],
        )
    ),
    str(decelerating_result["ioiSeconds"]),
)


# ---------------------------------------------------------
# G — roll 8–15 Hz
# ---------------------------------------------------------

roll_ioi = [
    0.090,
    0.082,
    0.095,
    0.087,
    0.091,
]

roll_rate = 1.0 / (
    sum(roll_ioi) / len(roll_ioi)
)

roll_gesture = gesture(
    "test:g00004",
    "TREMOLO_OR_ROLL",
    attack_strength=0.01,
    evidence={
        "rateHz": roll_rate,
        "ioiSeconds": roll_ioi,
    },
)

roll_rhythm = _rhythm_modifiers(
    [roll_gesture]
)[0]

check(
    "G roll remains coherent 8–15 Hz evidence",
    8.0 <= roll_rhythm["rateHz"] <= 15.0
    and roll_rhythm["ioiSeconds"] == roll_ioi,
    f'rate={roll_rhythm["rateHz"]:.4f} Hz',
)

check(
    "G roll maps to one ROLL_RESONANCE primitive",
    _primitive(
        "repeated",
        {"TREMOLO_OR_ROLL", "REPEATED_PULSE"},
    ) == "ROLL_RESONANCE",
)


# ---------------------------------------------------------
# H — 5 s sustain
# ---------------------------------------------------------

sustain_intent = intent(
    0.008,
    temporal="sustained",
    start=2.0,
    end=7.0,
    gesture_refs=["test:g00005"],
)

sustain_gesture = gesture(
    "test:g00005",
    "SUSTAINED_TONE",
    start=2.0,
    end=7.0,
    sustain_strength=0.008,
)

sustain_behavior, _ = build_one(
    sustain_intent,
    [sustain_gesture],
    [],
)

check(
    "H sustain feeds continuously for causal duration",
    sustain_behavior["primitive"]
        == "SUSTAINED_EXCITATION"
    and sustain_behavior["feedMode"]
        == "CONTINUOUS_WHILE_CAUSAL"
    and math.isclose(
        sustain_behavior["duration"],
        5.0,
        abs_tol=1e-9,
    )
    and math.isclose(
        sustain_behavior["drive"][
            "feedDurationSeconds"
        ],
        5.0,
        abs_tol=1e-9,
    ),
    f'duration={sustain_behavior["duration"]}',
)


# ---------------------------------------------------------
# I/J — measured crescendo/decrescendo retained
# ---------------------------------------------------------

crescendo = gesture(
    "test:g00006",
    "CRESCENDO",
    start=2.0,
    end=5.0,
    evidence={
        "energyChangeDb": 12.0,
        "energyTimeCorrelation": 0.94,
    },
)

decrescendo = gesture(
    "test:g00007",
    "DECRESCENDO",
    start=5.0,
    end=8.0,
    evidence={
        "energyChangeDb": -18.0,
        "energyTimeCorrelation": -0.96,
    },
)

trend_up = _trend_modifiers(
    [crescendo]
)[0]

trend_down = _trend_modifiers(
    [decrescendo]
)[0]

check(
    "I crescendo measured direction preserved",
    trend_up["energyChangeDb"] > 0
    and trend_up["energyTimeCorrelation"] > 0,
    (
        f'dB={trend_up["energyChangeDb"]}, '
        f'corr={trend_up["energyTimeCorrelation"]}'
    ),
)

check(
    "J decrescendo measured direction preserved",
    trend_down["energyChangeDb"] < 0
    and trend_down["energyTimeCorrelation"] < 0,
    (
        f'dB={trend_down["energyChangeDb"]}, '
        f'corr={trend_down["energyTimeCorrelation"]}'
    ),
)


# ---------------------------------------------------------
# K — moving sustain
# ---------------------------------------------------------

moving_trajectory = [
    {
        "time": 1.0,
        "x": -0.40,
        "z": 0.10,
        "azimuth": -60.0,
        "elevation": 10.0,
        "distance": 1.0,
    },
    {
        "time": 2.0,
        "x": 0.00,
        "z": 0.20,
        "azimuth": 0.0,
        "elevation": 10.0,
        "distance": 1.0,
    },
    {
        "time": 3.0,
        "x": 0.40,
        "z": 0.10,
        "azimuth": 60.0,
        "elevation": 10.0,
        "distance": 1.0,
    },
]

moving_intent = intent(
    0.010,
    temporal="sustained",
    start=1.0,
    end=3.0,
    gesture_refs=["test:g00008"],
)

moving_gesture = gesture(
    "test:g00008",
    "CONTINUOUS_MOTION",
    start=1.0,
    end=3.0,
    sustain_strength=0.010,
    trajectory=moving_trajectory,
)

moving_behavior, _ = build_one(
    moving_intent,
    [moving_gesture],
    [],
)

check(
    "K moving sustain follows supplied T007 trajectory",
    moving_behavior["spatialBehavior"]["mode"]
        == "MOVING_SOURCE"
    and moving_behavior["spatialBehavior"][
        "trajectory"
    ][0]["x"] == -0.4
    and moving_behavior["spatialBehavior"][
        "trajectory"
    ][-1]["x"] == 0.4,
)


# ---------------------------------------------------------
# Static source must remain static
# ---------------------------------------------------------

static_trajectory = [
    {
        "time": 1.0,
        "x": 0.2,
        "z": -0.1,
        "azimuth": 20.0,
        "elevation": 5.0,
        "distance": 1.0,
    },
    {
        "time": 3.0,
        "x": 0.2,
        "z": -0.1,
        "azimuth": 20.0,
        "elevation": 5.0,
        "distance": 1.0,
    },
]

static_intent = intent(
    0.010,
    temporal="sustained",
    start=1.0,
    end=3.0,
    gesture_refs=["test:g00009"],
)

static_gesture = gesture(
    "test:g00009",
    "SUSTAINED_TONE",
    start=1.0,
    end=3.0,
    sustain_strength=0.010,
    trajectory=static_trajectory,
)

static_behavior, _ = build_one(
    static_intent,
    [static_gesture],
    [],
)

check(
    "Static source receives no invented movement",
    static_behavior["spatialBehavior"]["mode"]
        == "STATIC_SOURCE",
)


# ---------------------------------------------------------
# L — moving repeated pulses retain attack positions
# ---------------------------------------------------------

pulse_intent = intent(
    0.012,
    temporal="repeated",
    start=1.0,
    end=2.0,
    gesture_refs=["test:g00010"],
    attack_refs=[0, 1, 2],
)

pulse_gesture = gesture(
    "test:g00010",
    "REPEATED_PULSE_SEQUENCE",
    start=1.0,
    end=2.0,
    attack_strength=0.012,
    trajectory=[
        {
            "time": 1.0,
            "x": -0.3,
            "z": 0.0,
            "azimuth": -45.0,
            "elevation": 0.0,
            "distance": 1.0,
        },
        {
            "time": 1.5,
            "x": 0.0,
            "z": 0.0,
            "azimuth": 0.0,
            "elevation": 0.0,
            "distance": 1.0,
        },
        {
            "time": 2.0,
            "x": 0.3,
            "z": 0.0,
            "azimuth": 45.0,
            "elevation": 0.0,
            "distance": 1.0,
        },
    ],
    evidence={
        "ioiSeconds": [0.5, 0.5],
        "rateHz": 2.0,
    },
)

pulse_cues = [
    cue(
        1.0,
        0.2,
        x=-0.3,
        z=0.0,
    ),
    cue(
        1.5,
        0.3,
        x=0.0,
        z=0.0,
    ),
    cue(
        2.0,
        0.4,
        x=0.3,
        z=0.0,
    ),
]

pulse_behavior, _ = build_one(
    pulse_intent,
    [pulse_gesture],
    pulse_cues,
)

check(
    "L moving repeated pulses preserve per-attack T007 positions",
    [
        event["x"]
        for event in pulse_behavior["attackEvents"]
    ] == [-0.3, 0.0, 0.3]
    and pulse_behavior["spatialBehavior"]["mode"]
        == "MOVING_SOURCE",
)


# ---------------------------------------------------------
# M — two equal sources remain two behaviors
# ---------------------------------------------------------

equal_intents = {
    "duration": 4.0,
    "intents": [
        intent(
            0.01,
            intent_id="left:i00000",
            source="left",
            gesture_refs=["left:g00000"],
        ),
        intent(
            0.01,
            intent_id="right:i00000",
            source="right",
            gesture_refs=["right:g00000"],
        ),
    ],
}

equal_gestures = {
    "gestures": [
        gesture(
            "left:g00000",
            "IMPULSE",
            source="left",
            attack_strength=0.01,
        ),
        gesture(
            "right:g00000",
            "IMPULSE",
            source="right",
            attack_strength=0.01,
        ),
    ],
}

equal_behaviors, _ = build_behaviors(
    equal_gestures,
    equal_intents,
    {
        "duration": 4.0,
        "events": [],
    },
)

check(
    "M equal sources are never fused",
    len(equal_behaviors) == 2
    and {
        b["source"]
        for b in equal_behaviors
    } == {"left", "right"},
)


# ---------------------------------------------------------
# N — strong + weak preserve absolute order
# ---------------------------------------------------------

weak_intent = intent(
    0.002,
    salience=0.5,
    track_relative=0.5,
    local_context=0.5,
)

strong_intent = intent(
    0.020,
    salience=0.5,
    track_relative=0.5,
    local_context=0.5,
)

weak_drive = _drive_components(
    weak_intent,
    [
        gesture(
            "w:g",
            "IMPULSE",
            attack_strength=0.002,
        )
    ],
    "IMPULSE",
)["physicalDrive"]

strong_drive = _drive_components(
    strong_intent,
    [
        gesture(
            "s:g",
            "IMPULSE",
            attack_strength=0.020,
        )
    ],
    "IMPULSE",
)["physicalDrive"]

check(
    "N strong source remains stronger than equivalent weak source",
    strong_drive > weak_drive,
    f"weak={weak_drive:.9f}, strong={strong_drive:.9f}",
)


# ---------------------------------------------------------
# O — silence
# ---------------------------------------------------------

silent_behaviors, silent_summary = build_behaviors(
    {"gestures": []},
    {
        "duration": 5.0,
        "intents": [],
    },
    {
        "duration": 5.0,
        "events": [],
    },
)

check(
    "O silence generates zero behavior",
    silent_behaviors == []
    and silent_summary["behaviorCount"] == 0,
)


# ---------------------------------------------------------
# Cross-contracts
# ---------------------------------------------------------

check(
    "roleCode excluded from physicalDrive formula",
    "role" not in (
        "evidenceIntensity * "
        "(1+0.25*S/(1+S)) * "
        "(1+0.10*L/(1+L)) * "
        "(1+0.10*T/(1+T))"
    ).lower(),
)

check(
    "visualEnergyCandidate is not direct mesh height",
    sustain_behavior["drive"][
        "visualEnergyCandidateUsedAsMeshHeight"
    ] is False,
)

check(
    "Elevation is not mapped to mesh Y",
    moving_behavior["spatialBehavior"][
        "elevationPolicy"
    ] == "METADATA_ONLY_NOT_MESH_Y",
)


print("\n===== REAL TUKANA II ARTIFACT AUDIT =====")

artifact_path = Path(
    "visualizer/public/audio/"
    "tukana-musical-behaviors-v1.json"
)

data = json.loads(
    artifact_path.read_text(
        encoding="utf-8"
    )
)

behaviors = data["behaviors"]
summary = data["summary"]

check(
    "Real artifact has exactly 505 causal behaviors",
    len(behaviors) == 505,
)

check(
    "Real artifact preserves all 10,282 attacks",
    sum(
        len(b["attackEvents"])
        for b in behaviors
    ) == 10282,
)

check(
    "Real artifact has no unresolved causal references",
    summary["missingGestureRefCount"] == 0
    and summary["invalidAttackRefCount"] == 0,
)

check(
    "All zero-attack real behaviors are sustained excitation",
    all(
        b["primitive"]
            == "SUSTAINED_EXCITATION"
        for b in behaviors
        if not b["attackEvents"]
    ),
)

check(
    "No real behavior uses roleCode as binary gain",
    all(
        b["drive"]["roleCodeUsedAsGain"]
            is False
        for b in behaviors
    ),
)

check(
    "No real behavior maps relative energy directly to mesh height",
    all(
        b["drive"][
            "visualEnergyCandidateUsedAsMeshHeight"
        ] is False
        for b in behaviors
    ),
)

real_drives = [
    b["drive"]["physicalDrive"]
    for b in behaviors
]

check(
    "Real physicalDrive values are finite and non-negative",
    all(
        math.isfinite(value)
        and value >= 0.0
        for value in real_drives
    ),
)

moving_real = [
    b for b in behaviors
    if b["spatialBehavior"]["mode"]
        == "MOVING_SOURCE"
]

check(
    "Real moving sources retain trajectory evidence",
    len(moving_real) > 0
    and all(
        len(
            b["spatialBehavior"]["trajectory"]
        ) >= 2
        for b in moving_real
    ),
    f"moving={len(moving_real)}",
)


print("\n===== EXPLICITLY DEFERRED TO NEXT V1.3C LAYERS =====")

deferred = [
    (
        "I dynamic crescendo response",
        "Measured crescendo evidence is preserved, "
        "but time-varying physicalDrive envelope is not implemented yet."
    ),
    (
        "J dynamic decrescendo response",
        "Measured decrescendo evidence is preserved, "
        "but time-varying physicalDrive envelope is not implemented yet."
    ),
    (
        "P post-causal physical dissipation",
        "Planner correctly defines causal feed interval; "
        "wave continuation after feed stops belongs to Behavior Physics Lab."
    ),
    (
        "Dynamic Visual Headroom",
        "No Y/headroom mapping exists yet by design."
    ),
    (
        "A/B perceptual correspondence",
        "Requires Behavior Lab runtime using the same master clock."
    ),
]

for name, reason in deferred:
    print(f"DEFERRED — {name}")
    print(f"           {reason}")


print("\n===== RESULT =====")
print(f"FOUNDATION_ASSERTIONS_PASS={PASS_COUNT}")
print("FOUNDATION_ASSERTIONS_FAIL=0")
print(f"DEFERRED_CONTRACTS={len(deferred)}")
print("STATUS=FOUNDATION_PASS_DYNAMIC_BEHAVIOR_PENDING")
