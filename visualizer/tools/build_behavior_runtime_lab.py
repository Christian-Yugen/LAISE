import json
import sys
from pathlib import Path

ROOT = Path(".").resolve()
VIS = ROOT / "visualizer"

sys.path.insert(
    0,
    str((VIS / "tools").resolve())
)

import build_audio_cues as cue_builder


DYNAMIC = (
    VIS / "public/audio/"
    "tukana-musical-dynamic-drive-v1.json"
)

MANIFEST = (
    ROOT
    / "projects/tukana_02_a_mata_se_move"
    / "experiments/TUK2_T007"
    / "spatial_scenes"
    / "TUK2_T007_automation_manifest.json"
)

OUTPUT = (
    VIS / "public/audio/"
    "tukana-musical-behavior-runtime-v1.json"
)


def load(path):
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


dynamic = load(DYNAMIC)
manifest = load(MANIFEST)

roles = {
    role["source_id"]: role
    for role in manifest["roles"]
}


WIDTHS = {
    "drums": 0.64,
    "bass": 0.64,
    "percussion": 0.64,

    "lead_vocal": 0.80,
    "backing_vocals": 0.80,
    "guitar": 0.80,
    "keyboards": 0.80,
    "strings": 0.80,
    "synth": 0.80,
    "other": 0.80,
    "brass": 0.80,
    "woodwinds": 0.80,
}


CONTINUOUS = {
    "SUSTAINED_EXCITATION",
    "ROLL_RESONANCE",
}

DISCRETE = {
    "IMPULSE",
    "PULSE_SEQUENCE",
}


runtime_behaviors = []

continuous_samples = 0
physical_attacks = 0
trace_only_attacks = 0


for behavior in dynamic["behaviors"]:

    source = behavior["source"]
    primitive = behavior["primitive"]

    role = roles[source]

    continuous = []
    attacks = []


    if primitive in CONTINUOUS:

        samples = (
            behavior[
                "continuousDrive"
            ]["samples"]
        )

        for row in samples:

            t = float(row[0])
            drive = float(row[2])

            (
                x,
                z,
                azimuth,
                elevation,
                distance,
            ) = cue_builder.floor_position(
                role,
                t,
            )

            continuous.append([
                t,
                drive,
                x,
                z,
            ])

        continuous_samples += len(
            continuous
        )

        trace_only_attacks += len(
            behavior[
                "attackDriveEvents"
            ]
        )


    elif primitive in DISCRETE:

        for event in behavior[
            "attackDriveEvents"
        ]:

            t = float(
                event["time"]
            )

            (
                x,
                z,
                azimuth,
                elevation,
                distance,
            ) = cue_builder.floor_position(
                role,
                t,
            )

            attacks.append({
                "time":
                    t,

                "drive":
                    float(
                        event[
                            "physicalDrive"
                        ]
                    ),

                "x":
                    x,

                "z":
                    z,
            })

        physical_attacks += len(
            attacks
        )


    runtime_behaviors.append({
        "behaviorId":
            behavior["behaviorId"],

        "intentId":
            behavior["intentId"],

        "source":
            source,

        "primitive":
            primitive,

        "startTime":
            float(
                behavior["startTime"]
            ),

        "endTime":
            float(
                behavior["endTime"]
            ),

        "baseWidth":
            WIDTHS[source],

        "continuous":
            continuous,

        "attacks":
            attacks,
    })


runtime = {
    "schema":
        "laise-v1.3c-visible-behavior-runtime-v1",

    "version":
        "1.3C-VISIBLE-LAB-R1",

    "masterUrl":
        "/audio/TUKANA02_FINAL_MASTER_PCM24_48k.wav",

    "duration":
        330.0,

    "contracts": {
        "productionModified":
            False,

        "singleAudioClock":
            True,

        "positionAuthority":
            "T007",

        "dominantAnchor":
            "COMMON_TRANSLATION_RELATIVE_TO_DOMINANT",

        "elevationMappedToMeshY":
            False,

        "roleCodeUsedAsGain":
            False,

        "continuousAttackDoubleCount":
            False,

        "headroom":
            "LEGACY_2_8_LAB_ONLY_NOT_V1_3C_APPROVAL",

        "continuousCoupling":
            "RESPONSE_EQUIVALENT_PROVISIONAL",

        "footprintMapping":
            "PROVISIONAL_ABSOLUTE_DRIVE_LOG_MAPPING",
    },

    "calibration": {
        "amplitudeReferenceRms":
            0.014295334592461588,

        "kImpulse":
            1399.0578444065711,

        "kContinuous":
            2212.104683325114,

        "continuousDriveP10":
            0.000071516509686,

        "continuousDriveP50":
            0.0019082693464,

        "continuousDriveP95":
            0.00805533060326,

        "continuousDriveP99":
            0.0123078978185,

        "continuousDriveMax":
            0.0204331422574,

        "physicsStep":
            1.0 / 120.0,

        "arbitration": {
            "tie":
                0.01,

            "hysteresis":
                0.08,

            "holdSeconds":
                0.150,

            "strongChangeRatio":
                1.5,
        },
    },

    "counts": {
        "behaviors":
            len(runtime_behaviors),

        "continuousBehaviors":
            sum(
                bool(
                    b["continuous"]
                )
                for b in runtime_behaviors
            ),

        "continuousSamples":
            continuous_samples,

        "physicalAttacks":
            physical_attacks,

        "traceOnlyAttacks":
            trace_only_attacks,

        "totalAttackEvidence":
            (
                physical_attacks
                + trace_only_attacks
            ),
    },

    "behaviors":
        runtime_behaviors,
}


assert runtime["counts"]["behaviors"] == 505
assert runtime["counts"]["continuousBehaviors"] == 206
assert runtime["counts"]["continuousSamples"] == 93249
assert runtime["counts"]["physicalAttacks"] == 2174
assert runtime["counts"]["totalAttackEvidence"] == 10282


OUTPUT.write_text(
    json.dumps(
        runtime,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ) + "\n",
    encoding="utf-8",
    newline="\n",
)


print("BEHAVIORS=", runtime["counts"]["behaviors"])
print("CONTINUOUS_BEHAVIORS=", runtime["counts"]["continuousBehaviors"])
print("CONTINUOUS_SAMPLES=", runtime["counts"]["continuousSamples"])
print("PHYSICAL_ATTACKS=", runtime["counts"]["physicalAttacks"])
print("TRACE_ONLY_ATTACKS=", runtime["counts"]["traceOnlyAttacks"])
print("TOTAL_ATTACK_EVIDENCE=", runtime["counts"]["totalAttackEvidence"])
print("RUNTIME=", OUTPUT.resolve())
print("BEHAVIOR_RUNTIME_BUILD=PASS")
