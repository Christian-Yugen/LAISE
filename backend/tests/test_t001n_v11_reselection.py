from __future__ import annotations

import hashlib
import json
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPT_DIR = ROOT / "backend" / "spatial" / "optimization"
if str(OPT_DIR) not in sys.path:
    sys.path.insert(0, str(OPT_DIR))

from optimizer import select_v11

SOURCE_DIR = ROOT / "evidence" / "T001" / "T001-N"
SOURCE_RESULTS = SOURCE_DIR / "t001n_results.json"
SOURCE_CACHE = SOURCE_DIR / "render_cache"

OUT = ROOT / "evidence" / "T001" / "T001-N-v11"
BLIND = OUT / "blind_finalists"
PRIVATE = OUT / "PRIVATE"
RESULTS = OUT / "t001n_v11_results.json"
KEY = PRIVATE / "t001n_v11_blind_key.json"
LISTENER_SHEET = OUT / "listener_sheet.json"

SEED = 20262311


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_source_records():
    if not SOURCE_RESULTS.is_file():
        raise FileNotFoundError(
            f"Missing source results: {SOURCE_RESULTS}"
        )

    payload = json.loads(
        SOURCE_RESULTS.read_text(encoding="utf-8")
    )

    # v1.0 persisted the complete shortlist candidates in "finalists"
    # and the 30 strongest machine-ranked candidates in "top30".
    # For v1.1 we deliberately use the union of those persisted records.
    #
    # This means NO dearVR rerendering occurs.
    raw = []
    for key in ("top30", "finalists"):
        value = payload.get(key, [])
        if isinstance(value, list):
            raw.extend(value)

    dedup = {}
    for record in raw:
        candidate = record.get("candidate", {})
        cid = candidate.get("candidate_id")
        if cid:
            dedup[cid] = record

    records = list(dedup.values())
    if len(records) < 8:
        raise RuntimeError(
            "The persisted T001-N result does not contain enough "
            "candidate records for reselection."
        )

    return records, payload


def resolve_cached_wav(record):
    candidate_id = record["candidate"]["candidate_id"]

    preferred = SOURCE_CACHE / f"{candidate_id}.wav"
    if preferred.is_file():
        return preferred

    old = record.get("wav")
    if old:
        old_path = Path(old)
        if old_path.is_file():
            return old_path

    raise FileNotFoundError(
        f"Cached WAV not found for {candidate_id}"
    )


