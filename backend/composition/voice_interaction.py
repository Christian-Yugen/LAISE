from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class RoleInstruction:
    role: str
    relation: str
    density: float
    register: str
    anticipation_beats: float
    release_beats: float
    dynamic_scale: float

class VoiceInteractionEngine:
    """
    Makes orchestral roles respond to phrase function rather than run as
    independent generators.
    """
    MAP = {
      "statement": [
        RoleInstruction("piano","present",.45,"mid",0,.15,.72),
        RoleInstruction("strings","sustain",.18,"mid_high",0,.45,.38),
        RoleInstruction("bass","root_support",.16,"low",0,.20,.34),
      ],
      "response": [
        RoleInstruction("piano","answer",.38,"mid",0,.20,.68),
        RoleInstruction("strings","counter_sustain",.28,"mid_high",-.10,.55,.48),
        RoleInstruction("bass","voice_lead",.22,"low",0,.25,.42),
      ],
      "development": [
        RoleInstruction("piano","motif_fragment",.62,"mid_high",-.05,.12,.82),
        RoleInstruction("strings","expand",.56,"mid_high",-.12,.65,.76),
        RoleInstruction("bass","propel",.48,"low",0,.18,.67),
        RoleInstruction("ostinato","derive_rhythm",.68,"mid",0,.08,.60),
        RoleInstruction("percussion","punctuate",.46,"wide",0,.05,.68),
        RoleInstruction("brass","punctuate_peak",.24,"mid",0,.38,.58),
      ],
      "resolution": [
        RoleInstruction("piano","resolve",.34,"mid",0,.30,.58),
        RoleInstruction("strings","release",.32,"mid_high",-.12,.85,.50),
        RoleInstruction("bass","cadence",.20,"low",0,.40,.38),
      ],
    }
    def instructions(self, phrase_function: str) -> List[RoleInstruction]:
        return list(self.MAP[phrase_function])
