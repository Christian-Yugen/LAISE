from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SPATIAL = ROOT / "backend" / "spatial"
if str(SPATIAL) not in sys.path:
    sys.path.insert(0, str(SPATIAL))

from tukana_full_renderer import render_full

PROJECT = ROOT / "projects" / "tukana"
REPORT = PROJECT / "reports" / "t015_full_render_validation.json"


def main() -> None:
    original_stats = {path.name: (path.stat().st_size, path.stat().st_mtime_ns)
                      for path in (PROJECT / "stems_original").glob("*.wav")}
    report = render_full(PROJECT / "spatial_scenes" / "tukana_balanced_scene.json", PROJECT)
    after_stats = {path.name: (path.stat().st_size, path.stat().st_mtime_ns)
                   for path in (PROJECT / "stems_original").glob("*.wav")}
    sources = report["source_reports"]; binaural = report["outputs"]["binaural"]
    dry = report["outputs"]["dry_comparison"]
    validations = {
        "ten_full_spatial_stems": len(sources) == 10,
        "all_stems_exact_frames": all(item["metrics"]["frames"] == 12_844_801 for item in sources.values()),
        "all_stems_finite": all(item["metrics"]["finite"] for item in sources.values()),
        "all_stems_no_clipping": all(item["metrics"]["peak"] < 0.999 for item in sources.values()),
        "no_boundary_discontinuity_outliers": all(
            item["metrics"]["max_block_boundary_delta"]
            <= max(0.25, item["metrics"]["max_sample_delta"] * 0.8)
            for item in sources.values()
        ),
        "mix_exact_frames": binaural["metrics"]["frames"] == dry["metrics"]["frames"] == 12_844_801,
        "mix_finite": binaural["metrics"]["finite"] and dry["metrics"]["finite"],
        "mix_headroom": binaural["metrics"]["peak_dbfs"] <= -2.99,
        "mix_no_large_boundary_click": binaural["metrics"]["max_block_boundary_delta"] < 0.25,
        "comparison_level_matched": abs(report["outputs"]["rms_difference_db"]) < 0.1,
        "ebu_r128_measured": binaural["ebu_r128"]["integrated_lufs"] is not None,
        "true_peak_measured": binaural["ebu_r128"]["true_peak_dbtp"] is not None,
        "incremental_processing": report["processing"]["incremental"],
        "independent_instances": report["processing"]["independent_dearvr_instances"],
        "distance_fixed_at_3m": report["processing"]["distance_m"] == 3.0 and
                                not report["processing"]["dynamic_distance"],
        "originals_unchanged": original_stats == after_stats,
        "candidate_not_final_master": report["delivery_status"] == "MASTER_CANDIDATE" and
                                      report["human_approval_required"],
    }
    report["objective_result"] = "PASS" if all(validations.values()) else "FAIL"
    report["human_result"] = "PENDING"
    report["validations"] = validations
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"test_id": "T015", "objective_result": report["objective_result"],
                      "validations": validations, "outputs": report["outputs"],
                      "elapsed_seconds": report["elapsed_seconds"]}, indent=2), flush=True)
    if report["objective_result"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

