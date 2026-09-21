from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Dict

@dataclass
class NarrativeDecision:
    bar:int
    phase:str
    tension:float
    energy:float
    phrase_function:str
    density:float
    articulation_bias:str
    spatial_width:float

class NarrativePlanner:
    """
    Bridges emotional/harmonic narrative to T006 phrase/orchestration controls.
    """
    def build(self, curve:List[dict])->List[dict]:
        out=[]
        for p in curve:
            phase=p["phase"];t=p["target_tension"];e=p["energy"]
            if phase in ("stability","preparation"):
                pf="statement" if t<.35 else "response"
            elif phase in ("expectation","tension","suspension"):
                pf="development"
            elif phase=="breakthrough":
                pf="development"
            else:
                pf="resolution"
            if t<.30:art="legato"
            elif t<.68:art="flowing"
            elif t<.85:art="accented"
            else:art="urgent"
            density=min(1.0,.20+.72*e)
            width=min(1.0,.18+.72*e)
            out.append(asdict(NarrativeDecision(
                p["bar"],phase,t,e,pf,density,art,width)))
        return out
