from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Dict
import math, random

PPQ = 480

@dataclass
class PhraseNote:
    beat: float
    duration: float
    degree: int
    velocity: int
    articulation: str = "legato"

@dataclass
class Phrase:
    phrase_id: str
    function: str
    bars: int
    tension_start: float
    tension_end: float
    notes: List[PhraseNote]

    def to_dict(self):
        d = asdict(self)
        return d

class PhraseEngine:
    """
    LAISE T006 — Phrase Engine v0.1

    Generates musical thought in phrase units rather than isolated notes.
    A phrase has a rhetorical function:
      statement -> response -> development -> resolution
    """

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def _vel(self, base: int, tension: float, idx: int, total: int) -> int:
        arch = math.sin(math.pi * (idx + 1) / (total + 1))
        jitter = self.rng.randint(-2, 2)
        return max(1, min(127, int(base + tension * 18 + arch * 7 + jitter)))

    def statement(self, motif: List[int], phrase_id="P1") -> Phrase:
        rhythm = [0.0, 1.0, 1.75, 2.5, 4.0, 5.0, 6.0, 7.0]
        durations = [0.9, .65, .65, 1.25, .9, .7, .9, .75]
        notes=[]
        for i,d in enumerate(motif[:8]):
            t=.22 + .30*(i/7)
            notes.append(PhraseNote(rhythm[i],durations[i],d,self._vel(48,t,i,8)))
        return Phrase(phrase_id,"statement",2,.22,.52,notes)

    def response(self, source: Phrase, phrase_id="P2") -> Phrase:
        degrees=[n.degree for n in source.notes]
        # Answer descends and closes more strongly than the statement.
        transformed=[degrees[0],degrees[2],degrees[1],degrees[0],
                     degrees[3],degrees[1],degrees[0],degrees[0]-2]
        rhythm=[0.0,.75,1.5,2.5,4.0,4.75,5.5,6.5]
        durations=[.7,.7,.85,1.2,.7,.7,.9,1.35]
        notes=[]
        for i,d in enumerate(transformed):
            t=.48 - .22*(i/7)
            notes.append(PhraseNote(rhythm[i],durations[i],d,self._vel(50,t,i,8)))
        return Phrase(phrase_id,"response",2,.48,.26,notes)

    def develop(self, source: Phrase, phrase_id="P3") -> Phrase:
        src=[n.degree for n in source.notes]
        # Sequence + extension: recognisable motif, greater register/tension.
        degrees=[src[0]+2,src[1]+2,src[2]+2,src[3]+2,
                 src[0]+4,src[1]+4,src[2]+4,src[3]+5,
                 src[4]+4,src[5]+4,src[6]+5,src[7]+4]
        rhythm=[0,.5,1,1.5,2.5,3,3.5,4,5,.5+5,6,7]
        durations=[.46,.46,.46,.8,.46,.46,.46,.8,.46,.46,.8,.9]
        notes=[]
        for i,d in enumerate(degrees):
            t=.48 + .36*(i/(len(degrees)-1))
            notes.append(PhraseNote(rhythm[i],durations[i],d,self._vel(55,t,i,len(degrees)),
                                    "accent" if i in (0,4,8) else "legato"))
        return Phrase(phrase_id,"development",2,.48,.84,notes)

    def resolve(self, source: Phrase, tonic_degree: int=0, phrase_id="P4") -> Phrase:
        src=[n.degree for n in source.notes]
        degrees=[src[0],src[2],src[1],src[0],2,1,0,tonic_degree]
        rhythm=[0,1,1.75,2.5,4,5,6,7]
        durations=[.9,.65,.65,1.15,.85,.85,.85,1.7]
        notes=[]
        for i,d in enumerate(degrees):
            t=.62 - .48*(i/7)
            notes.append(PhraseNote(rhythm[i],durations[i],d,self._vel(47,t,i,8),
                                    "tenuto" if i==7 else "legato"))
        return Phrase(phrase_id,"resolution",2,.62,.14,notes)

    def make_arc(self, motif: List[int]) -> List[Phrase]:
        p1=self.statement(motif)
        p2=self.response(p1)
        p3=self.develop(p1)
        p4=self.resolve(p1)
        return [p1,p2,p3,p4]
