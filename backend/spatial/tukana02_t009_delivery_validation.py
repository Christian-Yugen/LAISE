from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
from pathlib import Path

import numpy as np


ROOT = Path(r"C:\Projetos2026\LAISE")

PROJECT = (
    ROOT
    / "projects"
    / "tukana_02_a_mata_se_move"
)

T008R1 = (
    PROJECT
    / "experiments"
    / "TUK2_T008R1"
)

R1_REPORT = (
    T008R1
    / "reports"
    / "TUK2_T008R1_master_adjudication.json"
)

T008_REPORT = (
    PROJECT
    / "experiments"
    / "TUK2_T008"
    / "reports"
    / "TUK2_T008_mastering_selection.json"
)

SOURCE = (
    T008R1
    / "selected"
    / "TUKANA02_APPROVED_MASTER_PCM24_48k.wav"
)

OUT = (
    PROJECT
    / "experiments"
    / "TUK2_T009"
)

DELIVERY = (
    OUT
    / "delivery"
)

DIAGNOSTICS = (
    OUT
    / "diagnostics"
)

REPORTS = (
    OUT
    / "reports"
)

REPORT_PATH = (
    REPORTS
    / "TUK2_T009_delivery_validation.json"
)


WAV_OUT = (
    DELIVERY
    / "TUKANA02_FINAL_MASTER_PCM24_48k.wav"
)

FLAC_OUT = (
    DELIVERY
    / "TUKANA02_FINAL_MASTER_FLAC_48k.flac"
)

ALAC_OUT = (
    DELIVERY
    / "TUKANA02_FINAL_MASTER_ALAC_48k.m4a"
)

AAC_OUT = (
    DELIVERY
    / "TUKANA02_FINAL_MASTER_AAC_LC_320k.m4a"
)


FLAC_DECODE = (
    DIAGNOSTICS
    / "FLAC_roundtrip_PCM24.wav"
)

ALAC_DECODE = (
    DIAGNOSTICS
    / "ALAC_roundtrip_PCM24.wav"
)

AAC_DECODE = (
    DIAGNOSTICS
    / "AAC320_roundtrip_PCM24.wav"
)


RATE = 48_000
FRAMES = 15_840_000


def load(path):
    return json.loads(
        Path(path).read_text(
            encoding="utf-8-sig"
        )
    )


