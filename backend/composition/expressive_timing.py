from __future__ import annotations
import math, random

class ExpressiveTiming:
    """Phrase-aware deterministic timing/dynamics, not random note scatter."""
    def __init__(self, seed:int, ppq:int=480):
        self.rng=random.Random(seed); self.ppq=ppq

    def timing_offset_ticks(self, position:float, phrase_length:float,
                            articulation:str="legato") -> int:
        x=max(0.0,min(1.0,position/max(phrase_length,1e-9)))
        # breathe slightly at phrase boundaries, lean into the middle
        curve=math.sin(2*math.pi*x)
        base=int(curve*0.018*self.ppq)
        if articulation=="accent": base-=int(.010*self.ppq)
        if articulation=="tenuto": base+=int(.008*self.ppq)
        return base+self.rng.randint(-3,3)

    def duration_factor(self, articulation:str) -> float:
        return {"legato":1.08,"accent":.82,"tenuto":1.16,"staccato":.52}.get(articulation,1.0)

    def dynamic_arch(self, index:int,total:int,start:int,end:int) -> int:
        if total<=1:return end
        x=index/(total-1)
        linear=start+(end-start)*x
        arch=7*math.sin(math.pi*x)
        return max(1,min(127,round(linear+arch)))
