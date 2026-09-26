from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import subprocess

from t0102_semantic_catalog import VSCOAssetCatalog, SfzAsset
from t0102_percussion_wrapper_builder import VSCOGeneratedPercussionBuilder
from t010_hybrid_renderer import read_wav_float


@dataclass(frozen=True)
class SemanticRoute:
    role: str
    family: str
    instrument: str
    articulation: str
    function: str
    renderer: str
    asset_id: str
    asset_path: str
    asset_status: str
    playable_center: int | None = None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class T0102SemanticRouter:
    """
    Full orchestral migration router for MUSIC-009.

    tuple = family + articulation + musical function
    """

    def __init__(self, root: Path, sr: int = 48000):
        self.root = Path(root)
        self.sr = sr
        self.sfizz = self.root / "tools" / "sfizz" / "bin" / "Release" / "sfizz_render.exe"
        self.generaluser = self.root / "assets" / "soundfonts" / "GeneralUser GS v1.471.sf2"
        self.salamander = (
            self.root / "assets" / "sfz" / "SalamanderGrandPiano-master"
            / "Salamander Grand Piano V3.sfz"
        )
        self.vsco_root = self.root / "assets" / "sfz" / "VSCO-2-CE-1.1.0"

        for p in (self.sfizz, self.generaluser, self.salamander):
            if not p.is_file():
                raise FileNotFoundError(str(p))

        self.generated_percussion_root = (
            self.root / "assets" / "generated_sfz" / "vsco2ce_percussion"
        )
        self.percussion_wrappers = VSCOGeneratedPercussionBuilder(
            self.vsco_root,
            self.generated_percussion_root,
        ).ensure()

        self.catalog = VSCOAssetCatalog(
            self.vsco_root,
            extra_roots=(self.generated_percussion_root,),
        )
        self.routes = self._build_routes()

    def _sfz_route(
        self, role, family, articulation, function,
        instrument_preferences, articulation_preferences,
        prefer_ensemble=False, require_instrument_match=False
    ):
        asset = self.catalog.select(
            family=family,
            instrument_preferences=instrument_preferences,
            articulation_preferences=articulation_preferences,
            function=function,
            prefer_ensemble=prefer_ensemble,
            require_instrument_match=require_instrument_match,
        )
        return SemanticRoute(
            role=role,
            family=family,
            instrument=asset.instrument,
            articulation=articulation,
            function=function,
            renderer="sfizz_render",
            asset_id=f"LAISE-VSCO2CE-{role.upper()}",
            asset_path=asset.path,
            asset_status="ONBOARDING_VALIDATED",
            playable_center=asset.playable_center,
        )

    def _build_routes(self):
        routes = {}

        routes["piano"] = SemanticRoute(
            "piano", "keys", "piano", "sustain", "harmonic_anchor",
            "sfizz_render", "LAISE-SFZ-PIANO-SALAMANDER-V3",
            str(self.salamander), "ONBOARDING_VALIDATED", 60
        )

        routes["theme"] = self._sfz_route(
            "theme", "woodwinds", "sustain", "theme",
            ("oboe", "flute", "clarinet", "bassoon"),
            ("sustain", "generic"), False
        )
        routes["strings"] = self._sfz_route(
            "strings", "strings", "sustain", "harmonic_bed",
            ("violin", "viola", "cello", "strings_generic"),
            ("sustain", "generic"), True
        )
        routes["bass"] = self._sfz_route(
            "bass", "strings", "sustain", "bass",
            ("double_bass", "cello", "strings_generic"),
            ("sustain", "generic"), True
        )
        routes["ostinato"] = self._sfz_route(
            "ostinato", "strings", "short", "ostinato",
            ("violin", "viola", "cello", "strings_generic"),
            ("short", "generic"), True
        )
        routes["brass"] = self._sfz_route(
            "brass", "brass", "sustain", "brass_sustain",
            ("french_horn", "trombone", "trumpet", "brass_generic"),
            ("sustain", "generic"), True
        )
        routes["countermelody"] = self._sfz_route(
            "countermelody", "strings", "sustain", "countermelody",
            ("violin", "viola", "strings_generic"),
            ("sustain", "generic"), False
        )
        routes["brass_attack"] = self._sfz_route(
            "brass_attack", "brass", "short", "brass_attack",
            ("french_horn", "trombone", "trumpet", "brass_generic"),
            ("short", "generic"), True
        )

        routes["percussion_low"] = self._sfz_route(
            "percussion_low", "percussion", "hit", "percussion_low",
            ("bass_drum", "timpani", "tom"),
            ("generic", "short"), False, True
        )
        routes["percussion_snare"] = self._sfz_route(
            "percussion_snare", "percussion", "hit", "percussion_snare",
            ("snare",),
            ("generic", "short"), False, True
        )
        routes["percussion_cymbal"] = self._sfz_route(
            "percussion_cymbal", "percussion", "hit", "percussion_cymbal",
            ("cymbal", "gong"),
            ("generic", "short"), False, True
        )

        # Trailer sound-design exceptions remain isolated fallbacks.
        for role in ("braam", "ping"):
            routes[role] = SemanticRoute(
                role, "sound_design", role, "effect", role,
                "fluidsynth", "LAISE-SF-TEST-0001",
                str(self.generaluser), "TEST_ONLY", None
            )

        return routes

    def route(self, role: str) -> SemanticRoute:
        if role not in self.routes:
            raise KeyError(f"No T010.2 semantic route for role={role}")
        return self.routes[role]

    def render_sfizz(self, route: SemanticRoute, midi_path: Path, wav_path: Path):
        cmd = [
            str(self.sfizz),
            "--sfz", route.asset_path,
            "--midi", str(midi_path),
            "--wav", str(wav_path),
            "--samplerate", str(self.sr),
            "--use-eot",
        ]
        cp = subprocess.run(
            cmd, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        if cp.returncode != 0:
            raise RuntimeError(
                f"sfizz render failed role={route.role}\n{cp.stdout[-4000:]}"
            )
        audio, info = read_wav_float(wav_path)
        return audio, info, cp.stdout[-1000:]

    def provenance(self, role: str) -> dict:
        r = self.route(role)
        p = Path(r.asset_path)
        return {
            **r.__dict__,
            "asset_sha256": sha256_file(p),
        }
