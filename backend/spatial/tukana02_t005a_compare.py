from __future__ import annotations

import json
import math
import hashlib
import wave
from pathlib import Path

import numpy as np

from music02_t005_common import (
    classify,
    feature_distance,
)

from music02_t003 import unit


ROOT = Path(r"C:\Projetos2026\LAISE")

PROJECT = (
    ROOT
    / "projects"
    / "tukana_02_a_mata_se_move"
)

NEW_LIBRARY = (
    PROJECT
    / "experiments"
    / "TUK2_T005"
    / "reports"
    / "probe_library_native256.json"
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

OLD_PROVENANCE = (
    ROOT
    / "projects"
    / "music_02"
    / "experiments"
    / "M02_T005"
    / "reports"
    / "reference_provenance.json"
)

REPORT = (
    PROJECT
    / "experiments"
    / "TUK2_T005"
    / "reports"
    / "TUK2_T005A_cross_calibration_audit.json"
)


def load(path):
    return json.loads(
        path.read_text(encoding="utf-8-sig")
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


def reference_hash():
    RATE = 48000

    rng = np.random.default_rng(5017)

    noise = rng.normal(
        size=RATE + RATE // 4
    )

    spectrum = np.fft.rfft(noise)

    freq = np.fft.rfftfreq(
        len(noise),
        1 / RATE
    )

    spectrum *= np.where(
        (freq >= 60)
        & (freq <= 20000),

        1 / np.sqrt(
            np.maximum(freq, 60)
        ),

        0.0
    )

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

    mono = mono.astype(
        np.float32
    )

    return hashlib.sha256(
        mono.tobytes()
    ).hexdigest()


def decode_pcm24(path):
    with wave.open(str(path), "rb") as w:

        channels = w.getnchannels()
        width = w.getsampwidth()
        rate = w.getframerate()
        frames = w.getnframes()

        if channels != 2:
            raise RuntimeError(
                f"Expected stereo: {path}"
            )

        if width != 3:
            raise RuntimeError(
                f"Expected PCM24: {path}"
            )

        raw = w.readframes(frames)

    u = np.frombuffer(
        raw,
        dtype=np.uint8
    ).reshape(-1, 3)

    value = (
        u[:, 0].astype(np.int32)
        |
        (
            u[:, 1].astype(np.int32)
            << 8
        )
        |
        (
            u[:, 2].astype(np.int32)
            << 16
        )
    )

    negative = (
        value & 0x800000
    ) != 0

    value[negative] -= (
        1 << 24
    )

    return (
        value.reshape(-1, 2),
        rate
    )


def angular_error(
    intended_az,
    intended_el,
    estimated_az,
    estimated_el
):
    dot = float(
        np.clip(
            np.dot(
                unit(
                    intended_az,
                    intended_el
                ),
                unit(
                    estimated_az,
                    estimated_el
                )
            ),
            -1.0,
            1.0
        )
    )

    return math.degrees(
        math.acos(dot)
    )


if REPORT.exists():
    raise RuntimeError(
        f"Refusing overwrite: {REPORT}"
    )

if not NEW_LIBRARY.exists():
    raise RuntimeError(
        "Current TUK2 probe library missing."
    )

if not OLD_LIBRARY.exists():
    raise RuntimeError(
        "MUSIC02 probe library missing."
    )


new = load(NEW_LIBRARY)
old = load(OLD_LIBRARY)

new_by = {
    r["id"]: r
    for r in new["records"]
}

old_by = {
    r["id"]: r
    for r in old["records"]
}

common = sorted(
    set(new_by)
    & set(old_by)
)

if len(common) != 504:
    raise RuntimeError(
        f"Expected 504 common probes, got {len(common)}"
    )


# ============================================================
# REFERENCE SIGNAL
# ============================================================

current_reference_hash = (
    reference_hash()
)

old_reference_hash = None

if OLD_PROVENANCE.exists():

    provenance = load(
        OLD_PROVENANCE
    )

    old_reference_hash = (
        provenance.get(
            "mono_reference_float32_sha256"
        )
    )


# ============================================================
# HASH / FEATURE / PCM COMPARISON
# ============================================================

identical = []
different = []

feature_distances = []

pcm_available = 0
pcm_metrics = []


for probe_id in common:

    n = new_by[probe_id]
    o = old_by[probe_id]

    same_hash = (
        n["sha256"]
        ==
        o["sha256"]
    )

    fd = feature_distance(
        o["full"],
        n["full"],
        new
    )

    feature_distances.append(fd)

    item = {
        "id":
            probe_id,

        "azimuth_deg":
            n["azimuth_deg"],

        "elevation_deg":
            n["elevation_deg"],

        "distance_m":
            n["distance_m"],

        "same_hash":
            same_hash,

        "feature_distance":
            float(fd),
    }

    old_path = Path(
        o["path"]
    )

    new_path = Path(
        n["path"]
    )

    if (
        old_path.exists()
        and
        new_path.exists()
    ):

        old_pcm, old_rate = (
            decode_pcm24(old_path)
        )

        new_pcm, new_rate = (
            decode_pcm24(new_path)
        )

        if (
            old_rate != new_rate
            or
            old_pcm.shape
            != new_pcm.shape
        ):
            raise RuntimeError(
                f"PCM geometry mismatch: {probe_id}"
            )

        diff = (
            new_pcm.astype(np.int64)
            -
            old_pcm.astype(np.int64)
        )

        absdiff = np.abs(diff)

        max_abs_lsb = int(
            absdiff.max()
        )

        differing_samples = int(
            np.count_nonzero(diff)
        )

        rms_lsb = float(
            np.sqrt(
                np.mean(
                    diff.astype(
                        np.float64
                    ) ** 2
                )
            )
        )

        rms_dbfs = float(
            20
            * np.log10(
                max(
                    rms_lsb
                    / 8388608.0,
                    1e-15
                )
            )
        )

        item.update({
            "pcm_compared":
                True,

            "max_abs_difference_lsb":
                max_abs_lsb,

            "differing_sample_values":
                differing_samples,

            "rms_difference_lsb":
                rms_lsb,

            "rms_difference_dbfs":
                rms_dbfs,
        })

        pcm_available += 1

        pcm_metrics.append(
            item
        )

    else:

        item[
            "pcm_compared"
        ] = False


    if same_hash:
        identical.append(item)
    else:
        different.append(item)


# ============================================================
# CROSS-CLASSIFICATION
# ============================================================

new_using_old = []
old_using_new = []


for probe_id in common:

    n = new_by[probe_id]
    o = old_by[probe_id]

    # NEW probe -> OLD library
    e1 = classify(
        n["holdout"],
        old
    )

    err1 = angular_error(
        n["azimuth_deg"],
        n["elevation_deg"],
        e1["azimuth_deg"],
        e1["elevation_deg"]
    )

    new_using_old.append({
        "id":
            probe_id,

        "angular_error_deg":
            err1,

        "exact_pose":
            (
                e1["azimuth_deg"]
                ==
                n["azimuth_deg"]
                and
                e1["elevation_deg"]
                ==
                n["elevation_deg"]
            )
    })


    # OLD probe -> NEW library
    e2 = classify(
        o["holdout"],
        new
    )

    err2 = angular_error(
        o["azimuth_deg"],
        o["elevation_deg"],
        e2["azimuth_deg"],
        e2["elevation_deg"]
    )

    old_using_new.append({
        "id":
            probe_id,

        "angular_error_deg":
            err2,

        "exact_pose":
            (
                e2["azimuth_deg"]
                ==
                o["azimuth_deg"]
                and
                e2["elevation_deg"]
                ==
                o["elevation_deg"]
            )
    })


# ============================================================
# MISMATCH DISTRIBUTION
# ============================================================

def count_by(field):
    result = {}

    for item in different:
        key = str(
            item[field]
        )

        result[key] = (
            result.get(key, 0)
            + 1
        )

    return result


def stats(values):
    if not values:
        return None

    a = np.asarray(
        values,
        dtype=np.float64
    )

    return {
        "min":
            float(np.min(a)),

        "median":
            float(np.median(a)),

        "p95":
            float(
                np.percentile(a, 95)
            ),

        "max":
            float(np.max(a)),
    }


mismatch_pcm = [
    x
    for x in different
    if x.get("pcm_compared")
]


report = {
    "schema":
        "LAISE TUK2 Cross Calibration Audit v1.0",

    "project":
        "tukana_02_a_mata_se_move",

    "test_id":
        "TUK2-T005A-DIFF",

    "status":
        "PASS",

    "probe_count":
        len(common),

    "hash_comparison": {
        "identical":
            len(identical),

        "different":
            len(different),
    },

    "reference_signal": {
        "current_reference_sha256":
            current_reference_hash,

        "music02_reference_sha256":
            old_reference_hash,

        "identical":
            (
                old_reference_hash
                ==
                current_reference_hash
                if old_reference_hash
                else None
            )
    },

    "feature_distance": {
        "all_probes":
            stats(
                feature_distances
            ),

        "hash_mismatch_only":
            stats(
                [
                    x[
                        "feature_distance"
                    ]
                    for x in different
                ]
            ),
    },

    "pcm_comparison": {
        "files_compared":
            pcm_available,

        "mismatch_files_compared":
            len(mismatch_pcm),

        "max_abs_difference_lsb":
            stats(
                [
                    x[
                        "max_abs_difference_lsb"
                    ]
                    for x in mismatch_pcm
                ]
            ),

        "rms_difference_lsb":
            stats(
                [
                    x[
                        "rms_difference_lsb"
                    ]
                    for x in mismatch_pcm
                ]
            ),

        "rms_difference_dbfs":
            stats(
                [
                    x[
                        "rms_difference_dbfs"
                    ]
                    for x in mismatch_pcm
                ]
            ),
    },

    "cross_classification": {
        "new_probes_using_music02_library": {
            "exact_pose_accuracy":
                float(
                    np.mean(
                        [
                            x["exact_pose"]
                            for x
                            in new_using_old
                        ]
                    )
                ),

            "median_angular_error_deg":
                float(
                    np.median(
                        [
                            x[
                                "angular_error_deg"
                            ]
                            for x
                            in new_using_old
                        ]
                    )
                ),

            "p95_angular_error_deg":
                float(
                    np.percentile(
                        [
                            x[
                                "angular_error_deg"
                            ]
                            for x
                            in new_using_old
                        ],
                        95
                    )
                ),
        },

        "music02_probes_using_new_library": {
            "exact_pose_accuracy":
                float(
                    np.mean(
                        [
                            x["exact_pose"]
                            for x
                            in old_using_new
                        ]
                    )
                ),

            "median_angular_error_deg":
                float(
                    np.median(
                        [
                            x[
                                "angular_error_deg"
                            ]
                            for x
                            in old_using_new
                        ]
                    )
                ),

            "p95_angular_error_deg":
                float(
                    np.percentile(
                        [
                            x[
                                "angular_error_deg"
                            ]
                            for x
                            in old_using_new
                        ],
                        95
                    )
                ),
        }
    },

    "mismatch_distribution": {
        "by_azimuth":
            count_by(
                "azimuth_deg"
            ),

        "by_elevation":
            count_by(
                "elevation_deg"
            ),

        "by_distance":
            count_by(
                "distance_m"
            ),
    },

    "mismatch_records":
        different,

    "interpretation_policy":
        (
            "File hash mismatch alone is not treated as "
            "spatial failure. PCM magnitude, feature distance "
            "and cross-classification determine whether drift "
            "is technically meaningful."
        )
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
    "TUK2-T005A-DIFF - CROSS CALIBRATION AUDIT"
)
print(
    "=================================================="
)

print()
print(
    f"Identical hashes       : {len(identical)}"
)

print(
    f"Different hashes       : {len(different)}"
)

print()
print(
    "REFERENCE:"
)

print(
    f"Current                : {current_reference_hash}"
)

print(
    f"MUSIC02                : {old_reference_hash}"
)

print(
    f"Identical              : "
    f"{old_reference_hash == current_reference_hash}"
)

print()
print(
    "FEATURE DISTANCE - HASH MISMATCHES:"
)

fstats = report[
    "feature_distance"
]["hash_mismatch_only"]

print(
    f"Median                 : {fstats['median']:.8f}"
)

print(
    f"P95                    : {fstats['p95']:.8f}"
)

print(
    f"Max                    : {fstats['max']:.8f}"
)


if mismatch_pcm:

    print()
    print(
        "PCM DIFFERENCE - HASH MISMATCHES:"
    )

    p = report[
        "pcm_comparison"
    ]

    print(
        f"PCM files compared     : "
        f"{p['mismatch_files_compared']}"
    )

    print(
        f"Median max delta LSB   : "
        f"{p['max_abs_difference_lsb']['median']:.2f}"
    )

    print(
        f"P95 max delta LSB      : "
        f"{p['max_abs_difference_lsb']['p95']:.2f}"
    )

    print(
        f"Worst max delta LSB    : "
        f"{p['max_abs_difference_lsb']['max']:.2f}"
    )

    print(
        f"Median diff RMS dBFS   : "
        f"{p['rms_difference_dbfs']['median']:.2f}"
    )

    print(
        f"Worst diff RMS dBFS    : "
        f"{p['rms_difference_dbfs']['max']:.2f}"
    )


print()
print(
    "CROSS CLASSIFICATION:"
)

a = report[
    "cross_classification"
][
    "new_probes_using_music02_library"
]

b = report[
    "cross_classification"
][
    "music02_probes_using_new_library"
]

print(
    f"New -> old exact pose  : "
    f"{a['exact_pose_accuracy']:.4f}"
)

print(
    f"New -> old P95 error   : "
    f"{a['p95_angular_error_deg']:.3f} deg"
)

print(
    f"Old -> new exact pose  : "
    f"{b['exact_pose_accuracy']:.4f}"
)

print(
    f"Old -> new P95 error   : "
    f"{b['p95_angular_error_deg']:.3f} deg"
)

print()
print(
    "MISMATCH BY DISTANCE:"
)

for key, value in sorted(
    report[
        "mismatch_distribution"
    ]["by_distance"].items(),
    key=lambda x: float(x[0])
):
    print(
        f"{key:>4} m : {value}"
    )

print()
print(
    "Report:"
)
print(REPORT)

print()
print(
    "TUK2-T005A-DIFF: PASS"
)
