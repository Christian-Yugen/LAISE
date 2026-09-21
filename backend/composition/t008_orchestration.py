from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Iterable
import math

@dataclass
class T008Note:
    start:int
    duration:int
    pitch:int
    velocity:int
    channel:int=0

class CinematicOrchestrationEngine:
    """T008 v0.1: deterministic orchestration refinements over an existing score."""
    def __init__(self, ppq:int=480, total_bars:int=40):
        self.ppq=ppq; self.bar=ppq*4; self.total_bars=total_bars

    def apply_predrop(self, notes:Iterable, climax_bar:int=32, silence_beats:float=1.5,
                      roles_to_cut=("strings","bass","ostinato","percussion","brass")):
        cut_at=climax_bar*self.bar-round(silence_beats*self.ppq)
        resume=climax_bar*self.bar
        out={}
        for role,seq in notes.items():
            new=[]
            for n in seq:
                if role not in roles_to_cut:
                    new.append(n); continue
                end=n.start+n.duration
                if cut_at <= n.start < resume:
                    continue
                if n.start < cut_at < end:
                    n=type(n)(n.start,max(1,cut_at-n.start),n.pitch,n.velocity,n.channel)
                new.append(n)
            out[role]=new
        return out,{"climax_bar":climax_bar,"cut_at_tick":cut_at,"resume_tick":resume,
                    "silence_beats":silence_beats,"roles":list(roles_to_cut)}

    def countermelody(self, harmonic_bars:Dict, start_bar:int=27, end_bar:int=34)->List[T008Note]:
        # Slow, singable upper line; derived from chord tones, not a new independent theme.
        notes=[]
        contour=[2,3,2,1,3,2,1]
        for i,bar in enumerate(range(start_bar,end_bar)):
            st=harmonic_bars[bar]
            chord=list(st.pitches)
            idx=min(contour[i%len(contour)],len(chord)-1)
            p=chord[idx]+12
            if p<72:p+=12
            notes.append(T008Note(bar*self.bar+60,round(self.bar*.88),p,58+min(i,4)*2))
        return notes

    def brass_attack_layer(self, harmonic_bars:Dict, bars=(27,30,32,33))->List[T008Note]:
        notes=[]
        for bar in bars:
            st=harmonic_bars[bar]
            for p in (st.pitches[0],st.pitches[min(2,len(st.pitches)-1)],st.pitches[1]+12):
                notes.append(T008Note(bar*self.bar,round(.42*self.ppq),p,min(92,72+(bar>=32)*10)))
        return notes

    def cinematic_punctuation(self, harmonic_bars:Dict, enable_braam=True, enable_ping=True):
        out={"braam":[],"ping":[]}
        if enable_braam:
            root=harmonic_bars[32].pitches[0]-24
            out["braam"]=[T008Note(32*self.bar,round(1.4*self.ppq),max(24,root),86)]
        if enable_ping:
            p=harmonic_bars[30].pitches[-1]+24
            out["ping"]=[T008Note(30*self.bar,round(.32*self.ppq),min(96,p),66)]
        return out
