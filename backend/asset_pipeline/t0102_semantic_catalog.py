from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import re
from typing import Iterable


NOTE_PC = {
    "c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3, "e": 4,
    "f": 5, "f#": 6, "gb": 6, "g": 7, "g#": 8, "ab": 8,
    "a": 9, "a#": 10, "bb": 10, "b": 11,
}


def note_token_to_midi(token: str) -> int | None:
    token = token.strip().lower()
    if re.fullmatch(r"-?\d+", token):
        v = int(token)
        return v if 0 <= v <= 127 else None

    m = re.fullmatch(r"([a-g](?:#|b)?)(-?\d+)", token)
    if not m:
        return None

    # SFZ commonly follows MIDI convention where C4 = 60.
    name, octave = m.group(1), int(m.group(2))
    value = 12 * (octave + 1) + NOTE_PC[name]
    return value if 0 <= value <= 127 else None


@dataclass(frozen=True)
class SfzAsset:
    path: str
    family: str
    instrument: str
    articulation: str
    ensemble: bool
    playable_low: int
    playable_high: int
    playable_center: int

    def as_dict(self) -> dict:
        return asdict(self)


class VSCOAssetCatalog:
    """
    T010.2 semantic SFZ catalog.

    Selection is constrained first by FAMILY, then by INSTRUMENT,
    ARTICULATION and MUSICAL FUNCTION. This prevents cross-family mistakes
    such as the earlier OboeStac -> string ostinato mapping.
    """

    def __init__(self, root: Path, extra_roots: Iterable[Path] = ()):
        self.root = Path(root)
        if not self.root.is_dir():
            raise FileNotFoundError(f"VSCO root not found: {self.root}")

        roots = [self.root]
        for r in extra_roots:
            rp = Path(r)
            if rp.is_dir():
                roots.append(rp)

        sfz_files = []
        for r in roots:
            sfz_files.extend(r.rglob("*.sfz"))

        self.assets = [self._classify(p) for p in sfz_files]

    @staticmethod
    def _tokens(path: Path) -> str:
        return f"{path.parent} {path.stem}".lower().replace("_", " ")

    def _family(self, path: Path) -> str:
        t = self._tokens(path)
        if "strings" in t:
            return "strings"
        if "brass" in t:
            return "brass"
        if "woodwinds" in t or "woodwind" in t:
            return "woodwinds"
        if "percussion" in t:
            return "percussion"
        if "laise_vsco2ce_snare" in t or "laise_vsco2ce_cymbal" in t:
            return "percussion"
        if "keys" in t:
            return "keys"

        # Conservative filename fallback.
        if any(x in t for x in ("violin", "viola", "cello", "contrabass", "double bass")):
            return "strings"
        if any(x in t for x in ("horn", "trumpet", "trombone", "tuba")):
            return "brass"
        if any(x in t for x in ("flute", "oboe", "clarinet", "bassoon")):
            return "woodwinds"
        if any(x in t for x in ("cymbal", "timp", "drum", "snare", "gong", "triangle")):
            return "percussion"
        return "other"

    def _instrument(self, path: Path, family: str) -> str:
        t = self._tokens(path)

        ordered = [
            ("double_bass", ("double bass", "contrabass", "bassens", "bass ens")),
            ("violin", ("violin",)),
            ("viola", ("viola",)),
            ("cello", ("cello", "violoncello")),
            ("french_horn", ("french horn", "frenchhorn", "horn")),
            ("trombone", ("trombone",)),
            ("trumpet", ("trumpet",)),
            ("tuba", ("tuba",)),
            ("flute", ("flute",)),
            ("oboe", ("oboe",)),
            ("clarinet", ("clarinet",)),
            ("bassoon", ("bassoon",)),
            ("bass_drum", ("bass drum", "bassdrum", "gran cassa", "kick")),
            ("timpani", ("timpani", "timp")),
            ("snare", ("snare",)),
            ("cymbal", ("cymbal", "crash", "splash")),
            ("tom", ("tom",)),
            ("gong", ("gong", "tam tam", "tamtam")),
            ("triangle", ("triangle",)),
            ("xylophone", ("xylophone",)),
        ]
        for label, words in ordered:
            if any(w in t for w in words):
                return label

        return {
            "strings": "strings_generic",
            "brass": "brass_generic",
            "woodwinds": "woodwind_generic",
            "percussion": "percussion_generic",
            "keys": "keys_generic",
        }.get(family, "unknown")

    def _articulation(self, path: Path) -> str:
        t = self._tokens(path)
        if any(x in t for x in ("stac", "stacc", "spic", "short")):
            return "short"
        if "pizz" in t:
            return "pizzicato"
        if "trem" in t:
            return "tremolo"
        if any(x in t for x in ("sus", "sustain", "vib", "legato")):
            return "sustain"
        return "generic"

    def _key_range(self, path: Path) -> tuple[int, int, int]:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            return (36, 84, 60)

        values = []
        for opcode in ("key", "lokey", "hikey", "pitch_keycenter"):
            for match in re.finditer(rf"\b{opcode}\s*=\s*([a-g](?:#|b)?-?\d+|-?\d+)", text):
                v = note_token_to_midi(match.group(1))
                if v is not None:
                    values.append(v)

        if not values:
            return (36, 84, 60)

        lo = min(values)
        hi = max(values)
        center = sorted(values)[len(values) // 2]
        if lo == hi:
            center = lo
        else:
            center = max(lo, min(hi, center))
        return (lo, hi, center)

    def _classify(self, path: Path) -> SfzAsset:
        family = self._family(path)
        instrument = self._instrument(path, family)
        articulation = self._articulation(path)
        t = self._tokens(path)
        ensemble = any(x in t for x in ("ens", "ensemble", "section"))
        lo, hi, center = self._key_range(path)
        return SfzAsset(
            path=str(path),
            family=family,
            instrument=instrument,
            articulation=articulation,
            ensemble=ensemble,
            playable_low=lo,
            playable_high=hi,
            playable_center=center,
        )

    def select(
        self,
        *,
        family: str,
        instrument_preferences: Iterable[str],
        articulation_preferences: Iterable[str],
        function: str,
        prefer_ensemble: bool = False,
        require_instrument_match: bool = False,
    ) -> SfzAsset:
        instruments = tuple(instrument_preferences)
        articulations = tuple(articulation_preferences)

        # HARD FAMILY GATE.
        candidates = [a for a in self.assets if a.family == family]
        if not candidates:
            raise LookupError(f"No VSCO assets found for family={family}")

        # Optional HARD INSTRUMENT GATE.
        # Used where a generic same-family fallback would be musically wrong,
        # especially percussion (snare/cymbal must never become timpani).
        if require_instrument_match:
            exact = [a for a in candidates if a.instrument in instruments]
            if not exact:
                available = sorted({a.instrument for a in candidates})
                raise LookupError(
                    f"No exact instrument candidate for family={family}, "
                    f"function={function}, requested={instruments}. "
                    f"Available instruments={available}"
                )
            candidates = exact

        def score(a: SfzAsset):
            points = 0

            if a.instrument in instruments:
                points += 80 - 7 * instruments.index(a.instrument)
            elif a.instrument.endswith("_generic"):
                points += 8

            if a.articulation in articulations:
                points += 60 - 8 * articulations.index(a.articulation)
            elif a.articulation == "generic":
                points += 5

            if prefer_ensemble and a.ensemble:
                points += 18
            if not prefer_ensemble and not a.ensemble:
                points += 6

            # Function-specific preferences.
            if function in ("theme", "countermelody"):
                if a.articulation == "sustain":
                    points += 22
            elif function in ("ostinato", "brass_attack"):
                if a.articulation == "short":
                    points += 30
            elif function == "bass":
                if a.instrument in ("double_bass", "cello"):
                    points += 25
            elif function == "brass_sustain":
                if a.instrument in ("french_horn", "trombone"):
                    points += 24
            elif function.startswith("percussion_"):
                if a.family == "percussion":
                    points += 18

            return (-points, len(a.path), a.path.lower())

        selected = sorted(candidates, key=score)[0]

        # Semantic sanity gates.
        if selected.family != family:
            raise AssertionError(
                f"Semantic family mismatch: requested={family}, got={selected.family}"
            )

        if function in ("ostinato", "brass_attack") and selected.articulation not in ("short", "generic"):
            raise LookupError(
                f"No valid short articulation for function={function}; selected={selected.path}"
            )

        return selected
