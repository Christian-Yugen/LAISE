from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class RenderJob:
    renderer: str
    asset_path: str
    midi_path: str
    output_path: str
    sample_rate: int
    gain: float
    program: int
    channel: int

class FluidSynthAssetAdapter:
    """
    T010 renderer adapter for SoundFont-based development assets.
    It builds a deterministic command but does not own composition logic.
    """

    def __init__(self, executable: Path):
        self.executable = Path(executable)

    def command(self, job: RenderJob) -> list[str]:
        if job.renderer != "fluidsynth":
            raise ValueError(f"Unsupported renderer for FluidSynth adapter: {job.renderer}")
        return [
            str(self.executable),
            "-ni",
            "-g", str(job.gain),
            "-r", str(job.sample_rate),
            "-F", str(job.output_path),
            str(job.asset_path),
            str(job.midi_path),
        ]

class RendererRouter:
    """
    Keeps room for SFZ/VSTi/sampler adapters without changing the musical engine.
    """
    SUPPORTED = {"fluidsynth"}

    @classmethod
    def ensure_supported(cls, renderer: str):
        if renderer not in cls.SUPPORTED:
            raise NotImplementedError(
                f"Renderer '{renderer}' is registered but has no T010 adapter yet."
            )
