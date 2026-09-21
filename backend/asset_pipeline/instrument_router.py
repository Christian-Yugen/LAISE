from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List

from asset_registry import AssetRegistry

@dataclass(frozen=True)
class InstrumentRequest:
    role: str
    articulation: str
    intensity: float
    mode: str = "development"

@dataclass(frozen=True)
class ResolvedInstrument:
    role: str
    requested_articulation: str
    resolved_articulation: str
    asset_id: str
    renderer: str
    program: int
    channel: int
    articulation_mode: str
    path: str

ROLE_PROGRAMS = {
    "piano": (0, 0),
    "theme": (73, 0),
    "strings": (48, 0),
    "bass": (42, 0),
    "ostinato": (48, 0),
    "percussion": (0, 9),
    "brass": (61, 0),
    "countermelody": (40, 0),
    "brass_attack": (61, 0),
    "braam": (61, 0),
    "ping": (0, 0),
}

ROLE_FAMILY = {
    "piano": "piano",
    "theme": "solo",
    "strings": "strings",
    "bass": "low_strings",
    "ostinato": "strings",
    "percussion": "percussion",
    "brass": "brass",
    "countermelody": "strings",
    "brass_attack": "brass",
    "braam": "brass",
    "ping": "piano",
}

ARTICULATION_FALLBACK = {
    "legato": ("legato", "sustain", "performance_simulated"),
    "sustain": ("sustain", "performance_simulated"),
    "staccato": ("staccato", "marcato", "short", "performance_simulated"),
    "marcato": ("marcato", "staccato", "short", "performance_simulated"),
    "tremolo": ("tremolo", "sustain", "performance_simulated"),
    "accent": ("accent", "marcato", "short", "performance_simulated"),
    "hit": ("hit", "short", "performance_simulated"),
}

class InstrumentRouter:
    """
    Selects an approved asset by role and articulation without coupling the
    composition engine to a vendor, file format or sampler.
    """

    def __init__(self, registry: AssetRegistry):
        self.registry = registry

    def _candidate_assets(self, role: str):
        family = ROLE_FAMILY.get(role, role)
        return [
            a for a in self.registry.all()
            if family in a.instruments or "*" in a.instruments
        ]

    def resolve(self, req: InstrumentRequest) -> ResolvedInstrument:
        if req.role not in ROLE_PROGRAMS:
            raise KeyError(f"No routing definition for role: {req.role}")
        if not 0.0 <= req.intensity <= 1.0:
            raise ValueError("intensity must be between 0.0 and 1.0")

        candidates = self._candidate_assets(req.role)
        if not candidates:
            raise LookupError(f"No asset available for role: {req.role}")

        fallbacks = ARTICULATION_FALLBACK.get(
            req.articulation,
            (req.articulation, "sustain", "performance_simulated")
        )

        chosen = None
        resolved_articulation = None
        for art in fallbacks:
            for asset in candidates:
                if art in asset.articulations or "*" in asset.articulations:
                    chosen = asset
                    resolved_articulation = art
                    break
            if chosen:
                break

        if not chosen:
            raise LookupError(
                f"No articulation route for role={req.role}, articulation={req.articulation}"
            )

        self.registry.assert_release_allowed([chosen.asset_id], mode=req.mode)

        program, channel = ROLE_PROGRAMS[req.role]
        articulation_mode = (
            "native"
            if resolved_articulation not in {"performance_simulated"}
            else "performance_simulation"
        )

        return ResolvedInstrument(
            role=req.role,
            requested_articulation=req.articulation,
            resolved_articulation=resolved_articulation,
            asset_id=chosen.asset_id,
            renderer=chosen.renderer,
            program=program,
            channel=channel,
            articulation_mode=articulation_mode,
            path=str(self.registry.resolved_path(chosen.asset_id)),
        )
