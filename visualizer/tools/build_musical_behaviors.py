from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from musical_behaviors import (
    SCHEMA,
    VERSION,
    build_behaviors,
)


def sha256(path: Path) -> str:

    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Build deterministic LAISE V1.3C "
            "musical behavior artifact."
        )
    )

    parser.add_argument(
        "--gestures",
        default=(
            "visualizer/public/audio/"
            "tukana-musical-gestures-v1.json"
        ),
    )

    parser.add_argument(
        "--intents",
        default=(
            "visualizer/public/audio/"
            "tukana-musical-visual-intents-v1.json"
        ),
    )

    parser.add_argument(
        "--cues",
        default=(
            "visualizer/public/audio/"
            "tukana-stem-cues.json"
        ),
    )

    parser.add_argument(
        "--output",
        default=(
            "visualizer/public/audio/"
            "tukana-musical-behaviors-v1.json"
        ),
    )

    args = parser.parse_args()

    gestures_path = Path(
        args.gestures
    )

    intents_path = Path(
        args.intents
    )

    cues_path = Path(
        args.cues
    )

    output_path = Path(
        args.output
    )

    gestures = load_json(
        gestures_path
    )

    intents = load_json(
        intents_path
    )

    cues = load_json(
        cues_path
    )

    behaviors, summary = (
        build_behaviors(
            gestures,
            intents,
            cues,
        )
    )

    payload = {
        "schema":
            SCHEMA,

        "version":
            VERSION,

        "duration":
            intents.get(
                "duration",
                cues.get("duration"),
            ),

        "status":
            "V1.3C_BEHAVIOR_LAB_ONLY_NOT_PRODUCTION_RUNTIME",

        "contracts": {
            "causalOwnership":
                "NO VISUAL BEHAVIOR WITHOUT V1.3B INTENT OWNER",

            "roleCode":
                "PRIORITY_ANNOTATION_ONLY_NEVER_BINARY_GAIN",

            "visualEnergyCandidate":
                "RELATIVE_ENERGY_ONLY_NEVER_DIRECT_MESH_HEIGHT",

            "elevation":
                "PRESERVED_AS_SPATIAL_METADATA_NOT_MAPPED_TO_MESH_Y",

            "headroom":
                "NOT_SELECTED_IN_THIS_ARTIFACT",
        },

        "inputReferences": {
            "gestures": {
                "path":
                    gestures_path.as_posix(),

                "sha256":
                    sha256(gestures_path),

                "schema":
                    gestures.get("schema"),

                "version":
                    gestures.get("version"),
            },

            "intents": {
                "path":
                    intents_path.as_posix(),

                "sha256":
                    sha256(intents_path),

                "schema":
                    intents.get("schema"),

                "version":
                    intents.get("version"),
            },

            "cues": {
                "path":
                    cues_path.as_posix(),

                "sha256":
                    sha256(cues_path),

                "schema":
                    cues.get("schema"),

                "version":
                    cues.get("version"),
            },

            "spatialTrajectoryReference":
                gestures.get(
                    "spatialTrajectoryReference"
                ),
        },

        "physicalDriveContract": {
            "anchor":
                "absolute audio evidence; no per-source normalization",

            "formula":
                "evidenceIntensity * "
                "(1+0.25*S/(1+S)) * "
                "(1+0.10*L/(1+L)) * "
                "(1+0.10*T/(1+T))",

            "S":
                "musicalSalience",

            "L":
                "localContextIntensity",

            "T":
                "trackRelativeIntensity",

            "evidenceIntensity":
                "max(absoluteIntensity, attackStrength) "
                "for impulse/pulse/roll; "
                "max(absoluteIntensity, sustainStrength) "
                "for sustained",

            "durationPolicy":
                "duration does not inflate instantaneous amplitude; "
                "sustained/roll duration controls feed time "
                "and integratedDriveCandidate",

            "trendPolicy":
                "crescendo/decrescendo retain measured evidence "
                "as modifiers; no invented linear amplitude ramp "
                "is generated here",
        },

        "summary":
            summary,

        "behaviors":
            behaviors,
    }

    if (
        summary["missingGestureRefCount"]
        or summary["invalidAttackRefCount"]
    ):
        raise SystemExit(
            "FAIL: unresolved causal references; "
            "output not written. "
            f"{summary}"
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    encoded = (
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")

    output_path.write_bytes(
        encoded
    )

    print("STATUS=PASS")

    print(
        f"OUTPUT={output_path}"
    )

    print(
        "OUTPUT_SHA256="
        + hashlib.sha256(
            encoded
        ).hexdigest()
    )

    for key, value in summary.items():
        if not isinstance(
            value,
            (list, dict),
        ):
            print(
                f"{key}={value}"
            )

    print(
        "primitiveCounts="
        + json.dumps(
            summary[
                "primitiveCounts"
            ],
            sort_keys=True,
        )
    )

    print(
        "zeroAttackPrimitiveCounts="
        + json.dumps(
            summary[
                "zeroAttackPrimitiveCounts"
            ],
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
