from __future__ import annotations

SECTIONS=[
 ("Opening",0,8,.16),
 ("Connection",8,16,.32),
 ("Ascent",16,26,.56),
 ("Breakthrough",26,34,.86),
 ("Home",34,40,.24),
]

def keyframes(duration:float,role:str):
 bar=duration/40.0
 frames=[]
 for name,a,b,e in SECTIONS:
  t0=a*bar;t1=b*bar
  if role=="piano": width,elev=8+10*e,1
  elif role=="theme": width,elev=11+20*e,5+5*e
  elif role=="strings": width,elev=18+25*e,9+3*e
  elif role=="bass": width,elev=2,-5
  elif role=="ostinato": width,elev=10+17*e,3
  elif role=="percussion": width,elev=12+25*e,0
  else: width,elev=10+18*e,6
  sign=-1 if (a//4)%2==0 else 1
  # MUSIC-004: movement is deliberately restrained; width expands with emotion.
  frames.extend([
   {"time_seconds":t0,"azimuth_deg":sign*width*.55,"elevation_deg":elev,
    "distance_m":3.0,"section":name,"energy":e},
   {"time_seconds":(t0+t1)/2,"azimuth_deg":-sign*width*.35,"elevation_deg":elev,
    "distance_m":3.0,"section":name,"energy":e},
  ])
 frames.append({"time_seconds":duration,"azimuth_deg":0,"elevation_deg":0,
                "distance_m":3.0,"section":"Home","energy":.16})
 return frames
