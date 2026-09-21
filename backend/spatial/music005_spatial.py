from __future__ import annotations

def narrative_keyframes(duration,role,plan,total_bars=40):
 bar_seconds=duration/total_bars
 frames=[]
 for p in plan:
  t=p["bar"]*bar_seconds;e=p["energy"];w=p["spatial_width"]
  base={"piano":10,"theme":14,"strings":24,"bass":2,"ostinato":13,"percussion":18,"brass":14}[role]
  width=base*(.55+.85*w)
  elev={"piano":1,"theme":7,"strings":11,"bass":-5,"ostinato":3,"percussion":0,"brass":6}[role]
  sign=-1 if (p["bar"]//4)%2==0 else 1
  frames.append({"time_seconds":t,"azimuth_deg":sign*width*.48,
                 "elevation_deg":elev,"distance_m":3.0,
                 "section":p["phase"],"energy":e})
  frames.append({"time_seconds":min(duration,t+2*bar_seconds),
                 "azimuth_deg":-sign*width*.28,"elevation_deg":elev,
                 "distance_m":3.0,"section":p["phase"],"energy":e})
 frames.append({"time_seconds":duration,"azimuth_deg":0,"elevation_deg":0,
                "distance_m":3.0,"section":"resolution","energy":.12})
 return frames