def write_listener_sheet(ids):
    template = {
        "test_id": "T001-N-v1.1",
        "WARNING": (
            "Do not open PRIVATE/t001n_v11_blind_key.json "
            "before all ratings are frozen."
        ),
        "scale_externalization": {
            "0": "completely inside head",
            "1": "predominantly inside",
            "2": "near forehead/face",
            "3": "beginning to externalize in front",
            "4": "clearly outside and in front",
            "5": "convincing external frontal source",
        },
        "scale_centrality": {
            "0": "clearly displaced to one side",
            "1": "strongly lateral",
            "2": "slightly lateral",
            "3": "approximately central",
            "4": "central",
            "5": "perfectly central",
        },
        "ratings": {
            bid: {
                "externalization": None,
                "centrality": None,
                "perceived_position": "",
                "confidence_0_to_3": None,
            }
            for bid in ids
        },
    }
    LISTENER_SHEET.write_text(
        json.dumps(template, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main():
    print("=" * 78)
    print("LAISE — T001-N v1.1")
    print("Diversity Reselection — NO dearVR rerendering")
    print("=" * 78)

    OUT.mkdir(parents=True, exist_ok=True)
    BLIND.mkdir(parents=True, exist_ok=True)
    PRIVATE.mkdir(parents=True, exist_ok=True)

    records, source_payload = load_source_records()
    print(f"Persisted unique candidates available: {len(records)}")

    # Use all persisted unique records. The selector itself ranks them.
    selected, diagnostics = select_v11(
        records,
        n=8,
        pool_size=len(records),
        max_per_exact_distance=2,
        min_same_distance_gain_gap_db=6.0,
        min_descriptor_distance=0.035,
        min_unique_distances=4,
        min_distance_span_m=0.6,
    )

    print(f"Selected: {len(selected)}")
    print(
        "Unique distances:",
        diagnostics["unique_distances"],
    )
    print(
        "Distance span:",
        f'{diagnostics["distance_span_m"]:.2f} m',
    )
    print(
        "Max at same distance:",
        diagnostics["max_candidates_same_distance"],
    )
    print(
        "Distance counts:",
        diagnostics["distance_counts"],
    )

    # Remove stale blind files if this script is rerun.
    for old in BLIND.glob("t001n_v11_*.wav"):
        old.unlink()

    blind_ids = list("ABCDEFGH")
    shuffled = selected.copy()
    random.Random(SEED).shuffle(shuffled)

    mapping = {}

    for blind_id, record in zip(blind_ids, shuffled):
        source_wav = resolve_cached_wav(record)
        destination = BLIND / f"t001n_v11_{blind_id}.wav"
        shutil.copy2(source_wav, destination)

        mapping[blind_id] = {
            "source_candidate_id": (
                record["candidate"]["candidate_id"]
            ),
            "candidate": record["candidate"],
            "features": record["features"],
            "combined_score": record["combined_score"],
            "acoustic_score": record.get("acoustic_score"),
            "human_prior_score": record.get(
                "human_prior_score"
            ),
            "source_sha256": sha256(source_wav),
            "blind_sha256": sha256(destination),
        }

    write_listener_sheet(blind_ids)

    KEY.write_text(
        json.dumps(
            {
                "WARNING": (
                    "DO NOT OPEN BEFORE HUMAN RATINGS "
                    "ARE FROZEN."
                ),
                "test_id": "T001-N-v1.1",
                "seed": SEED,
                "mapping": mapping,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    gates = diagnostics["gates"]
    validations = {
        "source_results_found": SOURCE_RESULTS.is_file(),
        "no_rerendering_required": True,
        "eight_finalists": gates["eight_finalists"],
        "max_two_per_exact_distance": (
            gates["max_two_per_exact_distance"]
        ),
        "at_least_four_unique_distances": (
            gates["at_least_four_unique_distances"]
        ),
        "distance_span_at_least_0_6m": (
            gates["distance_span_at_least_0_6m"]
        ),
        "unique_parameter_pairs": (
            gates["unique_parameter_pairs"]
        ),
        "eight_blind_files_created": all(
            (BLIND / f"t001n_v11_{bid}.wav").is_file()
            for bid in blind_ids
        ),
    }

    objective = (
        "PASS"
        if all(validations.values())
        else "FAIL"
    )

    result_payload = {
        "test_id": "T001-N-v1.1",
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "objective_result": objective,
        "human_result": "PENDING",
        "source_test": "T001-N v1.0",
        "source_results": str(SOURCE_RESULTS),
        "persisted_candidate_count": len(records),
        "diagnostics": diagnostics,
        "validations": validations,
        "selected_machine_records": selected,
    }

    RESULTS.write_text(
        json.dumps(
            result_payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\n" + "-" * 78)
    print("SELECTED MACHINE CANDIDATES")
    print("-" * 78)
    for i, record in enumerate(
        sorted(
            selected,
            key=lambda r: r["combined_score"],
            reverse=True,
        ),
        1,
    ):
        c = record["candidate"]
        print(
            f"{i:02d}. {c['candidate_id']} | "
            f"{c['distance_m']:.2f} m | "
            f"{c['reflection_gain_db']:+.0f} dB | "
            f"score={record['combined_score']:.6f}"
        )

    print("\n" + "-" * 78)
    print("AUTOMATED AUDIT")
    print("-" * 78)
    for name, value in validations.items():
        print(
            f"{name:<40}"
            f"{'PASS' if value else 'FAIL'}"
        )

    print("\n" + "=" * 78)
    print("T001-N v1.1 OBJECTIVE RESULT:", objective)
    print("T001-N v1.1 HUMAN RESULT: PENDING")
    print("=" * 78)
    print("\nBlind finalists:", BLIND)
    print("Listener sheet:", LISTENER_SHEET)
    print("PRIVATE KEY — DO NOT OPEN:", KEY)
    print("Results:", RESULTS)


if __name__ == "__main__":
    main()
