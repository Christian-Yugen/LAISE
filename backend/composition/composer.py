from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib, json, random, struct

PPQ=480
DEFAULT_SEED=20260921
DEFAULT_BPM=96
SECTIONS=[("Intro",4),("Development",8),("Crescendo",8),("Climax",8),("Resolution",4)]
PROGRESSION=("Am","F","C","G","Am","F","Dm","Em")
CHORDS={"Am":(57,60,64),"F":(53,57,60),"C":(48,52,55),"G":(55,59,62),"Dm":(50,53,57),"Em":(52,55,59)}
SCALE_PCS=(9,11,0,2,4,5,7)
ROLE_FILES={"strings_pad":"01_strings_pad.mid","bass_sub":"02_bass_sub.mid","drums_impacts":"03_drums_impacts.mid","lead_melody":"04_lead_melody.mid"}
GM_PROGRAMS={"strings_pad":48,"bass_sub":38,"lead_melody":81}

@dataclass(frozen=True)
class Note:
    start_beats:float; duration_beats:float; pitch:int; velocity:int; channel:int=0

def _vlq(v):
    b=[v&127]; v>>=7
    while v: b.insert(0,(v&127)|128); v>>=7
    return bytes(b)

def _write_midi(path,notes,bpm,program,name,drums=False):
    tempo=round(60000000/bpm); ev=[]
    nb=name.encode()
    ev += [(0,0,b"\xff\x03"+_vlq(len(nb))+nb),(0,1,b"\xff\x51\x03"+tempo.to_bytes(3,"big")),(0,2,b"\xff\x58\x04\x04\x02\x18\x08")]
    if program is not None and not drums: ev.append((0,3,bytes([0xC0,program])))
    for n in notes:
        s=round(n.start_beats*PPQ); e=round((n.start_beats+n.duration_beats)*PPQ); ch=9 if drums else n.channel
        ev.append((s,10,bytes([0x90|ch,n.pitch, n.velocity])))
        ev.append((e,5,bytes([0x80|ch,n.pitch,0])))
    ev.sort(key=lambda x:(x[0],x[1])); body=bytearray(); prev=0
    for tick,_,raw in ev: body+=_vlq(tick-prev)+raw; prev=tick
    body+=b"\x00\xff\x2f\x00"
    path.write_bytes(b"MThd"+struct.pack(">IHHH",6,0,1,PPQ)+b"MTrk"+struct.pack(">I",len(body))+body)

def _section(bar):
    c=0
    for name,n in SECTIONS:
        if c<=bar<c+n:return name
        c+=n
    return "Resolution"

def _vel(sec,base):
    return max(20,min(120,base+{"Intro":-14,"Development":-5,"Crescendo":3,"Climax":12,"Resolution":-10}[sec]))

def _pad():
    a=[]
    for bar in range(32):
        sec=_section(bar); chord=CHORDS[PROGRESSION[bar%8]]; pitches=list(chord)+( [chord[0]+12] if sec=="Climax" else [])
        for p in pitches:a.append(Note(bar*4,3.92,p+12,_vel(sec,58)))
    return a

def _bass():
    a=[]
    for bar in range(32):
        sec=_section(bar); root=CHORDS[PROGRESSION[bar%8]][0]-12
        pat=[(0,3.75,root)] if sec=="Intro" else ([(0,1.75,root),(2,1.75,root+7)] if sec in ("Development","Resolution") else [(0,.85,root),(1,.85,root+7),(2,.85,root),(3,.85,root+12)])
        for o,d,p in pat:a.append(Note(bar*4+o,d,p,_vel(sec,72)))
    return a

def _drums(rng):
    a=[]
    for bar in range(32):
        sec=_section(bar); st=bar*4
        if sec!="Intro" or bar>=2:
            kicks=(0,2) if sec not in ("Crescendo","Climax") else (0,1.5,2,3.25)
            for x in kicks:a.append(Note(st+x,.12,36,_vel(sec,88),9))
        if sec!="Intro":
            for x in (1,3):a.append(Note(st+x,.12,38,_vel(sec,82),9))
        step=.25 if sec=="Climax" else (.5 if sec not in ("Intro","Resolution") else 1)
        x=0
        while x<4:
            a.append(Note(st+x,.08,42,max(25,min(110,_vel(sec,52)+rng.choice((-4,0,3)))),9)); x+=step
        if bar in (4,12,20,28):
            a += [Note(st,.5,49,105,9),Note(st,.35,45,92,9)]
    return a

def _pitch(pc,target):
    cs=[pc+12*o for o in range(1,9) if 64<=pc+12*o<=81]
    return min(cs,key=lambda p:abs(p-target))

def _lead(rng):
    a=[]; prev=69
    for bar in range(32):
        sec=_section(bar); st=bar*4
        if sec=="Intro" and bar<2:continue
        density={"Intro":2,"Development":4,"Crescendo":6,"Climax":8,"Resolution":2}[sec]; step=4/density
        chordpcs={p%12 for p in CHORDS[PROGRESSION[bar%8]]}
        for i in range(density):
            pcs=sorted(chordpcs) if i%2==0 else SCALE_PCS
            choices=sorted((_pitch(pc,prev) for pc in pcs),key=lambda p:abs(p-prev))
            p=rng.choice(choices[:min(4,len(choices))])
            if sec=="Climax" and rng.random()<.18 and p+12<=84:p+=12
            a.append(Note(st+i*step,step*(.9 if sec=="Resolution" else .72),p,max(30,min(118,_vel(sec,70)+rng.choice((-5,0,4))))))
            prev=p
    return a

def generate_midi_set(output_dir,seed=DEFAULT_SEED,bpm=DEFAULT_BPM):
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); rng=random.Random(seed)
    tracks={"strings_pad":_pad(),"bass_sub":_bass(),"drums_impacts":_drums(rng),"lead_melody":_lead(rng)}
    cursor=0; sections=[]
    for name,n in SECTIONS: sections.append({"name":name,"start_bar":cursor+1,"end_bar":cursor+n,"bars":n}); cursor+=n
    plan={"seed":seed,"bpm":bpm,"meter":"4/4","key":"A","mode":"natural_minor","bars":32,"duration_seconds":32*4*60/bpm,"sections":sections}
    for role,fn in ROLE_FILES.items():
        _write_midi(out/fn,tracks[role],bpm,None if role=="drums_impacts" else GM_PROGRAMS[role],role,role=="drums_impacts")
    return {"plan":plan,"note_counts":{k:len(v) for k,v in tracks.items()},"midi_files":{k:str(out/v) for k,v in ROLE_FILES.items()}}
