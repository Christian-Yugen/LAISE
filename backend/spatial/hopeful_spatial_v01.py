from __future__ import annotations
SECTIONS=[("Intimate",0,6,.14),("Bloom",6,14,.32),("Lift",14,22,.52),("Crescendo",22,29,.76),("Peak",29,33,.94)]
def keyframes(duration,role):
 bar=duration/33.;f=[]
 for name,a,b,e in SECTIONS:
  t0=a*bar;t1=b*bar
  if role=="piano":w,el=10+10*e,1
  elif role=="theme":w,el=16+24*e,5+5*e
  elif role=="strings":w,el=20+28*e,11
  elif role=="cello_bass":w,el=3,-5
  elif role=="ostinato":w,el=12+22*e,4
  elif role=="percussion":w,el=15+28*e,1
  else:w,el=12+20*e,6
  # gentler motion than MUSIC-002: spatial movement supports phrasing.
  a0=-w if (a//4)%2==0 else w
  f += [{"time_seconds":t0,"azimuth_deg":a0,"elevation_deg":el,"distance_m":3.0,"section":name,"energy":e},
        {"time_seconds":(t0+t1)/2,"azimuth_deg":-a0*.65,"elevation_deg":el,"distance_m":3.0,"section":name,"energy":e}]
 f.append({"time_seconds":duration,"azimuth_deg":0,"elevation_deg":0,"distance_m":3.0,"section":"Peak","energy":.35})
 return f
