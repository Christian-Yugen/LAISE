from __future__ import annotations

import json
import math
import time
import hashlib
import multiprocessing
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from music02_t005_common import (
    RATE,
    BLOCK,
    features,
    classify,
    intended_distance,
    feature_distance,
    direction,
    elevation_band,
    transient_proxy,
)

from music02_t005_render import render
from music02_t003 import unit
from music02_preview import write24
from dearvr_adapter import PLUGIN_PATH


ROOT = Path(r"C:\Projetos2026\LAISE")

PROJECT = (
    ROOT
    / "projects"
    / "tukana_02_a_mata_se_move"
)

OUT = (
    PROJECT
    / "experiments"
    / "TUK2_T005"
)

REPORTS = OUT / "reports"
PROBES = OUT / "probes" / "native256"

T001 = (
    PROJECT
    / "analysis"
    / "TUK2_T001_immutable_intake.json"
)

T002 = (
    PROJECT
    / "analysis"
    / "TUK2_T002_objective_stem_profiles.json"
)

T003 = (
    PROJECT
    / "analysis"
    / "TUK2_T003_structural_masking_map.json"
)

T004R1 = (
    PROJECT
    / "analysis"
    / "TUK2_T004R1_blueprint_correction.json"
)

BLUEPRINT = (
    PROJECT
    / "spatial_scenes"
    / "TUK2_T004R1_blueprint.json"
)

OLD_LIBRARY = (
    ROOT
    / "projects"
    / "music_02"
    / "experiments"
    / "M02_T005"
    / "reports"
    / "probe_library_native256.json"
)


AZ = [
    0,
    30, -30,
    60, -60,
    90, -90,
    120, -120,
    150, -150,
    180,
]

EL = [
    -45,
    -20,
    0,
    20,
    45,
    60,
]

DIST = [
    0.35,
    0.50,
    0.75,
    1.00,
    1.50,
    2.00,
    3.00,
]


def load(path):
    return json.loads(
        path.read_text(encoding="utf-8-sig")
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
            lambda: f.read(1024 * 1024),
            b""
        ):
            h.update(block)

    return h.hexdigest()


def reference():
    rng = np.random.default_rng(5017)

    noise = rng.normal(
        size=RATE + RATE // 4
    )

    spectrum = np.fft.rfft(noise)

    freq = np.fft.rfftfreq(
        len(noise),
        1 / RATE
    )

    shaping = np.where(
        (freq >= 60)
        & (freq <= 20000),

        1 / np.sqrt(
            np.maximum(freq, 60)
        ),

        0.0
    )

    spectrum *= shaping

    mono = np.fft.irfft(
        spectrum,
        n=len(noise)
    )

    mono *= (
        0.03
        / max(
            np.max(np.abs(mono)),
            1e-12
        )
    )

    return np.vstack(
        (mono, mono)
    ).astype(np.float32)


def make_source(
    azimuth,
    elevation,
    distance
):
    return {
        "gain_db": 0.0,

        "home": {
            "distance_m": float(distance)
        },

        "growth_reference_distance_m":
            float(distance),

        "keyframes": [
            {
                "time_seconds": 0.0,
                "azimuth_deg_unwrapped":
                    float(azimuth),
                "elevation_deg":
                    float(elevation),
                "gain_db": 0.0,
                "reason": "Known TUK2 probe",
            },

            {
                "time_seconds": 300.0,
                "azimuth_deg_unwrapped":
                    float(azimuth),
                "elevation_deg":
                    float(elevation),
                "gain_db": 0.0,
                "reason": "Hold",
            },
        ],

        "distance_keyframes": [
            {
                "time_seconds": 0.0,
                "distance_m":
                    float(distance),
            },

            {
                "time_seconds": 300.0,
                "distance_m":
                    float(distance),
            },
        ],
    }


