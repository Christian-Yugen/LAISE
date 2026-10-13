from __future__ import annotations

from pathlib import Path
import struct
import sys
import tempfile
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SPATIAL = ROOT / "backend" / "spatial"
if str(SPATIAL) not in sys.path:
    sys.path.insert(0, str(SPATIAL))

from stem_importer import StemImportError, inspect_wav, iter_blocks


def write_pcm(path: Path, audio: np.ndarray, bits: int) -> None:
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(audio.shape[1]); stream.setsampwidth(bits // 8); stream.setframerate(48000)
        if bits == 16:
            raw = (audio * 32767).astype("<i2").tobytes()
        elif bits == 24:
            value = (audio * 8388607).astype(np.int32).reshape(-1)
            packed = np.empty((len(value), 3), dtype=np.uint8)
            packed[:, 0] = value & 255; packed[:, 1] = (value >> 8) & 255; packed[:, 2] = (value >> 16) & 255
            raw = packed.tobytes()
        else:
            raw = (audio * 2147483647).astype("<i4").tobytes()
        stream.writeframes(raw)


def write_float(path: Path, audio: np.ndarray) -> None:
    raw = audio.astype("<f4").tobytes(); channels = audio.shape[1]; align = channels * 4
    fmt = struct.pack("<HHIIHH", 3, channels, 48000, 48000 * align, align, 32)
    with path.open("wb") as stream:
        stream.write(b"RIFF" + struct.pack("<I", 4 + 8 + len(fmt) + 8 + len(raw)) + b"WAVE")
        stream.write(b"fmt " + struct.pack("<I", len(fmt)) + fmt)
        stream.write(b"data" + struct.pack("<I", len(raw)) + raw)


def main() -> None:
    time = np.arange(4800) / 48000
    mono = (0.2 * np.sin(2 * np.pi * 440 * time)).astype(np.float32)[:, None]
    stereo = np.column_stack((mono[:, 0], mono[:, 0] * 0.8))
    with tempfile.TemporaryDirectory(prefix="laise_formats_") as temp:
        folder = Path(temp); paths = []
        for bits in (16, 24, 32):
            path = folder / f"pcm{bits}.wav"; write_pcm(path, mono, bits); paths.append(path)
        float_path = folder / "float32.wav"; write_float(float_path, stereo); paths.append(float_path)
        infos = [inspect_wav(path) for path in paths]
        decoded = [np.concatenate(list(iter_blocks(path, 1024)), axis=0) for path in paths]
        corrupt = folder / "corrupt.wav"; corrupt.write_bytes(b"invalid")
        rejected = False
        try:
            inspect_wav(corrupt)
        except StemImportError:
            rejected = True
    checks = {
        "pcm_16_24_32_supported": {info["bits_per_sample"] for info in infos[:3]} == {16, 24, 32},
        "float32_supported": infos[3]["encoding"] == 3,
        "mono_and_stereo_supported": {audio.shape[1] for audio in decoded} == {1, 2},
        "decoded_length_preserved": all(len(audio) == 4800 for audio in decoded),
        "finite_float32_output": all(audio.dtype == np.float32 and np.isfinite(audio).all() for audio in decoded),
        "corrupt_file_rejected": rejected,
    }
    for name, passed in checks.items():
        print(f"{name:<38}{'PASS' if passed else 'FAIL'}")
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
