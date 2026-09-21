from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List

@dataclass
class EmotionalPoint:
    bar:int
    phase:str
    target_tension:float
    brightness:float
    energy:float

class EmotionalNarrative:
    """
    Converts a high-level dramatic arc into explicit musical control targets.
    """
    def hopeful_cinematic(self, bars:int=40)->List[dict]:
        anchors=[
          (0,"stability",.18,.55,.16),
          (4,"preparation",.28,.58,.24),
          (8,"expectation",.38,.64,.34),
          (12,"preparation",.45,.66,.43),
          (16,"tension",.56,.64,.55),
          (20,"expectation",.63,.68,.64),
          (24,"suspension",.74,.62,.74),
          (27,"tension",.82,.68,.84),
          (30,"suspension",.90,.70,.94),
          (32,"breakthrough",.68,.82,1.00),
          (34,"resolution",.42,.84,.70),
          (36,"resolution",.27,.82,.46),
          (38,"resolution",.15,.78,.25),
          (39,"resolution",.10,.76,.15),
        ]
        return [asdict(EmotionalPoint(*x)) for x in anchors if x[0]<bars]
