from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIPE = ROOT / "backend" / "asset_pipeline"

if str(PIPE) not in sys.path:
    sys.path.insert(0, str(PIPE))

from t0104_production_approval import T0104ProductionApproval


def main():
    print("=" * 78)
    print("LAISE — T010.4 | Production Approval + Final LIPP Manifest")
    print("=" * 78)

    approval = T0104ProductionApproval(ROOT)
    result = approval.finalize()

    print("\nFINAL APPROVAL VALIDATION")
    for name, passed in result.checks.items():
        print(
            f"{name:<58}"
            f"{'PASS' if passed else 'FAIL'}"
        )

    print(
        "\nT010.4 OBJECTIVE RESULT:",
        "PASS" if result.passed else "FAIL",
    )

    if result.passed:
        print("WORK STATUS: PRODUCTION_READY")
        print("ASSET STATUS: PRODUCTION_APPROVED")
        print("Registry:", result.registry_path)
        print("LIPP:", result.lipp_path)
        print("Release record:", result.release_record_path)
    else:
        print("WORK STATUS: NOT PROMOTED")
        print(
            "No production promotion was finalized because "
            "one or more governance checks failed."
        )


if __name__ == "__main__":
    main()
