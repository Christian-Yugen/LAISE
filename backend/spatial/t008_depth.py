from __future__ import annotations
import numpy as np

DEPTH_PROFILES={
 "front":{"distance_m":2.0,"wet":0.07,"delay_ms":18,"feedback":0.10},
 "mid":{"distance_m":3.0,"wet":0.15,"delay_ms":31,"feedback":0.16},
 "back":{"distance_m":4.5,"wet":0.25,"delay_ms":47,"feedback":0.23},
}

ROLE_DEPTH={"piano":"front","theme":"front","countermelody":"mid","strings":"mid",
            "ostinato":"mid","bass":"mid","percussion":"back","brass":"back",
            "brass_attack":"back","braam":"back","ping":"back"}

def depth_profile(role):
 return DEPTH_PROFILES[ROLE_DEPTH.get(role,"mid")]

def apply_depth_tail(x,sr,role):
 """Small deterministic ambience layer; complements dearVR rather than replacing it."""
 p=depth_profile(role);d=max(1,round(sr*p["delay_ms"]/1000));y=x.astype(np.float32).copy()
 wet=p["wet"];fb=p["feedback"]
 for k,g in ((1,wet),(2,wet*fb),(3,wet*fb*fb)):
  off=d*k
  if off<y.shape[1]:y[:,off:]+=x[:,:-off]*g
 return y
