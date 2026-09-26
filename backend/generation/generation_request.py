from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


ALLOWED_STYLES = {
    "cinematic_epic",
    "cinematic_emotional",
    "cinematic_suspense",
}

ALLOWED_EMOTIONS = {
    "hopeful",
    "heroic",
    "dark",
    "melancholic",
    "tense",
    "triumphant",
}


@dataclass(frozen=True)
class GenerationRequest:
    """
    T011.1 — canonical request contract for a NEW LAISE composition.

    The important rule is that the request describes musical intent.
    It does not contain a frozen score, MIDI template, or reference to
    MUSIC-010's notes.
    """

    title: str
    style: str
    duration_seconds: float
    emotion: str
    intensity: float
    seed: int

    bpm: float | None = None
    key: str | None = None
    density: float = 0.65
    variation: float = 0.70
    spatial_profile: str = "cinematic_wide"

    def validate(self) -> None:
        if not self.title.strip():
            raise ValueError("title cannot be empty")

        if self.style not in ALLOWED_STYLES:
            raise ValueError(
                f"unsupported style={self.style}; "
                f"allowed={sorted(ALLOWED_STYLES)}"
            )

        if self.emotion not in ALLOWED_EMOTIONS:
            raise ValueError(
                f"unsupported emotion={self.emotion}; "
                f"allowed={sorted(ALLOWED_EMOTIONS)}"
            )

        if not 30.0 <= float(self.duration_seconds) <= 600.0:
            raise ValueError("duration_seconds must be between 30 and 600")

        for name, value in (
            ("intensity", self.intensity),
            ("density", self.density),
            ("variation", self.variation),
        ):
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

        if self.bpm is not None and not 40.0 <= float(self.bpm) <= 180.0:
            raise ValueError("bpm must be between 40 and 180")

        if not isinstance(self.seed, int):
            raise TypeError("seed must be int")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GenerationRequest":
        req = cls(**data)
        req.validate()
        return req
