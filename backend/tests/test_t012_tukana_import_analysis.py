from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SPATIAL = ROOT / "backend" / "spatial"
if str(SPATIAL) not in sys.path:
    sys.path.insert(0, str(SPATIAL))

from stem_importer import ROLES, identify_stems, import_folder, inspect_wav
from musical_analyzer import build_musical_map


PROJECT = ROOT / "projects" / "tukana"
ORIGINALS = PROJECT / "stems_original"
ANALYSIS = PROJECT / "analysis"
MANIFEST = ANALYSIS / "stem_import_manifest.json"
MUSICAL_MAP = ANALYSIS / "musical_map.json"
REPORT = PROJECT / "reports" / "phase_a_b_validation.json"


def main() -> None:
    for folder in (ANALYSIS, PROJECT / "spatial_scenes", PROJECT / "spatial_stems",
                   PROJECT / "renders", PROJECT / "reports"):
        folder.mkdir(parents=True, exist_ok=True)
    original_stats = {path.name: (path.stat().st_size, path.stat().st_mtime_ns) for path in ORIGINALS.glob("*.wav")}
    identified = identify_stems(ORIGINALS)
    manifest = import_folder(ORIGINALS, MANIFEST)
    musical_map = build_musical_map(manifest, MUSICAL_MAP)
    after_stats = {path.name: (path.stat().st_size, path.stat().st_mtime_ns) for path in ORIGINALS.glob("*.wav")}

    infos = [inspect_wav(path) for path in identified.values()]
    validations = {
        "ten_roles_identified": set(identified) == set(ROLES),
        "all_pcm16_stereo_48k": all(i["encoding"] == 1 and i["bits_per_sample"] == 16 and
                                      i["channels"] == 2 and i["sample_rate"] == 48000 for i in infos),
        "all_12844801_frames": all(i["frames"] == 12_844_801 for i in infos),
        "sample_aligned": manifest["sample_aligned"],
        "streaming_import": manifest["streaming_decode"],
        "hashes_complete": all(len(record["sha256"]) == 64 for record in manifest["stems"].values()),
        "metrics_finite": all(np.isfinite([record["metrics"]["peak"], record["metrics"]["rms"],
                                            record["metrics"]["dc_offset"]]).all()
                              for record in manifest["stems"].values()),
        "originals_unchanged": original_stats == after_stats,
        "bpm_in_valid_range": 70 <= musical_map["bpm"]["bpm"] <= 170,
        "beat_grid_created": len(musical_map["beat_grid_seconds"]) > 100,
        "bar_grid_created": len(musical_map["bar_grid_seconds"]) > 25,
        "entries_for_ten_stems": set(musical_map["stem_events"]) == set(ROLES),
        "transitions_created": len(musical_map["transitions"]) >= 3,
    }
    result = "PASS" if all(validations.values()) else "FAIL"
    payload = {
        "test_id": "T012-A-B", "project": "TUKANA", "objective_result": result,
        "perceptual_result": "PENDING", "validations": validations,
        "observed": {"duration_seconds": manifest["timeline_duration_seconds"],
                     "bpm": musical_map["bpm"],
                     "bar_count": len(musical_map["bar_grid_seconds"]),
                     "transition_count": len(musical_map["transitions"]),
                     "section_count": len(musical_map["sections"])},
        "artifacts": {"import_manifest": str(MANIFEST), "musical_map": str(MUSICAL_MAP)},
    }
    REPORT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if result != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
