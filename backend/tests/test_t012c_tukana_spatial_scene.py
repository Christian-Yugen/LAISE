from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SPATIAL = ROOT / "backend" / "spatial"
if str(SPATIAL) not in sys.path:
    sys.path.insert(0, str(SPATIAL))

from tukana_spatial_composer import write_tukana_scene

PROJECT = ROOT / "projects" / "tukana"
OUTPUT = PROJECT / "spatial_scenes" / "tukana_balanced_scene.json"
REPORT = PROJECT / "reports" / "phase_c_scene_validation.json"


def main() -> None:
    scene = write_tukana_scene(
        PROJECT / "analysis" / "stem_import_manifest.json",
        PROJECT / "analysis" / "musical_map.json",
        ROOT / "config" / "profiles" / "tukana_spatial.json",
        OUTPUT,
    )
    by_role = {source["source_id"]: source for source in scene["sources"]}
    percussion = by_role["percussion"]["keyframes"]
    validations = {
        "ten_sources": len(by_role) == 10,
        "duration_preserved": scene["duration_seconds"] == 267.60002083333336,
        "lead_vocal_stable": len({k["azimuth_deg_unwrapped"] for k in by_role["lead_vocal"]["keyframes"]}) == 1,
        "bass_stable": len({k["azimuth_deg_unwrapped"] for k in by_role["bass"]["keyframes"]}) == 1,
        "drums_stable": len({k["azimuth_deg_unwrapped"] for k in by_role["drums"]["keyframes"]}) == 1,
        "percussion_keyframes_monotonic": all(a["time_seconds"] <= b["time_seconds"] for a, b in zip(percussion, percussion[1:])),
        "woodwinds_follow_transitions": len(by_role["woodwinds"]["keyframes"]) > 4,
        "renderer_independent": scene["renderer_policy"]["scene_is_renderer_independent"],
        "distance_not_overclaimed": scene["renderer_policy"]["requested_distance_is_not_claimed_as_applied"],
        "perceptual_status_pending": scene["renderer_policy"]["frontal_externalization"] == "PENDING_HUMAN_VALIDATION",
    }
    result = "PASS" if all(validations.values()) else "FAIL"
    payload = {"test_id": "T012-C", "objective_result": result,
               "perceptual_result": "PENDING", "validations": validations,
               "scene": str(OUTPUT)}
    REPORT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if result != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
