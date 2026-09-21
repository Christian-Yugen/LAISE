from __future__ import annotations
import json
from pathlib import Path

def create_blind_sheet(blind_ids):
    return {
        "test_id": "T001-M",
        "status": "PENDING_HUMAN_EVALUATION",
        "scale": {
            "externalization": "0 inside head ... 5 convincing external FRONT",
            "centrality": "0 clearly lateral ... 5 perfectly central",
        },
        "samples": [
            {
                "blind_id": bid,
                "externalization_0_to_5": None,
                "centrality_0_to_5": None,
                "perceived_position": None,
                "confidence_0_to_5": None,
                "notes": None,
            } for bid in blind_ids
        ],
    }

def save_sheet(path: Path, blind_ids):
    path.write_text(json.dumps(create_blind_sheet(blind_ids), indent=2, ensure_ascii=False), encoding="utf-8")
