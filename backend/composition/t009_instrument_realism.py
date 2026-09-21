from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Tuple
import random

@dataclass(frozen=True)
class ArticulationProfile:
    family: str
    timing_jitter_ms: float
    timing_bias_ms: float
    velocity_jitter: int
    duration_factor: float
    overlap_ms: float
    accent_gain: int
    phrase_end_release: float

ROLE_PROFILES = {
    "piano": ArticulationProfile("keyboard", 5.5, 0.0, 3, 0.92, 0.0, 2, 0.78),
    "theme": ArticulationProfile("solo_wind", 3.0, -2.0, 2, 0.96, 34.0, 2, 0.84),
    "strings": ArticulationProfile("strings", 2.6, -1.5, 2, 0.98, 58.0, 2, 0.88),
    "bass": ArticulationProfile("low_strings", 4.0, 5.0, 2, 0.94, 18.0, 2, 0.80),
    "ostinato": ArticulationProfile("strings_short", 3.2, 1.5, 3, 0.72, 0.0, 3, 0.72),
    "percussion": ArticulationProfile("percussion", 1.8, 0.0, 3, 0.72, 0.0, 5, 0.70),
    "brass": ArticulationProfile("brass_sustain", 2.2, -3.0, 2, 0.90, 22.0, 4, 0.76),
    "countermelody": ArticulationProfile("solo_strings", 2.2, -2.5, 2, 0.98, 72.0, 2, 0.90),
    "brass_attack": ArticulationProfile("brass_short", 1.5, -4.0, 2, 0.48, 0.0, 8, 0.62),
    "braam": ArticulationProfile("cinematic_hit", 0.5, 0.0, 1, 0.95, 0.0, 6, 0.80),
    "ping": ArticulationProfile("cinematic_ping", 1.0, -1.0, 1, 0.82, 0.0, 3, 0.78),
}

class InstrumentRealismEngine:
    """
    LAISE T009 — Instrument Realism & Articulation Intelligence v0.1

    Operates on already-composed note events. It does not change theme or
    harmony. It shapes how each instrumental family performs those notes.
    """
    def __init__(self, ppq:int=480, bpm:int=96, seed:int=20260928):
        self.ppq=ppq
        self.bpm=bpm
        self.seed=seed
        self.ms_per_tick=(60000.0/bpm)/ppq

    def profile(self, role:str)->ArticulationProfile:
        return ROLE_PROFILES.get(role, ArticulationProfile(
            "generic", 2.5, 0.0, 2, 0.90, 0.0, 2, 0.80
        ))

    def _ticks(self, ms:float)->int:
        return round(ms/self.ms_per_tick)

    def _phase_for_tick(self, tick:int, narrative_plan:List[dict], bar_ticks:int)->Tuple[str,float]:
        bar=max(0, tick//bar_ticks)
        selected=narrative_plan[0] if narrative_plan else {"phase":"stability","energy":.2}
        for p in narrative_plan:
            if p["bar"] <= bar:
                selected=p
            else:
                break
        return selected["phase"], float(selected["energy"])

    def _next_phrase_boundary_tick(self, tick:int, narrative_plan:List[dict], bar_ticks:int):
        bar=tick/bar_ticks
        for p in narrative_plan:
            if p["bar"] > bar:
                return int(p["bar"]*bar_ticks)
        return None

    def shape_role(self, role:str, notes:Iterable, narrative_plan:List[dict],
                   bar_ticks:int):
        p=self.profile(role)
        rng=random.Random(f"{self.seed}:{role}")
        out=[]
        changed_timing=changed_velocity=changed_duration=phrase_breaths=0
        max_overlap_ticks=self._ticks(p.overlap_ms)

        seq=sorted(notes,key=lambda n:(n.start,n.pitch))
        for n in seq:
            phase,energy=self._phase_for_tick(n.start,narrative_plan,bar_ticks)

            jitter_ms=rng.uniform(-p.timing_jitter_ms,p.timing_jitter_ms)
            timing_ms=p.timing_bias_ms+jitter_ms
            if role in ("strings","brass","brass_attack","percussion"):
                timing_ms *= max(.45,1.0-.42*energy)
            start=max(0,n.start+self._ticks(timing_ms))
            if start != n.start:
                changed_timing+=1

            arch=0
            if phase in ("tension","suspension","breakthrough"):
                arch=round(4*energy)
            elif phase=="resolution":
                arch=-2

            accent=0
            beat=(n.start % bar_ticks)/self.ppq
            if beat < .15 and phase in ("tension","suspension","breakthrough"):
                accent=p.accent_gain

            velocity=max(1,min(127,n.velocity+rng.randint(-p.velocity_jitter,p.velocity_jitter)+arch+accent))
            if velocity != n.velocity:
                changed_velocity+=1

            factor=p.duration_factor
            overlap=max_overlap_ticks
            if role in ("strings","theme","countermelody") and phase in ("stability","preparation","expectation","resolution"):
                factor=min(1.08,factor+0.06)
                overlap=round(max_overlap_ticks*(1.0+.30*(1.0-energy)))
            if role=="brass" and phase in ("tension","suspension","breakthrough"):
                factor=.82
            if role=="brass_attack":
                factor=.42 if phase in ("tension","suspension","breakthrough") else .50
            if role=="ostinato" and energy>.78:
                factor=.64

            duration=max(1,round(n.duration*factor)+overlap)

            boundary=self._next_phrase_boundary_tick(n.start,narrative_plan,bar_ticks)
            if boundary and start < boundary <= start+duration+self._ticks(100):
                target=max(1,boundary-start-self._ticks(28))
                if target < duration:
                    duration=max(1,round(target*p.phrase_end_release))
                    phrase_breaths+=1

            if duration != n.duration:
                changed_duration+=1

            out.append(type(n)(start,duration,n.pitch,velocity,n.channel))

        diag={
            "role":role,
            "family":p.family,
            "profile":asdict(p),
            "notes":len(seq),
            "timing_changes":changed_timing,
            "velocity_changes":changed_velocity,
            "duration_changes":changed_duration,
            "phrase_breaths":phrase_breaths,
        }
        return out,diag

    def apply(self, note_map:Dict[str,list], narrative_plan:List[dict], bar_ticks:int):
        shaped={}
        diagnostics={}
        for role,notes in note_map.items():
            shaped[role],diagnostics[role]=self.shape_role(role,notes,narrative_plan,bar_ticks)
        return shaped,diagnostics
