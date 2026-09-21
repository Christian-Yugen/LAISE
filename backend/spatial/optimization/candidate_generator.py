from __future__ import annotations
from dataclasses import dataclass, asdict
import itertools

@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    distance_m: float
    reflection_gain_db: float
    virtual_acoustics: str = "MediumRecordingHall"
    reflection: bool = True
    reverb: bool = False
    azimuth_deg: float = 0.0
    elevation_deg: float = 0.0

    def to_dict(self):
        return asdict(self)

def generate_candidates():
    """
    T001-M v0.1 search space.
    Geometry is deliberately frozen at FRONT (0°, 0°).
    Search concentrates on the mechanism supported by T001-L:
    early reflections, plus a small distance interaction.
    """
    distances = [0.75, 1.0, 1.5, 2.0, 3.0, 4.0]
    reflection_gains = [-24.0, -18.0, -15.0, -12.0, -9.0, -6.0, -3.0, 0.0]

    candidates = []
    n = 1
    for distance, gain in itertools.product(distances, reflection_gains):
        candidates.append(Candidate(
            candidate_id=f"M{n:03d}",
            distance_m=distance,
            reflection_gain_db=gain,
        ))
        n += 1

    # Explicit dry controls for distances that matter most.
    for distance in [1.0, 3.0, 6.0]:
        candidates.append({
            "candidate_id": f"M{n:03d}",
            "distance_m": distance,
            "reflection_gain_db": None,
            "virtual_acoustics": "DirectSignal",
            "reflection": False,
            "reverb": False,
            "azimuth_deg": 0.0,
            "elevation_deg": 0.0,
            "family": "dry_control",
        })
        n += 1

    normalized = []
    for c in candidates:
        if isinstance(c, Candidate):
            d = c.to_dict()
            d["family"] = "early_reflection"
            normalized.append(d)
        else:
            normalized.append(c)
    return normalized