def worker(spec):
    az, el, distance = spec

    source = make_source(
        az,
        el,
        distance
    )

    x = reference()

    y, _, _ = render(
        x,
        source
    )

    # First 250 ms = plugin warm-up.
    y = y[:, RATE // 4:]

    if y.shape != (2, RATE):
        raise RuntimeError(
            f"Unexpected probe shape: {y.shape}"
        )

    if not np.isfinite(y).all():
        raise RuntimeError(
            "NaN/Inf detected."
        )

    name = (
        f"az_{az:+04d}"
        f"_el_{el:+03d}"
        f"_d_{distance:g}"
    )

    path = (
        PROBES
        / f"{name}.wav"
    )

    if path.exists():
        raise RuntimeError(
            f"Refusing overwrite: {path}"
        )

    write24(
        path,
        y
    )

    dry_measured = x[:, RATE // 4:]

    return {
        "id": name,

        "path":
            str(path),

        "sha256":
            sha256_file(path),

        "azimuth_deg":
            int(az),

        "elevation_deg":
            int(el),

        "distance_m":
            float(distance),

        "train":
            features(
                y[:, :RATE // 2]
            ),

        "holdout":
            features(
                y[:, RATE // 2:]
            ),

        "full":
            features(y),

        "transient":
            transient_proxy(
                dry_measured,
                y
            ),

        "peak":
            float(
                np.max(np.abs(y))
            ),
    }


def validate_inputs():
    required = [
        T001,
        T002,
        T003,
        T004R1,
        BLUEPRINT,
    ]

    for path in required:
        if not path.exists():
            raise RuntimeError(
                f"Missing prerequisite: {path}"
            )

    for path in (
        T001,
        T002,
        T003,
        T004R1,
    ):
        data = load(path)

        if data["status"] != "PASS":
            raise RuntimeError(
                f"Prerequisite failed: {path}"
            )

    if not PLUGIN_PATH.is_file():
        raise RuntimeError(
            f"dearVR not found: {PLUGIN_PATH}"
        )


def previous_library_comparison(
    records
):
    if not OLD_LIBRARY.exists():
        return {
            "available": False
        }

    old = load(OLD_LIBRARY)

    old_hashes = {
        item["id"]: item["sha256"]
        for item in old["records"]
    }

    new_hashes = {
        item["id"]: item["sha256"]
        for item in records
    }

    common = (
        set(old_hashes)
        & set(new_hashes)
    )

    matching = sum(
        old_hashes[k] == new_hashes[k]
        for k in common
    )

    return {
        "available": True,

        "old_test_id":
            old.get("test_id"),

        "common_probe_count":
            len(common),

        "identical_probe_hash_count":
            matching,

        "all_common_probes_identical":
            matching == len(common),

        "note":
            (
                "Hash equality means identical "
                "PCM probe rendering for that pose. "
                "Mismatch does not automatically "
                "invalidate current calibration."
            )
    }


def run():
    validate_inputs()

    if OUT.exists():
        raise RuntimeError(
            "TUK2_T005 namespace already exists. "
            "Preserving prior evidence."
        )

    REPORTS.mkdir(
        parents=True,
        exist_ok=False
    )

    PROBES.mkdir(
        parents=True,
        exist_ok=False
    )

    print()
    print(
        "=============================================="
    )
    print(
        "TUK2-T005A - dearVR NATIVE CALIBRATION"
    )
    print(
        "=============================================="
    )

    print()
    print(
        f"Plugin: {PLUGIN_PATH}"
    )

    plugin_hash = sha256_file(
        PLUGIN_PATH
    )

    print(
        f"Plugin SHA256: {plugin_hash}"
    )

    print()
    print(
        "Grid:"
    )

    print(
        f"Azimuths   : {len(AZ)}"
    )

    print(
        f"Elevations : {len(EL)}"
    )

    print(
        f"Distances  : {len(DIST)}"
    )

    print(
        f"Total      : "
        f"{len(AZ)*len(EL)*len(DIST)}"
    )

    specs = [
        (az, el, distance)

        for az in AZ
        for el in EL
        for distance in DIST
    ]

    records = []

    started = time.time()

    with ProcessPoolExecutor(
        max_workers=2
    ) as pool:

        for i, result in enumerate(
            pool.map(worker, specs),
            1
        ):
            records.append(result)

            if (
                i % 42 == 0
                or i == len(specs)
            ):
                elapsed = (
                    time.time()
                    - started
                )

                print(
                    f"Probes "
                    f"{i}/{len(specs)} "
                    f"({elapsed:.1f}s)"
                )


    # ========================================================
    # POSITION MODELS
    # ========================================================

    models = []

    for az in AZ:
        for el in EL:

            group = [
                r for r in records
                if (
                    r["azimuth_deg"] == az
                    and
                    r["elevation_deg"] == el
                )
            ]

            model_features = (
                group[0]["train"].copy()
            )

            model_features["vector"] = (
                np.mean(
                    [
                        r["train"]["vector"]
                        for r in group
                    ],
                    axis=0
                ).tolist()
            )

            models.append({
                "azimuth_deg":
                    az,

                "elevation_deg":
                    el,

                "features":
                    model_features,
            })


    train = np.array(
        [
            m["features"]["vector"]
            for m in models
        ],
        dtype=np.float64
    )

    scale = np.std(
        train,
        axis=0
    )

    scale = np.maximum(
        scale,

        np.r_[
            np.ones(6),
            np.ones(12) * 0.1,
            20.0,
            1.0,
            np.ones(6),
        ]
    )


    library = {
        "schema":
            "LAISE TUK2 dearVR Probe Library v1.0",

        "project":
            "tukana_02_a_mata_se_move",

        "test_id":
            "TUK2-T005A-PROBES",

        "positions":
            len(records),

        "azimuths":
            AZ,

        "elevations":
            EL,

        "distances_m":
            DIST,

        "same_mono_reference":
            True,

        "reference_seed":
            5017,

        "reference_description":
            (
                "Broadband pink-shaped deterministic "
                "noise 60 Hz-20 kHz; 250 ms warm-up; "
                "1 s measured output."
            ),

        "feature_scale":
            scale.tolist(),

        "position_models":
            models,

        "records":
            records,

        "absolute_gain_excluded_from_classifier":
            True,

        "process_call_frames":
            BLOCK,

        "dearvr_plugin": {
            "path":
                str(PLUGIN_PATH),

            "sha256":
                plugin_hash,
        },

        "blueprint_sha256":
            sha256_file(BLUEPRINT),
    }


    # ========================================================
    # HOLDOUT VALIDATION
    # ========================================================

    estimates = []
    self_distances = []

    for r in records:

        estimate = classify(
            r["holdout"],
            library
        )

        self_distance = intended_distance(
            r["holdout"],
            r["azimuth_deg"],
            r["elevation_deg"],
            library
        )

        self_distances.append(
            self_distance
        )

        dot = float(
            np.clip(
                np.dot(
                    unit(
                        r["azimuth_deg"],
                        r["elevation_deg"]
                    ),

                    unit(
                        estimate["azimuth_deg"],
                        estimate["elevation_deg"]
                    ),
                ),
                -1.0,
                1.0
            )
        )

        angular_error = math.degrees(
            math.acos(dot)
        )

        estimates.append({
            "probe_id":
                r["id"],

            "intended": [
                r["azimuth_deg"],
                r["elevation_deg"],
            ],

            "estimated":
                estimate,

            "angular_error_deg":
                angular_error,

            "front_back_correct":
                (
                    estimate["front_rear"]
                    ==
                    direction(
                        r["azimuth_deg"]
                    )
                ),

            "elevation_band_correct":
                (
                    estimate[
                        "elevation_band"
                    ]
                    ==
                    elevation_band(
                        r["elevation_deg"]
                    )
                ),

            "intended_feature_distance":
                self_distance,
        })


    threshold = float(
        np.percentile(
            self_distances,
            95
        )
        * 2.0
    )

    redundant = []

    for i, first in enumerate(models):

        for second in models[i + 1:]:

            separation = feature_distance(
                first["features"],
                second["features"],
                library
            )

            if separation < threshold:

                redundant.append({
                    "a": [
                        first["azimuth_deg"],
                        first["elevation_deg"],
                    ],

                    "b": [
                        second["azimuth_deg"],
                        second["elevation_deg"],
                    ],

                    "feature_distance":
                        separation,
                })


    validation = {
        "status":
            "PASS",

        "heldout_count":
            len(estimates),

        "front_back_accuracy":
            float(
                np.mean(
                    [
                        e[
                            "front_back_correct"
                        ]
                        for e in estimates
                    ]
                )
            ),

        "elevation_band_accuracy":
            float(
                np.mean(
                    [
                        e[
                            "elevation_band_correct"
                        ]
                        for e in estimates
                    ]
                )
            ),

        "median_angular_error_deg":
            float(
                np.median(
                    [
                        e[
                            "angular_error_deg"
                        ]
                        for e in estimates
                    ]
                )
            ),

        "p95_angular_error_deg":
            float(
                np.percentile(
                    [
                        e[
                            "angular_error_deg"
                        ]
                        for e in estimates
                    ],
                    95
                )
            ),

        "within_pose_feature_distance_p95":
            float(
                np.percentile(
                    self_distances,
                    95
                )
            ),

        "redundancy_threshold":
            threshold,

        "redundant_position_pair_count":
            len(redundant),

        "redundant_position_pairs":
            redundant,

        "holdout_estimates":
            estimates,

        "caveats": [
            (
                "Temporal holdout uses the same "
                "controlled broadband reference; "
                "this is not human HRTF validation."
            ),

            (
                "Musical stems are a domain shift "
                "from broadband probe signals."
            ),

            (
                "Classifier confidence is an "
                "engineering feature-margin heuristic, "
                "not perceptual probability."
            ),

            (
                "Distance is not given a near-field "
                "perceptual score bonus."
            ),
        ],
    }

    library["validation"] = validation

    library[
        "music02_reference_comparison"
    ] = previous_library_comparison(
        records
    )


    report = (
        REPORTS
        / "probe_library_native256.json"
    )

    dump(
        report,
        library
    )


    summary = {
        "test_id":
            "TUK2-T005A",

        "status":
            "PASS",

        "probe_count":
            len(records),

        "plugin_sha256":
            plugin_hash,

        "front_back_accuracy":
            validation[
                "front_back_accuracy"
            ],

        "elevation_band_accuracy":
            validation[
                "elevation_band_accuracy"
            ],

        "median_angular_error_deg":
            validation[
                "median_angular_error_deg"
            ],

        "p95_angular_error_deg":
            validation[
                "p95_angular_error_deg"
            ],

        "redundant_position_pair_count":
            len(redundant),

        "music02_reference_comparison":
            library[
                "music02_reference_comparison"
            ],

        "report":
            str(report),
    }

    dump(
        REPORTS
        / "TUK2_T005A_summary.json",
        summary
    )


    print()
    print(
        "=============================================="
    )
    print(
        "TUK2-T005A RESULT"
    )
    print(
        "=============================================="
    )

    print(
        f"Probes                    : "
        f"{len(records)}"
    )

    print(
        f"Front/back accuracy       : "
        f"{validation['front_back_accuracy']:.4f}"
    )

    print(
        f"Elevation-band accuracy   : "
        f"{validation['elevation_band_accuracy']:.4f}"
    )

    print(
        f"Median angular error      : "
        f"{validation['median_angular_error_deg']:.3f} deg"
    )

    print(
        f"P95 angular error         : "
        f"{validation['p95_angular_error_deg']:.3f} deg"
    )

    print(
        f"Redundant position pairs  : "
        f"{len(redundant)}"
    )


    comparison = library[
        "music02_reference_comparison"
    ]

    print()
    print(
        "MUSIC02 PROBE COMPARISON:"
    )

    if comparison["available"]:

        print(
            f"Common probes             : "
            f"{comparison['common_probe_count']}"
        )

        print(
            f"Identical hashes          : "
            f"{comparison['identical_probe_hash_count']}"
        )

        print(
            f"All identical             : "
            f"{comparison['all_common_probes_identical']}"
        )

    else:

        print(
            "Previous MUSIC02 library unavailable."
        )


    print()
    print(
        "Report:"
    )

    print(report)

    print()
    print(
        "TUK2-T005A: PASS"
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    run()
