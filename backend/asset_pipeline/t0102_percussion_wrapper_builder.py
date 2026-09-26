from __future__ import annotations

from pathlib import Path
import re


class VSCOGeneratedPercussionBuilder:
    """
    Builds LAISE-owned SFZ wrappers around raw CC0 VSCO percussion WAV samples.

    Why this exists:
    VSCO 2 CE contains raw snare/cymbal samples in the downloaded library,
    but the stock SFZ set does not necessarily expose each percussion family
    as a ready-to-route standalone .sfz patch.  T010.2 must never substitute
    timpani for snare/cymbal merely because it is the only existing SFZ preset.

    Generated wrappers are stored OUTSIDE the original VSCO folder:
      assets/generated_sfz/vsco2ce_percussion/
    so the source bundle remains untouched.
    """

    def __init__(self, vsco_root: Path, generated_root: Path):
        self.vsco_root = Path(vsco_root)
        self.generated_root = Path(generated_root)
        self.generated_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _norm(path: Path) -> str:
        return str(path).lower().replace("\\", "/")

    def _all_wavs(self) -> list[Path]:
        return [p for p in self.vsco_root.rglob("*.wav") if p.is_file()]

    def _snare_candidates(self) -> list[Path]:
        wavs = self._all_wavs()
        return sorted(
            [
                p for p in wavs
                if "snare" in self._norm(p)
                and not any(x in self._norm(p) for x in ("brush", "roll"))
            ],
            key=lambda p: self._sample_sort_key(p),
        )

    def _cymbal_candidates(self) -> list[Path]:
        wavs = self._all_wavs()

        # Prefer suspended cymbal hits/strokes. Fall back to any cymbal sample.
        preferred = [
            p for p in wavs
            if "cymbal" in self._norm(p)
            and any(x in self._norm(p) for x in ("susp", "suspended", "crash", "hit"))
            and not any(x in self._norm(p) for x in ("roll", "scrape"))
        ]
        if preferred:
            return sorted(preferred, key=lambda p: self._sample_sort_key(p))

        generic = [
            p for p in wavs
            if "cymbal" in self._norm(p)
            and not any(x in self._norm(p) for x in ("roll", "scrape"))
        ]
        return sorted(generic, key=lambda p: self._sample_sort_key(p))

    @staticmethod
    def _sample_sort_key(path: Path):
        name = path.name.lower()
        vel = re.search(r"(?:^|[_-])v(\d+)(?:[_-]|\.|$)", name)
        rr = re.search(r"rr(\d+)", name)
        return (
            int(vel.group(1)) if vel else 999,
            int(rr.group(1)) if rr else 999,
            name,
        )

    @staticmethod
    def _velocity_number(path: Path) -> int | None:
        m = re.search(r"(?:^|[_-])v(\d+)(?:[_-]|\.|$)", path.name.lower())
        return int(m.group(1)) if m else None

    def _representative_velocity_samples(self, candidates: list[Path], max_layers=5):
        if not candidates:
            return []

        # One representative sample per detected velocity level. Prefer rr1.
        by_vel = {}
        unknown = []
        for p in candidates:
            v = self._velocity_number(p)
            if v is None:
                unknown.append(p)
            else:
                current = by_vel.get(v)
                if current is None or ("rr1" in p.name.lower() and "rr1" not in current.name.lower()):
                    by_vel[v] = p

        selected = [by_vel[v] for v in sorted(by_vel)]
        if not selected:
            selected = unknown

        if len(selected) <= max_layers:
            return selected

        # Evenly sample the available dynamic range.
        idx = [round(i * (len(selected)-1) / (max_layers-1)) for i in range(max_layers)]
        return [selected[i] for i in idx]

    @staticmethod
    def _escape_sample(path: Path) -> str:
        return str(path.resolve()).replace("\\", "/")

    def _write_one_shot_sfz(
        self,
        *,
        out_path: Path,
        samples: list[Path],
        midi_key: int = 60,
        release: float = 0.4,
        volume_db: float = 0.0,
    ) -> Path:
        if not samples:
            raise LookupError(f"No samples available for {out_path.name}")

        samples = self._representative_velocity_samples(samples)
        n = len(samples)

        lines = [
            "// LAISE generated SFZ wrapper",
            "// Derived mapping only; source WAV files remain unmodified.",
            "<control>",
            "",
        ]

        for i, sample in enumerate(samples):
            lovel = round(i * 128 / n)
            hivel = 127 if i == n-1 else round((i+1) * 128 / n) - 1
            lines += [
                "<region>",
                f"sample={self._escape_sample(sample)}",
                f"key={midi_key}",
                f"lovel={lovel}",
                f"hivel={hivel}",
                "loop_mode=one_shot",
                f"ampeg_release={release}",
                f"volume={volume_db}",
                "",
            ]

        out_path.write_text("\n".join(lines), encoding="utf-8")
        return out_path

    def ensure(self) -> dict:
        snare = self.generated_root / "LAISE_VSCO2CE_Snare.sfz"
        cymbal = self.generated_root / "LAISE_VSCO2CE_Cymbal.sfz"

        snare_candidates = self._snare_candidates()
        cymbal_candidates = self._cymbal_candidates()

        self._write_one_shot_sfz(
            out_path=snare,
            samples=snare_candidates,
            midi_key=60,
            release=0.32,
            volume_db=-1.0,
        )
        self._write_one_shot_sfz(
            out_path=cymbal,
            samples=cymbal_candidates,
            midi_key=60,
            release=2.8,
            volume_db=-3.0,
        )

        return {
            "snare_sfz": str(snare),
            "cymbal_sfz": str(cymbal),
            "snare_source_samples": [str(p) for p in self._representative_velocity_samples(snare_candidates)],
            "cymbal_source_samples": [str(p) for p in self._representative_velocity_samples(cymbal_candidates)],
        }
