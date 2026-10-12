from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import math
import re
import struct
import unicodedata

import numpy as np


TARGET_RATE = 48_000
ROLES = (
    "lead_vocal", "backing_vocals", "drums", "bass", "guitar",
    "keyboards", "percussion", "synth", "other", "woodwinds",
)
ALIASES = {
    "lead_vocal": ("lead vocal", "voz principal"),
    "backing_vocals": ("backing vocals", "back vocal", "coro"),
    "drums": ("drums", "drum", "bateria", "tambores"),
    "bass": ("bass", "baixo"),
    "guitar": ("guitar", "guitarra", "violao"),
    "keyboards": ("keyboards", "keyboard", "keys", "teclado", "piano"),
    "percussion": ("percussion", "percussao", "maracas"),
    "synth": ("synth", "sintetizador"),
    "other": ("other", "outros", "ambience", "ambiente", "fx"),
    "woodwinds": ("woodwinds", "woodwind", "flutes", "flautas"),
}


class StemImportError(ValueError):
    pass


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def inspect_wav(path: str | Path) -> dict:
    path = Path(path)
    with path.open("rb") as stream:
        header = stream.read(12)
        if len(header) != 12 or header[:4] != b"RIFF" or header[8:] != b"WAVE":
            raise StemImportError(f"{path.name}: invalid WAV header")
        fmt = None
        data_offset = data_size = None
        while chunk := stream.read(8):
            if len(chunk) != 8:
                raise StemImportError(f"{path.name}: truncated chunk header")
            chunk_id, size = struct.unpack("<4sI", chunk)
            offset = stream.tell()
            if chunk_id == b"fmt ":
                fmt = stream.read(size)
            elif chunk_id == b"data":
                data_offset, data_size = offset, size
                stream.seek(size, 1)
            else:
                stream.seek(size, 1)
            if size & 1:
                stream.seek(1, 1)
    if fmt is None or data_offset is None or len(fmt) < 16:
        raise StemImportError(f"{path.name}: missing fmt/data chunk")
    encoding, channels, rate, _, align, bits = struct.unpack_from("<HHIIHH", fmt)
    if encoding == 0xFFFE and len(fmt) >= 40:
        encoding = struct.unpack_from("<H", fmt, 24)[0]
    supported = (encoding == 1 and bits in (16, 24, 32)) or (encoding == 3 and bits == 32)
    if not supported:
        raise StemImportError(f"{path.name}: unsupported encoding={encoding}, bits={bits}")
    if channels not in (1, 2) or align != channels * bits // 8 or data_size % align:
        raise StemImportError(f"{path.name}: invalid channels or sample alignment")
    return {
        "encoding": encoding, "channels": channels, "sample_rate": rate,
        "bits_per_sample": bits, "block_align": align,
        "data_offset": data_offset, "data_size": data_size,
        "frames": data_size // align, "duration_seconds": data_size / align / rate,
    }


def _decode(raw: bytes, info: dict) -> np.ndarray:
    if info["encoding"] == 3:
        values = np.frombuffer(raw, dtype="<f4").astype(np.float32, copy=False)
    elif info["bits_per_sample"] == 16:
        values = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif info["bits_per_sample"] == 24:
        packed = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        integer = packed[:, 0].astype(np.int32)
        integer |= packed[:, 1].astype(np.int32) << 8
        integer |= packed[:, 2].astype(np.int32) << 16
        integer = np.where(integer & 0x800000, integer - 0x1000000, integer)
        values = integer.astype(np.float32) / 8388608.0
    else:
        values = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    return values.reshape(-1, info["channels"])


def iter_blocks(path: str | Path, block_frames: int = 65_536):
    path = Path(path)
    info = inspect_wav(path)
    with path.open("rb") as stream:
        stream.seek(info["data_offset"])
        remaining = info["frames"]
        while remaining:
            frames = min(block_frames, remaining)
            raw = stream.read(frames * info["block_align"])
            if len(raw) != frames * info["block_align"]:
                raise StemImportError(f"{path.name}: truncated while decoding")
            yield _decode(raw, info)
            remaining -= frames


def iter_normalized_blocks(path: str | Path, target_rate: int = TARGET_RATE,
                           block_frames: int = 65_536):
    """Yield a time-preserving float32 stream without trimming silence."""
    info = inspect_wav(path)
    if info["sample_rate"] == target_rate:
        yield from iter_blocks(path, block_frames)
        return
    ratio = target_rate / info["sample_rate"]
    expected_frames = round(info["frames"] * ratio)
    previous = None
    native_cursor = next_output = 0
    for native in iter_blocks(path, block_frames):
        native_count = len(native)
        if previous is None:
            block, source_start = native, native_cursor
        else:
            block, source_start = np.vstack((previous, native)), native_cursor - 1
        native_cursor += native_count
        source_end = source_start + len(block) - 1
        if native_cursor == info["frames"]:
            last_output = expected_frames - 1
        else:
            last_output = min(expected_frames - 1, math.ceil(source_end * ratio) - 1)
        if last_output >= next_output:
            indices = np.arange(next_output, last_output + 1, dtype=np.float64)
            positions = indices / ratio - source_start
            left = np.clip(np.floor(positions).astype(np.int64), 0, len(block) - 1)
            right = np.minimum(left + 1, len(block) - 1)
            fraction = np.clip((positions - left).astype(np.float32), 0.0, 1.0)[:, None]
            yield (block[left] * (1.0 - fraction) + block[right] * fraction).astype(np.float32)
            next_output = last_output + 1
        previous = native[-1:]

