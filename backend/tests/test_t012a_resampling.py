from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SPATIAL = ROOT / "backend" / "spatial"
if str(SPATIAL) not in sys.path:
    sys.path.insert(0, str(SPATIAL))

from stem_importer import iter_blocks, iter_normalized_blocks


def write_pcm16(path: Path, audio: np.ndarray, rate: int) -> None:
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(audio.shape[1])
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())


def main() -> None:
    source_rate, target_rate = 44_100, 48_000
    frames = source_rate * 2
    audio = np.zeros((frames, 2), dtype=np.float32)
    impulse_frame = round(0.75 * source_rate)
    audio[impulse_frame, :] = 0.8
    audio[round(1.25 * source_rate):round(1.5 * source_rate), 0] = 0.1

    with tempfile.TemporaryDirectory(prefix="laise_resample_") as temp:
        path = Path(temp) / "timeline.wav"
        write_pcm16(path, audio, source_rate)
        output = np.concatenate(
            list(iter_normalized_blocks(path, target_rate, block_frames=4096)),
            axis=0,
        )
        passthrough = Path(temp) / "passthrough.wav"
        write_pcm16(passthrough, output, target_rate)
        direct = np.concatenate(list(iter_blocks(passthrough, 4096)), axis=0)

    expected_frames = round(frames * target_rate / source_rate)
    detected_impulse = int(np.argmax(np.abs(output[:, 0])))
    expected_impulse = round(impulse_frame * target_rate / source_rate)
    checks = {
        "exact_output_duration": len(output) == expected_frames,
        "timeline_starts_at_zero": float(np.max(np.abs(output[:round(0.70 * target_rate)]))) == 0.0,
        "impulse_time_preserved": abs(detected_impulse - expected_impulse) <= 1,
        "trailing_silence_preserved": float(np.max(np.abs(output[round(1.6 * target_rate):]))) == 0.0,
        "channels_preserved": output.shape[1] == 2,
        "float32_processing": output.dtype == np.float32,
        "48k_passthrough_frame_exact": len(direct) == len(output),
    }
    for name, passed in checks.items():
        print(f"{name:<38}{'PASS' if passed else 'FAIL'}")
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
