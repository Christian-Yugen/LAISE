import math
HUMAN_PRIOR=[
(3,0,1,3,2,1),(0.75,0,1,1,2,0),(3,None,0,1,4,0),(1,None,0,1,3,0),
(1.5,0,1,2,4,1),(2,0,1,2,4,0),(1,0,1,1,4,0),(4,0,1,1,4,0),
(3,0,1,3,4,1),(3,-12,1,3,3,1)]
def target(ext,cent,front): return .55*(ext/5)+.30*(cent/5)+.15*front
def prior_score(c):
    num=den=0.0
    cg=-24 if c["reflection_gain_db"] is None else c["reflection_gain_db"]
    for d,g,refl,e,cent,front in HUMAN_PRIOR:
        gg=-24 if g is None else g
        dd=((c["distance_m"]-d)/5.25)**2+((cg-gg)/24)**2+(int(c["reflection"])-refl)**2
        w=math.exp(-dd/(2*.16**2)); num+=w*target(e,cent,front); den+=w
    return num/den if den>1e-9 else 0.0