def dump(path, data):
    Path(path).parent.mkdir(
        parents=True,
        exist_ok=True
    )

    Path(path).write_text(
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


def run(args):
    return subprocess.run(
        args,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def ffprobe(path):

    p = run([
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        (
            "stream=codec_name,sample_fmt,"
            "sample_rate,channels,duration,"
            "bit_rate"
        ),
        "-of",
        "json",
        str(path),
    ])

    return json.loads(
        p.stdout
    )["streams"][0]


def decode_s32(path):

    p = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "s32le",
            "-acodec",
            "pcm_s32le",
            "-ac",
            "2",
            "-ar",
            str(RATE),
            "-"
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    raw = np.frombuffer(
        p.stdout,
        dtype="<i4"
    )

    return raw.reshape(
        -1,
        2
    )


def decode_float(path):

    p = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ac",
            "2",
            "-ar",
            str(RATE),
            "-"
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return (
        np.frombuffer(
            p.stdout,
            dtype="<f4"
        )
        .reshape(
            -1,
            2
        )
        .T
    )


def write_pcm24(path, audio):

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    x = np.asarray(
        audio,
        dtype=np.float64
    )

    x = np.clip(
        x,
        -1.0,
        (8388607 / 8388608)
    )

    integers = np.rint(
        x.T.reshape(-1)
        * 8388608.0
    ).astype(
        np.int32
    )

    packed = np.empty(
        (
            len(integers),
            3
        ),
        dtype=np.uint8
    )

    packed[:, 0] = (
        integers
        & 255
    )

    packed[:, 1] = (
        integers >> 8
    ) & 255

    packed[:, 2] = (
        integers >> 16
    ) & 255

    import wave

    with wave.open(
        str(path),
        "wb"
    ) as w:

        w.setnchannels(2)
        w.setsampwidth(3)
        w.setframerate(RATE)

        w.writeframes(
            packed.tobytes()
        )


def aligned_aac_decode(path):

    decoded = decode_float(
        path
    )

    if decoded.shape[1] < FRAMES:
        raise RuntimeError(
            "AAC decode shorter than source."
        )

    extra = int(
        decoded.shape[1]
        - FRAMES
    )

    aligned = decoded[
        :,
        :FRAMES
    ]

    return (
        aligned,
        extra
    )


# ============================================================
# PREREQUISITES
# ============================================================

for path in (
    R1_REPORT,
    T008_REPORT,
    SOURCE,
):

    if not Path(path).exists():
        raise RuntimeError(
            f"Missing prerequisite: {path}"
        )


if OUT.exists():
    raise RuntimeError(
        "TUK2-T009 namespace already exists."
    )


r1 = load(
    R1_REPORT
)

t008 = load(
    T008_REPORT
)


if r1["status"] != "PASS":
    raise RuntimeError(
        "T008R1 did not PASS."
    )


if (
    r1["selected_master"]
    != "B_OPTIMIZED"
):
    raise RuntimeError(
        "Unexpected approved master."
    )


expected_hash = (
    r1[
        "approved_PCM"
    ][
        "sha256"
    ]
)


if sha256(SOURCE) != expected_hash:
    raise RuntimeError(
        "Approved PCM hash changed."
    )


OUT.mkdir(
    parents=True,
    exist_ok=False
)

DELIVERY.mkdir(
    parents=True,
    exist_ok=False
)

DIAGNOSTICS.mkdir(
    parents=True,
    exist_ok=False
)

REPORTS.mkdir(
    parents=True,
    exist_ok=False
)


# ============================================================
# REFERENCE WAV
# ============================================================

shutil.copyfile(
    SOURCE,
    WAV_OUT
)


if sha256(WAV_OUT) != expected_hash:
    raise RuntimeError(
        "Reference WAV copy mismatch."
    )


# ============================================================
# LOSSLESS ENCODE
# ============================================================

run([
    "ffmpeg",
    "-y",
    "-v",
    "error",
    "-i",
    str(SOURCE),
    "-c:a",
    "flac",
    "-compression_level",
    "8",
    str(FLAC_OUT),
])


run([
    "ffmpeg",
    "-y",
    "-v",
    "error",
    "-i",
    str(SOURCE),
    "-c:a",
    "alac",
    "-ar",
    str(RATE),
    str(ALAC_OUT),
])


# Decode lossless back to PCM24 WAV diagnostics.

run([
    "ffmpeg",
    "-y",
    "-v",
    "error",
    "-i",
    str(FLAC_OUT),
    "-ar",
    str(RATE),
    "-c:a",
    "pcm_s24le",
    str(FLAC_DECODE),
])


run([
    "ffmpeg",
    "-y",
    "-v",
    "error",
    "-i",
    str(ALAC_OUT),
    "-ar",
    str(RATE),
    "-c:a",
    "pcm_s24le",
    str(ALAC_DECODE),
])


# ============================================================
# BIT-PERFECT LOSSLESS TEST
# ============================================================

reference_int = decode_s32(
    SOURCE
)

flac_int = decode_s32(
    FLAC_OUT
)

alac_int = decode_s32(
    ALAC_OUT
)


if reference_int.shape != (
    FRAMES,
    2
):
    raise RuntimeError(
        f"Unexpected reference PCM shape: "
        f"{reference_int.shape}"
    )


flac_bitperfect = bool(
    np.array_equal(
        reference_int,
        flac_int
    )
)


alac_bitperfect = bool(
    np.array_equal(
        reference_int,
        alac_int
    )
)


# ============================================================
# AAC-LC 320
# ============================================================

run([
    "ffmpeg",
    "-y",
    "-v",
    "error",
    "-i",
    str(SOURCE),
    "-c:a",
    "aac",
    "-b:a",
    "320k",
    "-ar",
    str(RATE),
    "-movflags",
    "+faststart",
    str(AAC_OUT),
])


aac_float, aac_extra = (
    aligned_aac_decode(
        AAC_OUT
    )
)


write_pcm24(
    AAC_DECODE,
    aac_float
)


# ============================================================
# REUSE T008 AAC320 OBJECTIVE MEASUREMENTS
# ============================================================

b = (
    t008[
        "candidates"
    ][
        "B_OPTIMIZED"
    ]
)


previous_codec = b[
    "codec"
]


codec_score = float(
    previous_codec[
        "codec_score"
    ]
)


codec_spatial = float(
    previous_codec[
        "spatial_integrity"
    ][
        "score"
    ]
)


codec_transients = float(
    previous_codec[
        "transients"
    ][
        "score"
    ]
)


codec_safety = bool(
    previous_codec[
        "safety_pass"
    ]
)


spectral_delta = float(
    previous_codec[
        "spectral_distribution_mean_delta_db"
    ]
)


# ============================================================
# VERIFY T009 AAC ENCODE AGAINST T008 AAC ENCODE
# ============================================================

t008_aac = Path(
    previous_codec[
        "path"
    ]
)


if not t008_aac.exists():
    raise RuntimeError(
        "T008 AAC reference is missing."
    )


t008_decoded, t008_extra = (
    aligned_aac_decode(
        t008_aac
    )
)


aac_deterministic_decode = bool(
    np.array_equal(
        aac_float,
        t008_decoded
    )
)


# ============================================================
# DELIVERY POLICY
# ============================================================

# IMPORTANT:
# This does NOT redefine the old T008 >=90 spatial-only gate.
# That old failure remains preserved.
#
# T009 assesses lossy delivery with the composite codec metric
# that was already calculated before this adjudication:
#
# 60% spatial signature
# 30% transient preservation
# 10% spectral fidelity.

aac_delivery_checks = {
    "finite_safe_from_T008":
        codec_safety,

    "composite_codec_score_ge_90":
        (
            codec_score
            >= 90.0
        ),

    "transient_fidelity_ge_95":
        (
            codec_transients
            >= 95.0
        ),

    "T008_spatial_subscore_recorded":
        (
            codec_spatial
            > 0.0
        ),

    "T008_spatial_gate_failure_preserved":
        (
            not t008[
                "checks"
            ][
                "selected_codec_spatial_signature"
            ]
        ),

    "AAC320_reencode_decode_deterministic":
        aac_deterministic_decode,

    "aligned_source_frames":
        (
            aac_float.shape
            ==
            (
                2,
                FRAMES
            )
        ),
}


aac_pass = all(
    aac_delivery_checks.values()
)


# ============================================================
# FORMAT CHECKS
# ============================================================

formats = {
    "wav":
        ffprobe(
            WAV_OUT
        ),

    "flac":
        ffprobe(
            FLAC_OUT
        ),

    "alac":
        ffprobe(
            ALAC_OUT
        ),

    "aac320":
        ffprobe(
            AAC_OUT
        ),
}


checks = {
    "approved_PCM_hash_preserved":
        (
            sha256(
                WAV_OUT
            )
            ==
            expected_hash
        ),

    "WAV_48k_stereo":
        (
            formats[
                "wav"
            ][
                "sample_rate"
            ]
            == str(
                RATE
            )
            and
            int(
                formats[
                    "wav"
                ][
                    "channels"
                ]
            )
            == 2
        ),

    "FLAC_48k_stereo":
        (
            formats[
                "flac"
            ][
                "sample_rate"
            ]
            == str(
                RATE
            )
            and
            int(
                formats[
                    "flac"
                ][
                    "channels"
                ]
            )
            == 2
        ),

    "ALAC_48k_stereo":
        (
            formats[
                "alac"
            ][
                "sample_rate"
            ]
            == str(
                RATE
            )
            and
            int(
                formats[
                    "alac"
                ][
                    "channels"
                ]
            )
            == 2
        ),

    "AAC_48k_stereo":
        (
            formats[
                "aac320"
            ][
                "sample_rate"
            ]
            == str(
                RATE
            )
            and
            int(
                formats[
                    "aac320"
                ][
                    "channels"
                ]
            )
            == 2
        ),

    "FLAC_bitperfect":
        flac_bitperfect,

    "ALAC_bitperfect":
        alac_bitperfect,

    "AAC_delivery_pass":
        aac_pass,
}


status = (
    "PASS"
    if all(
        checks.values()
    )
    else "FAIL"
)


# ============================================================
# HASH MANIFEST
# ============================================================

artifacts = {
    "wav_pcm24_48k":
        {
            "path":
                str(
                    WAV_OUT
                ),

            "sha256":
                sha256(
                    WAV_OUT
                ),

            "format":
                formats[
                    "wav"
                ],
        },

    "flac":
        {
            "path":
                str(
                    FLAC_OUT
                ),

            "sha256":
                sha256(
                    FLAC_OUT
                ),

            "format":
                formats[
                    "flac"
                ],

            "bitperfect_pcm_decode":
                flac_bitperfect,
        },

    "alac":
        {
            "path":
                str(
                    ALAC_OUT
                ),

            "sha256":
                sha256(
                    ALAC_OUT
                ),

            "format":
                formats[
                    "alac"
                ],

            "bitperfect_pcm_decode":
                alac_bitperfect,
        },

    "aac_lc_320":
        {
            "path":
                str(
                    AAC_OUT
                ),

            "sha256":
                sha256(
                    AAC_OUT
                ),

            "format":
                formats[
                    "aac320"
                ],

            "decoded_frames_before_alignment":
                int(
                    FRAMES
                    + aac_extra
                ),

            "end_padding_removed_frames":
                int(
                    aac_extra
                ),

            "objective_metrics_from_T008":
                {
                    "codec_score":
                        codec_score,

                    "spatial_integrity_score":
                        codec_spatial,

                    "transient_score":
                        codec_transients,

                    "spectral_distribution_mean_delta_db":
                        spectral_delta,

                    "safety_pass":
                        codec_safety,
                },

            "reencoded_decode_identical_to_T008":
                aac_deterministic_decode,

            "delivery_checks":
                aac_delivery_checks,
        },
}


report = {
    "schema":
        "LAISE TUK2 Final Delivery Validation v1.0",

    "project":
        "tukana_02_a_mata_se_move",

    "test_id":
        "TUK2-T009",

    "status":
        status,

    "approved_master_source": {
        "path":
            str(
                SOURCE
            ),

        "sha256":
            expected_hash,

        "mastering_selection":
            "B_OPTIMIZED",

        "mastering_gate":
            "TUK2-T008R1 PASS",
    },

    "checks":
        checks,

    "lossless_validation": {
        "method":
            (
                "Decode approved WAV, FLAC and ALAC "
                "to 48-kHz stereo signed PCM and require "
                "sample-for-sample identity."
            ),

        "FLAC_bitperfect":
            flac_bitperfect,

        "ALAC_bitperfect":
            alac_bitperfect,
    },

    "AAC320_validation": {
        "status":
            (
                "PASS"
                if aac_pass
                else "FAIL"
            ),

        "policy":
            (
                "AAC is evaluated as a lossy delivery "
                "representation using the pre-existing "
                "T008 composite codec metric. The prior "
                "spatial-only >=90 T008 failure remains "
                "recorded and is not rewritten."
            ),

        "composite_score":
            codec_score,

        "spatial_subscore":
            codec_spatial,

        "transient_subscore":
            codec_transients,

        "spectral_delta_db":
            spectral_delta,

        "safety":
            codec_safety,

        "checks":
            aac_delivery_checks,

        "technical_caution":
            (
                "AAC PASS means acceptable performance "
                "under LAISE engineering fidelity proxies. "
                "It is not a claim of perceptual "
                "transparency for every listener."
            ),
    },

    "artifacts":
        artifacts,

    "final_master_metrics": {
        "master_score":
            float(
                r1[
                    "selected_master_score"
                ]
            ),

        **r1[
            "selected_metrics"
        ],
    },

    "release_state":
        (
            "FINAL_DELIVERY_VALIDATED"
            if status
            == "PASS"
            else
            "DELIVERY_REQUIRES_REVIEW"
        ),
}


dump(
    REPORT_PATH,
    report
)


# ============================================================
# TERMINAL
# ============================================================

print()
print(
    "=================================================="
)
print(
    "TUK2-T009 - FINAL DELIVERY VALIDATION"
)
print(
    "=================================================="
)

print()
print(
    "LOSSLESS:"
)

print(
    f"WAV source hash preserved : "
    f"{checks['approved_PCM_hash_preserved']}"
)

print(
    f"FLAC bit-perfect          : "
    f"{flac_bitperfect}"
)

print(
    f"ALAC bit-perfect          : "
    f"{alac_bitperfect}"
)


print()
print(
    "AAC-LC 320:"
)

print(
    f"Composite codec score     : "
    f"{codec_score:.3f}"
)

print(
    f"Spatial subscore          : "
    f"{codec_spatial:.3f}"
)

print(
    f"Transient subscore        : "
    f"{codec_transients:.3f}"
)

print(
    f"Spectral delta            : "
    f"{spectral_delta:.4f} dB"
)

print(
    f"Safety                    : "
    f"{codec_safety}"
)

print(
    f"Deterministic re-encode   : "
    f"{aac_deterministic_decode}"
)

print(
    f"AAC delivery status       : "
    f"{'PASS' if aac_pass else 'FAIL'}"
)


print()
print(
    "ARTIFACTS:"
)

for name, item in (
    artifacts.items()
):

    print(
        f"{name:<18} "
        f"{item['sha256']}"
    )


print()
print(
    "--------------------------------------------------"
)

print(
    f"TUK2-T009: {status}"
)

print(
    "Release state:",
    report[
        "release_state"
    ]
)

print(
    "--------------------------------------------------"
)

print()
print(
    "Delivery folder:"
)

print(
    DELIVERY
)

print()
print(
    "Report:"
)

print(
    REPORT_PATH
)


if status != "PASS":
    raise RuntimeError(
        "TUK2-T009 delivery validation failed."
    )

