from __future__ import annotations

SECTION_BARS=[
 ("Stillness",0,8,.22),
 ("Awakening",8,16,.38),
 ("Build",16,28,.58),
 ("Acceleration",28,36,.78),
 ("EpicClimax",36,44,1.0),
 ("Aftermath",44,48,.25),
]

def keyframes(duration,role):
    bar=duration/48
    frames=[]
    for name,a,b,e in SECTION_BARS:
        t0=a*bar;t1=b*bar
        if role=="bass": width=3; elev=-4
        elif role=="strings": width=14+28*e; elev=8+10*e
        elif role=="brass": width=10+24*e; elev=4+7*e
        elif role=="epic_percussion": width=18+42*e; elev=2+7*e
        elif role=="pulse_ostinato": width=12+35*e; elev=5
        else: width=20+48*e; elev=5+9*e
        # calm -> broadening -> kinetic climax -> centered aftermath
        az0=-width if (a//4)%2==0 else width
        az1=-az0
        frames += [
          {"time_seconds":t0,"azimuth_deg":az0,"elevation_deg":elev,"distance_m":3.0,"section":name,"energy":e},
          {"time_seconds":(t0+t1)/2,"azimuth_deg":az1,"elevation_deg":elev,"distance_m":3.0,"section":name,"energy":e},
        ]
    frames.append({"time_seconds":duration,"azimuth_deg":0,"elevation_deg":0,"distance_m":3.0,"section":"Aftermath","energy":.15})
    return frames
