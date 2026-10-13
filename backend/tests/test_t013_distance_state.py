from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
SPATIAL = ROOT / "backend" / "spatial"
if str(SPATIAL) not in sys.path:
    sys.path.insert(0, str(SPATIAL))

from pedalboard import load_plugin
from dearvr_adapter import (
    CALIBRATED_DISTANCE_RAW,
    PLUGIN_PATH,
    configure_direct_signal,
    set_pose,
)


def main() -> None:
    plugin = load_plugin(str(PLUGIN_PATH))
    configure_direct_signal(plugin)
    before = float(plugin.parameters["distance"].raw_value)
    set_pose(plugin, 190.0, 0.0)
    after = float(plugin.parameters["distance"].raw_value)
    checks = {
        "calibrated_state_applied": abs(before - CALIBRATED_DISTANCE_RAW) < 1e-6,
        "pose_preserves_distance": abs(after - before) < 1e-9,
    }
    report = {
        "test_id": "T013-DISTANCE",
        "objective_result": "PASS" if all(checks.values()) else "FAIL",
        "dynamic_distance": "BLOCKED_PENDING_MAPPING_AND_HUMAN_VALIDATION",
        "fixed_distance_m": 3.0,
        "raw_before_pose": before,
        "raw_after_pose": after,
        "validations": checks,
    }
    output = ROOT / "projects" / "tukana" / "reports" / "distance_investigation.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["objective_result"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
