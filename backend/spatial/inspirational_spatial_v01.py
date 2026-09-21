from __future__ import annotations
SECTIONS=[("Reflection",0,7,.18),("Determination",7,15,.42),("Triumph",15,27,.88),("Release",27,33,.38),("Finale",33,36,.16)]
def keyframes(duration,role):
 bar=duration/36.;f=[]
 for name,a,b,e in SECTIONS:
  t0=a*bar;t1=b*bar
  if role=="piano":w,el=12+15*e,2
  elif role=="soft_synth":w,el=22+25*e,14
  elif role=="strings":w,el=18+32*e,10+7*e
  elif role=="bass":w,el=2,-4
  elif role=="percussion":w,el=16+35*e,1+5*e
  elif role=="lead":w,el=20+38*e,6+8*e
  elif role=="ostinato":w,el=12+30*e,5
  else:w,el=12+28*e,7
  a0=-w if (a//4)%2==0 else w
  f += [{"time_seconds":t0,"azimuth_deg":a0,"elevation_deg":el,"distance_m":3.0,"section":name,"energy":e},{"time_seconds":(t0+t1)/2,"azimuth_deg":-a0,"elevation_deg":el,"distance_m":3.0,"section":name,"energy":e}]
 f.append({"time_seconds":duration,"azimuth_deg":0,"elevation_deg":0,"distance_m":3.0,"section":"Finale","energy":.1})
 return f
