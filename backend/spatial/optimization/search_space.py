from itertools import product
def build_search_space():
    distances=[1,1.25,1.5,1.75,2,2.2,2.4,2.6,2.7,2.8,2.9,3,3.1,3.2,3.3,3.4,3.5,3.6,3.8,4,4.5]
    gains=[-24,-20,-16,-14,-12,-10,-8,-6,-4,-3,-2,-1,0]
    out=[]; n=1
    for d,g in product(distances,gains):
        out.append({"candidate_id":f"N{n:04d}","family":"early_reflection","distance_m":float(d),"reflection_gain_db":float(g),"virtual_acoustics":"MediumRecordingHall","reflection":True,"reverb":False,"azimuth_deg":0.0,"elevation_deg":0.0}); n+=1
    for d in [1,2,3,4,6]:
        out.append({"candidate_id":f"N{n:04d}","family":"dry_control","distance_m":float(d),"reflection_gain_db":None,"virtual_acoustics":"DirectSignal","reflection":False,"reverb":False,"azimuth_deg":0.0,"elevation_deg":0.0}); n+=1
    return out
