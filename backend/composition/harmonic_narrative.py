from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple
import random

@dataclass(frozen=True)
class HarmonicState:
    name: str
    chord: str
    pitches: Tuple[int, ...]
    function: str
    tension: float
    brightness: float

@dataclass
class HarmonicEvent:
    bar: int
    state: str
    chord: str
    function: str
    tension: float
    target_tension: float
    reason: str

class HarmonicNarrativeEngine:
    """
    LAISE T007 — Harmonic & Emotional Narrative Engine v0.1

    Chooses harmony from emotional/tension targets instead of cycling a fixed
    progression. It is deterministic for a seed and preserves tonal coherence.
    """

    def __init__(self, seed:int=20260926):
        self.rng=random.Random(seed)
        # G major / E minor family, with functional alternatives.
        self.states=[
            HarmonicState("I","Gadd9",(55,59,62,69),"tonic",.12,.82),
            HarmonicState("I6","G/B",(47,55,59,62),"tonic",.18,.78),
            HarmonicState("vi","Em7",(52,55,59,62),"tonic_relative",.25,.42),
            HarmonicState("IV","Cmaj7",(48,52,55,59),"predominant",.34,.72),
            HarmonicState("ii","Am7",(57,60,64,67),"predominant",.46,.46),
            HarmonicState("Vsus","Dsus4",(50,55,57,62),"dominant_suspension",.66,.58),
            HarmonicState("V","D",(50,54,57,62),"dominant",.78,.64),
            HarmonicState("V7","D7",(50,54,57,60),"dominant",.88,.50),
            HarmonicState("iii","Bm7",(47,50,54,57),"mediant",.39,.45),
            HarmonicState("IV6","C/E",(52,55,60,64),"predominant",.30,.70),
        ]
        self.by_name={s.name:s for s in self.states}

    def _allowed(self, previous:HarmonicState|None, phase:str)->List[HarmonicState]:
        if previous is None:
            return [self.by_name[x] for x in ("vi","I","IV")]
        table={
          "tonic":("I6","vi","IV","iii"),
          "tonic_relative":("IV","ii","I6","V","iii"),
          "predominant":("ii","Vsus","V","I6","vi"),
          "dominant_suspension":("V","V7","I"),
          "dominant":("I","vi","IV6"),
          "mediant":("vi","IV","ii"),
        }
        names=table.get(previous.function,("I","IV","V","vi"))
        if phase=="resolution":
            names=tuple(dict.fromkeys(("I","I6","IV6")+names))
        return [self.by_name[n] for n in names]

    def choose(self, previous:HarmonicState|None, target:float,
               phase:str, brightness_target:float=.60)->HarmonicState:
        candidates=self._allowed(previous,phase)
        scored=[]
        for s in candidates:
            tension_error=abs(s.tension-target)
            brightness_error=abs(s.brightness-brightness_target)*.24
            repeat_penalty=.30 if previous and s.name==previous.name else 0
            resolution_bonus=-.22 if phase=="resolution" and s.function=="tonic" else 0
            suspense_bonus=-.10 if phase=="suspension" and "dominant" in s.function else 0
            score=tension_error+brightness_error+repeat_penalty+resolution_bonus+suspense_bonus
            score += self.rng.random()*.025
            scored.append((score,s))
        return min(scored,key=lambda x:x[0])[1]

    def compose(self, emotional_curve:List[Dict])->List[HarmonicEvent]:
        events=[];prev=None
        for point in emotional_curve:
            state=self.choose(prev,float(point["target_tension"]),
                              point["phase"],float(point.get("brightness",.60)))
            reason=(f"{point['phase']}: target tension "
                    f"{point['target_tension']:.2f}, selected {state.function}")
            events.append(HarmonicEvent(point["bar"],state.name,state.chord,
                                        state.function,state.tension,
                                        point["target_tension"],reason))
            prev=state
        return events
