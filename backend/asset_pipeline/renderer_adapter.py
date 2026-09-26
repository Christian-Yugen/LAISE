from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class RenderJob:
    renderer: str
    asset_path: str
    midi_path: str
    output_path: str
    sample_rate: int = 48000
    gain: float = 0.8
    program: int = 0
    channel: int = 0

class FluidSynthAssetAdapter:
    def __init__(self, executable: Path):
        self.executable = Path(executable)

    def command(self, job: RenderJob) -> list[str]:
        if job.renderer != "fluidsynth":
            raise ValueError(f"Unsupported renderer for FluidSynth adapter: {job.renderer}")
        return [
            str(self.executable), "-ni", "-g", str(job.gain),
            "-r", str(job.sample_rate), "-F", str(job.output_path),
            str(job.asset_path), str(job.midi_path),
        ]

class SfizzRenderAdapter:
    """Offline SFZ renderer adapter for sfizz_render."""
    def __init__(self, executable: Path):
        self.executable = Path(executable)

    def command(self, job: RenderJob) -> list[str]:
        if job.renderer != "sfizz_render":
            raise ValueError(f"Unsupported renderer for sfizz adapter: {job.renderer}")
        return [
            str(self.executable),
            "--sfz", str(job.asset_path),
            "--midi", str(job.midi_path),
            "--wav", str(job.output_path),
            "--samplerate", str(job.sample_rate),
            "--use-eot",
        ]

class RendererRouter:
    SUPPORTED = {"fluidsynth", "sfizz_render"}

    @classmethod
    def ensure_supported(cls, renderer: str):
        if renderer not in cls.SUPPORTED:
            raise NotImplementedError(
                f"Renderer '{renderer}' is registered but has no LAISE adapter yet."
            )
