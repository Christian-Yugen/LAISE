from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SPATIAL = ROOT / "backend" / "spatial"
if str(SPATIAL) not in sys.path:
    sys.path.insert(0, str(SPATIAL))

from dearvr_adapter import azimuth_to_raw, wrap_azimuth
from tukana_preview_renderer import run

PROJECT = ROOT / "projects" / "tukana"
REPORT = PROJECT / "reports" / "t013_dearvr_preview_validation.json"


def main() -> None:
    report = run(
        PROJECT / "spatial_scenes" / "tukana_balanced_scene.json",
        PROJECT / "renders" / "tukana_preview_180_crossing.wav",
        REPORT,
    )
    angular = report["angular_validation"]
    mix = report["mix"]
    validations = {
        "angles_wrap_equivalently": azimuth_to_raw(190) == azimuth_to_raw(-170),
        "composer_angle_preserved": angular["monotonic_unwrapped"],
        "crosses_wrapped_boundary": angular["wrapped_boundary_crossings"] == 1,
        "circular_step_is_small": angular["max_circular_step_deg"] < 0.1,
        "two_sources_sample_aligned": len({v["frames"] for v in report["sources"].values()}) == 1,
        "all_audio_finite": mix["finite"] and all(v["finite"] for v in report["sources"].values()),
        "no_clipping": mix["peak"] < 0.999,
        "no_large_boundary_click": mix["max_block_boundary_delta"] < 0.25,
        "distance_fixed_at_3m": report["distance_policy"] == {"meters": 3.0, "raw": 0.0969899744, "dynamic": False},
        "wrap_reference": wrap_azimuth(460) == 100,
    }
    result = "PASS" if all(validations.values()) else "FAIL"
    payload = {"test_id": "T013", "objective_result": result,
               "perceptual_result": "PENDING", "validations": validations,
               "observed": report}
    REPORT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if result != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
