from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "mastering"))

from tukana_mastering import EXPECTED_FRAMES, master_tukana


def main() -> None:
    report = master_tukana(ROOT / "projects" / "tukana")
    assert report["status"] == "PASS", report["tests"]
    assert report["human_review"] == "PENDING"
    assert all(report["tests"].values())
    assert report["artifacts"]["transparent"]["signal"]["frames"] == EXPECTED_FRAMES
    assert report["artifacts"]["youtube"]["signal"]["frames"] == EXPECTED_FRAMES
    print(json.dumps({"test_id": "T016", "status": report["status"],
                      "tests": report["tests"]}, indent=2))


if __name__ == "__main__":
    main()
