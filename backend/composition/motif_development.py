from __future__ import annotations
from typing import List

class MotifDeveloper:
    """Deterministic motif transformations used by LAISE T006."""
    @staticmethod
    def transpose(motif: List[int], steps: int) -> List[int]:
        return [x + steps for x in motif]

    @staticmethod
    def invert(motif: List[int], axis: int | None = None) -> List[int]:
        if not motif: return []
        a = motif[0] if axis is None else axis
        return [a - (x-a) for x in motif]

    @staticmethod
    def sequence(motif: List[int], offsets=(0,2,4)) -> List[int]:
        out=[]
        for off in offsets: out.extend(x+off for x in motif)
        return out

    @staticmethod
    def fragment(motif: List[int], length=4) -> List[int]:
        return motif[:max(1,min(length,len(motif)))]

    @staticmethod
    def answer(motif: List[int]) -> List[int]:
        if len(motif)<4:return motif[:]
        head=motif[:4]
        return [head[0],head[2],head[1],head[0]-1]
