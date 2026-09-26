from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import struct
import subprocess
import wave

import numpy as np


@dataclass(frozen=True)
class HybridRenderAsset:
    role: str
    renderer: str
    asset_path: Path
    asset_id: str
    status: str


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_wav_float(path: Path) -> tuple[np.ndarray, dict]:
    """
    Read common PCM/IEEE-float WAVs into shape (channels, samples).
    Handles sfizz_render output and FluidSynth PCM output.
    """
    raw = path.read_bytes()
    if len(raw) < 44 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError(f"Invalid RIFF/WAVE file: {path}")

    fmt = None
    data = None
    pos = 12

    while pos + 8 <= len(raw):
        chunk_id = raw[pos:pos + 4]
        size = struct.unpack_from("<I", raw, pos + 4)[0]
        body = raw[pos + 8:pos + 8 + size]
        pos += 8 + size + (size & 1)

        if chunk_id == b"fmt ":
            fmt = body
        elif chunk_id == b"data":
            data = body

    if fmt is None or data is None or len(fmt) < 16:
        raise ValueError(f"WAV missing fmt/data chunks: {path}")

    audio_format, channels, sample_rate, _, _, bits = struct.unpack_from(
        "<HHIIHH", fmt, 0
    )

    if audio_format == 1:
        if bits == 16:
            samples = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
        elif bits == 24:
            b = np.frombuffer(data, dtype=np.uint8)
            b = b[: (len(b) // 3) * 3].reshape(-1, 3)
            v = (
                b[:, 0].astype(np.int32)
                | (b[:, 1].astype(np.int32) << 8)
                | (b[:, 2].astype(np.int32) << 16)
            )
            v = np.where(v & 0x800000, v - 0x1000000, v)
            samples = v.astype(np.float32) / 8388608.0
        elif bits == 32:
            samples = np.frombuffer(data, dtype="<i4").astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"Unsupported PCM bit depth: {bits}")
    elif audio_format == 3 and bits == 32:
        samples = np.frombuffer(data, dtype="<f4").astype(np.float32)
    else:
        raise ValueError(
            f"Unsupported WAV format={audio_format}, bits={bits}: {path}"
        )

    frames = len(samples) // channels
    samples = samples[: frames * channels].reshape(frames, channels).T

    if channels == 1:
        samples = np.repeat(samples, 2, axis=0)
    elif channels > 2:
        samples = samples[:2]

    info = {
        "audio_format": audio_format,
        "channels_original": channels,
        "sample_rate": sample_rate,
        "bits_per_sample": bits,
        "frames": frames,
        "duration_seconds": frames / sample_rate,
        "peak": float(np.max(np.abs(samples))) if samples.size else 0.0,
        "rms": float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
        if samples.size else 0.0,
        "finite": bool(np.isfinite(samples).all()),
    }
    return samples.astype(np.float32), info


def write_pcm16(path: Path, x: np.ndarray, sample_rate: int = 48000) -> None:
    x = np.clip(np.nan_to_num(x), -0.999, 0.999)
    raw = (x.T.reshape(-1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(raw.tobytes())


class HybridInstrumentRenderer:
    """
    MUSIC-008 renderer:
    - SFZ/sfizz_render for validated onboarding piano/strings assets.
    - FluidSynth for roles not yet migrated.
    """

    def __init__(
        self,
        project_root: Path,
        sample_rate: int = 48000,
        fluidsynth_gain: float = 0.8,
    ):
        self.root = Path(project_root)
        self.sr = sample_rate
        self.fluidsynth_gain = fluidsynth_gain

        self.sfizz = self.root / "tools" / "sfizz" / "bin" / "Release" / "sfizz_render.exe"
        self.fluidsynth = (
            self.root / "tools" / "fluidsynth" / "bin" / "fluidsynth.exe"
        )
        self.generaluser = (
            self.root / "assets" / "soundfonts" / "GeneralUser GS v1.471.sf2"
        )
        self.salamander = (
            self.root
            / "assets"
            / "sfz"
            / "SalamanderGrandPiano-master"
            / "Salamander Grand Piano V3.sfz"
        )
        self.vsco_root = (
            self.root / "assets" / "sfz" / "VSCO-2-CE-1.1.0"
        )
        self.vsco_sustain = self.vsco_root / "ViolinEnsSusVib.sfz"
        self.vsco_short = self._find_vsco_short_strings()

        required = [
            self.sfizz,
            self.fluidsynth,
            self.generaluser,
            self.salamander,
            self.vsco_sustain,
        ]
        missing = [str(p) for p in required if not p.is_file()]
        if missing:
            raise FileNotFoundError(
                "Required MUSIC-008 asset/tool missing:\n" + "\n".join(missing)
            )

    def _find_vsco_short_strings(self) -> Path | None:
        """
        Find only real short-string instruments.

        T010.1 bug fix:
        The previous heuristic searched the whole VSCO tree and could select
        a non-string staccato instrument (e.g. OboeStac.sfz).  This version
        hard-gates candidates to the Strings family before ranking.
        """
        if not self.vsco_root.is_dir():
            return None

        candidates = []
        for p in self.vsco_root.rglob("*.sfz"):
            name = p.stem.lower()
            path_text = str(p).lower()

            # Hard family gate: never allow woodwinds/brass/percussion here.
            is_string_family = (
                "\\strings\\" in path_text
                or "/strings/" in path_text
                or any(token in name for token in (
                    "violin", "viola", "cello", "bassens", "string"
                ))
            )
            is_short = any(token in name for token in (
                "stac", "stacc", "short", "spic"
            ))
            is_wrong_articulation = any(token in name for token in (
                "pizz", "trem", "sus", "sustain"
            ))

            if is_string_family and is_short and not is_wrong_articulation:
                candidates.append(p)

        if not candidates:
            return None

        def score(p: Path):
            name = p.stem.lower()
            path_text = str(p).lower()
            points = 0

            if "\\strings\\" in path_text or "/strings/" in path_text:
                points += 50
            if "violin" in name:
                points += 28
            if "viola" in name:
                points += 20
            if "cello" in name:
                points += 18
            if "ens" in name or "ensemble" in name:
                points += 18
            if "stac" in name or "stacc" in name:
                points += 35
            if "short" in name or "spic" in name:
                points += 22

            return (-points, len(str(p)), str(p).lower())

        return sorted(candidates, key=score)[0]

    def route(self, role: str) -> HybridRenderAsset:
        if role == "piano":
            return HybridRenderAsset(
                role,
                "sfizz_render",
                self.salamander,
                "LAISE-SFZ-PIANO-SALAMANDER-V3",
                "ONBOARDING_VALIDATED",
            )

        if role in ("strings", "countermelody"):
            return HybridRenderAsset(
                role,
                "sfizz_render",
                self.vsco_sustain,
                "LAISE-SFZ-VSCO2CE-STRINGS-SUS-001",
                "ONBOARDING_VALIDATED",
            )

        if role == "ostinato" and self.vsco_short is not None:
            return HybridRenderAsset(
                role,
                "sfizz_render",
                self.vsco_short,
                "LAISE-SFZ-VSCO2CE-STRINGS-SHORT-001",
                "ONBOARDING_CANDIDATE",
            )

        return HybridRenderAsset(
            role,
            "fluidsynth",
            self.generaluser,
            "LAISE-SF-TEST-0001",
            "TEST_ONLY",
        )

    def render(
        self,
        role: str,
        midi_path: Path,
        wav_path: Path,
    ) -> dict:
        route = self.route(role)

        if route.renderer == "sfizz_render":
            cmd = [
                str(self.sfizz),
                "--sfz",
                str(route.asset_path),
                "--midi",
                str(midi_path),
                "--wav",
                str(wav_path),
                "--samplerate",
                str(self.sr),
                "--use-eot",
            ]
        else:
            cmd = [
                str(self.fluidsynth),
                "-ni",
                "-g",
                str(self.fluidsynth_gain),
                "-r",
                str(self.sr),
                "-F",
                str(wav_path),
                str(route.asset_path),
                str(midi_path),
            ]

        cp = subprocess.run(
            cmd,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if cp.returncode != 0:
            raise RuntimeError(
                f"Render failed for {role} via {route.renderer}.\n"
                f"Exit={cp.returncode}\n{cp.stdout[-5000:]}"
            )

        audio, info = read_wav_float(wav_path)
        if info["sample_rate"] != self.sr:
            raise ValueError(
                f"{role}: expected {self.sr} Hz, got {info['sample_rate']} Hz"
            )
        if not info["finite"] or info["rms"] <= 1e-7:
            raise ValueError(f"{role}: invalid/silent render.")

        return {
            "role": role,
            "renderer": route.renderer,
            "asset_id": route.asset_id,
            "asset_status": route.status,
            "asset_path": str(route.asset_path),
            "asset_sha256": sha256_file(route.asset_path),
            "wav_path": str(wav_path),
            "wav_sha256": sha256_file(wav_path),
            "audio_info": info,
            "console_tail": cp.stdout[-1200:],
            "audio": audio,
        }
