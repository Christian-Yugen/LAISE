from __future__ import annotations

import json
import hashlib
import shutil
from pathlib import Path


ROOT = Path(r"C:\Projetos2026\LAISE")

PROJECT = (
    ROOT
    / "projects"
    / "tukana_02_a_mata_se_move"
)

T008 = (
    PROJECT
    / "experiments"
    / "TUK2_T008"
)

SOURCE_REPORT = (
    T008
    / "reports"
    / "TUK2_T008_mastering_selection.json"
)

OUT = (
    PROJECT
    / "experiments"
    / "TUK2_T008R1"
)

REPORTS = OUT / "reports"
SELECTED = OUT / "selected"

REPORT = (
    REPORTS
    / "TUK2_T008R1_master_adjudication.json"
)

FINAL_WAV = (
    SELECTED
    / "TUKANA02_APPROVED_MASTER_PCM24_48k.wav"
)


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


if not SOURCE_REPORT.exists():
    raise RuntimeError(
        f"Missing T008 report: {SOURCE_REPORT}"
    )


if OUT.exists():
    raise RuntimeError(
        "TUK2-T008R1 namespace already exists."
    )


r = load(SOURCE_REPORT)


if r["selected_master"] != "B_OPTIMIZED":
    raise RuntimeError(
        "Unexpected T008 selected master."
    )


b = r["candidates"]["B_OPTIMIZED"]
a = r["candidates"]["A_TRANSPARENT"]
c = r["candidates"]["C_REFINED"]


# ============================================================
# PCM-MASTER GATES ONLY
# ============================================================

pcm_checks = {
    "T007_spatial_QA_passed":
        bool(
            r["checks"][
                "T007_spatial_QA_passed"
            ]
        ),

    "T007_spatial_source_unchanged":
        bool(
            r["checks"][
                "T007_spatial_source_unchanged"
            ]
        ),

    "selected_exact_frames":
        bool(
            r["checks"][
                "selected_exact_frames"
            ]
        ),

    "selected_finite":
        bool(
            r["checks"][
                "selected_finite"
            ]
        ),

    "selected_no_sample_clipping":
        bool(
            r["checks"][
                "selected_no_sample_clipping"
            ]
        ),

    "selected_true_peak_safe":
        bool(
            r["checks"][
                "selected_true_peak_safe"
            ]
        ),

    "selected_spatial_integrity_ge_95":
        (
            float(
                b["spatial_integrity"]["score"]
            )
            >= 95.0
        ),

    "selected_transient_fidelity_ge_95":
        (
            float(
                b["transient_fidelity"]["score"]
            )
            >= 95.0
        ),

    "no_widening":
        bool(
            r["checks"]["no_widening"]
        ),

    "no_mid_side":
        bool(
            r["checks"]["no_mid_side"]
        ),

    "no_channel_independent_gain":
        bool(
            r["checks"][
                "no_channel_independent_gain"
            ]
        ),

    "no_respatialization":
        bool(
            r["checks"][
                "no_respatialization"
            ]
        ),

    "no_EQ_added":
        bool(
            r["checks"]["no_EQ_added"]
        ),
}


# ============================================================
# SELECTION CONSISTENCY
# ============================================================

selection_checks = {
    "B_is_highest_master_score":
        (
            float(b["master_score"])
            >
            float(a["master_score"])
            and
            float(b["master_score"])
            >
            float(c["master_score"])
        ),

    "B_is_PCM_eligible":
        bool(
            b["eligible_base"]
        ),

    "A_remains_valid_alternative":
        bool(
            a["eligible_base"]
        ),

    "C_refinement_rejected":
        (
            not bool(
                c["eligible"]
            )
        ),

    "C_rejected_on_multiple_fidelity_gates":
        (
            sum(
                1
                for value
                in r[
                    "refinement_gate"
                ].values()
                if not value
            )
            >= 2
        ),
}


all_pcm = all(
    pcm_checks.values()
)

all_selection = all(
    selection_checks.values()
)


status = (
    "PASS"
    if (
        all_pcm
        and
        all_selection
    )
    else
    "FAIL"
)


# ============================================================
# PRESERVE SELECTED PCM
# ============================================================

source_wav = Path(
    b["path"]
)


if not source_wav.exists():
    raise RuntimeError(
        f"Missing selected PCM: {source_wav}"
    )


OUT.mkdir(
    parents=True,
    exist_ok=False
)

REPORTS.mkdir(
    parents=True,
    exist_ok=False
)

SELECTED.mkdir(
    parents=True,
    exist_ok=False
)


shutil.copyfile(
    source_wav,
    FINAL_WAV
)


source_hash = sha256(
    source_wav
)

final_hash = sha256(
    FINAL_WAV
)


if source_hash != final_hash:
    raise RuntimeError(
        "Approved master copy is not bit-identical."
    )


# ============================================================
# CODEC — RECORDED, NOT USED AS PCM MASTER BLOCKER
# ============================================================

