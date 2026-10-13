from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SPATIAL = ROOT / "backend" / "spatial"
if str(SPATIAL) not in sys.path:
    sys.path.insert(0, str(SPATIAL))

from tukana_multistem_preview import render_multistem_preview

PROJECT = ROOT / "projects" / "tukana"
REPORT = PROJECT / "reports" / "t014_multistem_preview_validation.json"


def main() -> None:
    report = render_multistem_preview(
        PROJECT / "spatial_scenes" / "tukana_balanced_scene.json",
        PROJECT / "analysis" / "musical_map.json",
        PROJECT,
    )
    sources = report["source_reports"]
    binaural = report["mixes"]["binaural"]["metrics"]
    dry = report["mixes"]["dry_comparison"]["metrics"]
    anchors = {role: sources[role]["trajectory"] == "stable_anchor"
               for role in ("lead_vocal", "drums", "bass")}
    validations = {
        "ten_spatial_stems": len(sources) == 10,
        "all_roles_active_in_interval": len(report["active_roles_from_map"]) == 10,
        "all_stems_exact_duration": all(item["metrics"]["frames"] == 2_160_000 for item in sources.values()),
        "all_stems_finite": all(item["metrics"]["finite"] for item in sources.values()),
        "all_outputs_distinct": len({item["output_sha256"] for item in sources.values()}) == 10,
        "mixes_sample_aligned": binaural["frames"] == dry["frames"] == 2_160_000,
        "no_clipping": binaural["peak"] < 0.999 and dry["peak"] < 0.999,
        "no_nan_inf": binaural["finite"] and dry["finite"],
        "no_large_clicks": binaural["max_block_boundary_delta"] < 0.25,
        "perceptual_level_match": abs(report["mixes"]["rms_difference_db"]) < 0.1,
        "orbit_continuous": report["angular_continuity"]["monotonic"] and
                            report["angular_continuity"]["max_circular_step_deg"] < 0.1,
        "independent_plugin_instances": report["processing"]["isolated_plugin_instance_per_source"],
        "anchors_preserved": all(anchors.values()),
        "distance_fixed_at_3m": report["processing"]["distance_m"] == 3.0 and
                                not report["processing"]["dynamic_distance"],
        "originals_unchanged": report["originals_unchanged"],
    }
    result = "PASS" if all(validations.values()) else "FAIL"
    payload = {"test_id": "T014", "objective_result": result,
               "human_result": "PENDING", "validations": validations,
               "observed": report}
    REPORT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"test_id": "T014", "objective_result": result,
                      "validations": validations, "mixes": report["mixes"],
                      "active_roles": report["active_roles_from_map"]}, indent=2))
    if result != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
