from __future__ import annotations

# Section-aware spatial plan. The spatial scene now follows musical form.
SECTION_PLAN = [
    ("Intro", 0, 4, 0.35),
    ("Development", 4, 12, 0.55),
    ("Crescendo", 12, 20, 0.78),
    ("Climax", 20, 28, 1.00),
    ("Resolution", 28, 32, 0.40),
]

def section_keyframes(duration_seconds: float, role: str):
    bar_seconds=duration_seconds/32.0
    frames=[]
    for name,start_bar,end_bar,energy in SECTION_PLAN:
        t0=start_bar*bar_seconds
        t1=end_bar*bar_seconds
        if role=="bass_sub":
            az0,az1=-3*energy,3*energy
            el=-3
        elif role=="strings_pad":
            width=18+28*energy
            az0,az1=-width,width
            el=8+10*energy
        elif role=="drums_impacts":
            width=22+38*energy
            az0,az1=(-width,width) if start_bar%8==4 else (width,-width)
            el=2+6*energy
        else:
            width=25+45*energy
            az0,az1=-width,width
            el=3+9*energy
        frames.append({"time_seconds":t0,"azimuth_deg":az0,"elevation_deg":el,"distance_m":3.0,
                       "section":name,"energy":energy})
        frames.append({"time_seconds":(t0+t1)/2,"azimuth_deg":az1,"elevation_deg":el,"distance_m":3.0,
                       "section":name,"energy":energy})
    # Explicit resolution endpoint.
    frames.append({"time_seconds":duration_seconds,"azimuth_deg":0.0,"elevation_deg":0.0,
                   "distance_m":3.0,"section":"Resolution","energy":0.25})
    return frames