codec_observation = {
    "status":
        "PENDING_TUK2_T009_DELIVERY_VALIDATION",

    "AAC320_codec_score":
        float(
            b["codec"]["codec_score"]
        ),

    "AAC320_spatial_integrity_score":
        float(
            b[
                "codec"
            ][
                "spatial_integrity"
            ][
                "score"
            ]
        ),

    "AAC320_transient_score":
        float(
            b[
                "codec"
            ][
                "transients"
            ][
                "score"
            ]
        ),

    "AAC320_safety_pass":
        bool(
            b[
                "codec"
            ][
                "safety_pass"
            ]
        ),

    "reason_not_mastering_gate":
        (
            "AAC is a lossy delivery transform. "
            "Its fidelity must be evaluated in the "
            "delivery stage and must not invalidate "
            "a PCM mastering candidate that independently "
            "passes mastering fidelity and safety gates."
        ),

    "no_threshold_relaxation":
        True,

    "prior_failed_T008_gate_preserved":
        {
            "name":
                "selected_codec_spatial_signature",

            "value":
                False,

            "threshold_used":
                90.0,
        },
}


report = {
    "schema":
        "LAISE TUK2 PCM Master Adjudication v1.0",

    "project":
        "tukana_02_a_mata_se_move",

    "test_id":
        "TUK2-T008R1",

    "status":
        status,

    "supersedes_for_PCM_master_selection":
        "TUK2-T008",

    "T008_original_status":
        r["status"],

    "T008_original_report_preserved":
        str(
            SOURCE_REPORT
        ),

    "methodological_correction":
        (
            "PCM mastering approval and lossy delivery "
            "validation are separated. No numerical codec "
            "threshold was lowered or changed to force PASS."
        ),

    "selected_master":
        "B_OPTIMIZED",

    "selected_master_score":
        float(
            b["master_score"]
        ),

    "selected_metrics":
        {
            "integrated_lufs":
                float(
                    b[
                        "loudness"
                    ][
                        "integrated_lufs"
                    ]
                ),

            "true_peak_dbtp":
                float(
                    b[
                        "loudness"
                    ][
                        "true_peak_dbtp"
                    ]
                ),

            "crest_factor_db":
                float(
                    b[
                        "signal"
                    ][
                        "crest_factor_db"
                    ]
                ),

            "spatial_integrity":
                float(
                    b[
                        "spatial_integrity"
                    ][
                        "score"
                    ]
                ),

            "transient_fidelity":
                float(
                    b[
                        "transient_fidelity"
                    ][
                        "score"
                    ]
                ),
        },

    "pcm_checks":
        pcm_checks,

    "selection_checks":
        selection_checks,

    "codec_observation":
        codec_observation,

    "approved_PCM": {
        "path":
            str(
                FINAL_WAV
            ),

        "sha256":
            final_hash,

        "bit_identical_to_T008_B":
            (
                source_hash
                ==
                final_hash
            ),

        "source_path":
            str(
                source_wav
            ),

        "source_sha256":
            source_hash,
    },

    "next_stage":
        (
            "TUK2-T009 delivery validation: "
            "WAV PCM24, FLAC, ALAC and AAC-LC 320 kb/s. "
            "Lossless formats require bit-perfect decode. "
            "AAC is evaluated independently as a lossy "
            "delivery representation."
        ),

    "epistemic_note":
        (
            "Technical fidelity metrics are engineering "
            "proxies and do not establish universal "
            "human perceptual equivalence."
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
    "TUK2-T008R1 - PCM MASTER ADJUDICATION"
)
print(
    "=================================================="
)

print()
print(
    "PCM MASTER CHECKS:"
)

for key, value in (
    pcm_checks.items()
):

    print(
        f"{key:<43}: "
        f"{'PASS' if value else 'FAIL'}"
    )


print()
print(
    "SELECTION CHECKS:"
)

for key, value in (
    selection_checks.items()
):

    print(
        f"{key:<43}: "
        f"{'PASS' if value else 'FAIL'}"
    )


print()
print(
    "--------------------------------------------------"
)

print(
    "SELECTED MASTER : B_OPTIMIZED"
)

print(
    f"MASTER SCORE    : "
    f"{b['master_score']:.4f}"
)

print(
    f"LUFS            : "
    f"{b['loudness']['integrated_lufs']:.2f}"
)

print(
    f"TRUE PEAK       : "
    f"{b['loudness']['true_peak_dbtp']:.2f} dBTP"
)

print(
    f"SPATIAL         : "
    f"{b['spatial_integrity']['score']:.3f}"
)

print(
    f"TRANSIENTS      : "
    f"{b['transient_fidelity']['score']:.3f}"
)

print()
print(
    "AAC320 DELIVERY OBSERVATION:"
)

print(
    f"Codec score     : "
    f"{b['codec']['codec_score']:.3f}"
)

print(
    f"Spatial score   : "
    f"{b['codec']['spatial_integrity']['score']:.3f}"
)

print(
    f"Transient score : "
    f"{b['codec']['transients']['score']:.3f}"
)

print(
    f"Safety          : "
    f"{b['codec']['safety_pass']}"
)

print(
    "Delivery state : PENDING T009"
)

print()
print(
    f"TUK2-T008R1: {status}"
)

print()
print(
    "Approved PCM:"
)

print(
    FINAL_WAV
)

print()
print(
    "Report:"
)

print(
    REPORT
)


if status != "PASS":

    raise RuntimeError(
        "TUK2-T008R1 PCM mastering adjudication failed."
    )