def identify_stems(folder: str | Path, aliases: dict | None = None) -> dict[str, Path]:
    folder = Path(folder)
    if not folder.is_dir():
        raise StemImportError(f"folder not found: {folder}")
    aliases = {**ALIASES, **(aliases or {})}
    found = {}
    for path in sorted(folder.glob("*.wav")):
        name = _normalize(path.stem)
        candidates = []
        for role, role_aliases in aliases.items():
            normalized = [_normalize(alias) for alias in role_aliases]
            if any(re.search(rf"(^| ){re.escape(alias)}( |$)", name) for alias in normalized):
                candidates.append((max(map(len, normalized)), role))
        if candidates:
            role = max(candidates)[1]
            if role in found:
                raise StemImportError(f"duplicate {role}: {found[role].name}, {path.name}")
            found[role] = path.resolve()
    missing = sorted(set(ROLES) - set(found))
    if missing:
        raise StemImportError(f"missing stems: {', '.join(missing)}")
    return found


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def analyze_stem(path: Path, silence_dbfs: float = -60.0, block_frames: int = 4096) -> dict:
    info = inspect_wav(path)
    threshold = 10 ** (silence_dbfs / 20)
    peak = squares = total_sum = 0.0
    samples = clipped = cursor = 0
    regions, region_start = [], None
    for block in iter_blocks(path, block_frames):
        if not np.isfinite(block).all():
            raise StemImportError(f"{path.name}: NaN/Inf samples")
        absolute = np.abs(block)
        peak = max(peak, float(absolute.max()))
        squares += float(np.sum(block.astype(np.float64) ** 2))
        total_sum += float(np.sum(block, dtype=np.float64))
        samples += block.size
        clipped += int(np.count_nonzero(absolute >= 0.999969))
        block_rms = float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))
        if block_rms >= threshold and region_start is None:
            region_start = cursor / info["sample_rate"]
        elif block_rms < threshold and region_start is not None:
            regions.append({"start_seconds": region_start, "end_seconds": cursor / info["sample_rate"]})
            region_start = None
        cursor += len(block)
    if region_start is not None:
        regions.append({"start_seconds": region_start, "end_seconds": info["duration_seconds"]})
    rms = math.sqrt(squares / max(samples, 1))
    return {
        "path": str(path), "sha256": _sha256(path), "wav": info,
        "internal_format": {"sample_rate": TARGET_RATE, "sample_type": "float32",
                            "channels_preserved": info["channels"],
                            "resampling_required": info["sample_rate"] != TARGET_RATE,
                            "expected_frames": round(info["frames"] * TARGET_RATE / info["sample_rate"]),
                            "timeline_origin_seconds": 0.0,
                            "silence_policy": "PRESERVE_ALL",
                            "resampler_delay_frames": 0},
        "metrics": {"peak": peak, "peak_dbfs": 20 * math.log10(max(peak, 1e-12)),
                    "rms": rms, "rms_dbfs": 20 * math.log10(max(rms, 1e-12)),
                    "dc_offset": total_sum / max(samples, 1), "clipped_sample_count": clipped,
                    "silence_threshold_dbfs": silence_dbfs, "active_regions": regions},
    }


def import_folder(folder: str | Path, manifest_path: str | Path, aliases: dict | None = None) -> dict:
    records = {role: analyze_stem(path) for role, path in identify_stems(folder, aliases).items()}
    durations = [record["wav"]["duration_seconds"] for record in records.values()]
    timeline = max(durations)
    aligned = max(durations) - min(durations) <= 1 / TARGET_RATE
    for record in records.values():
        record["synchronization"] = {
            "timeline_start_seconds": 0.0, "initial_silence_preserved": True,
            "duration_difference_seconds": timeline - record["wav"]["duration_seconds"],
        }
    manifest = {
        "schema": "LAISE Stem Import Manifest v1.0", "source_folder": str(Path(folder).resolve()),
        "required_roles": list(ROLES), "stem_count": len(records), "target_sample_rate": TARGET_RATE,
        "target_sample_type": "float32", "streaming_decode": True, "originals_modified": False,
        "timeline_duration_seconds": timeline, "sample_aligned": aligned,
        "status": "PASS" if aligned else "FAIL", "stems": records,
    }
    output = Path(manifest_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest

