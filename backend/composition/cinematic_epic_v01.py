from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import random, struct

PPQ=480
BPM=86
SEED=20260921
BAR=PPQ*4

# 48 bars ~= 134 s at 86 BPM. Long enough for a real emotional arc.
SECTIONS=[
 ("Stillness",0,8),
 ("Awakening",8,16),
 ("Build",16,28),
 ("Acceleration",28,36),
 ("EpicClimax",36,44),
 ("Aftermath",44,48),
]

# Harmonic language: D minor cinematic, with pedal tones and dominant tension.
PROG=[
 ("Dm",(50,53,57,60)), ("Bb",(46,50,53,57)),
 ("F",(53,57,60,64)), ("C",(48,52,55,60)),
 ("Gm",(55,58,62,65)), ("Bb",(46,50,53,57)),
 ("Csus",(48,53,55,60)), ("A7",(45,49,52,55)),
]
SCALE=[50,52,53,55,57,58,60,62,64,65,67,69,70,72,74,77]

@dataclass
class Note:
    start:int; duration:int; pitch:int; velocity:int; channel:int=0

def vlq(n):
    b=[n&127]; n>>=7
    while n: b.append((n&127)|128); n>>=7
    return bytes(reversed(b))

def midi(notes,program,channel):
    tempo=round(60_000_000/BPM)
    ev=[(0,0,b"\xff\x51\x03"+tempo.to_bytes(3,"big")),(0,1,bytes([0xC0|channel,program]))]
    for n in notes:
        ev += [(n.start,2,bytes([0x90|n.channel,n.pitch,n.velocity])),
               (n.start+n.duration,1,bytes([0x80|n.channel,n.pitch,0]))]
    ev.sort(key=lambda x:(x[0],x[1]))
    tr=bytearray(); last=0
    for t,_,d in ev: tr+=vlq(t-last)+d; last=t
    tr+=b"\x00\xff\x2f\x00"
    return b"MThd"+struct.pack(">IHHH",6,0,1,PPQ)+b"MTrk"+struct.pack(">I",len(tr))+tr

def sec(bar):
    for name,a,b in SECTIONS:
        if a<=bar<b:return name
    return "Aftermath"

def vel(base,rng,j=4): return max(1,min(127,base+rng.randint(-j,j)))

def strings(rng):
    n=[]
    for bar in range(48):
        s=sec(bar); _,ch=PROG[bar%8]
        # cinematic open voicing: low root + fifth + upper chord colours
        pitches=[ch[0]-12,ch[2],ch[1]+12,ch[3]+12]
        if s=="Stillness": pitches=pitches[1:3]
        if s=="EpicClimax": pitches += [ch[2]+12]
        v={"Stillness":34,"Awakening":43,"Build":52,"Acceleration":59,"EpicClimax":70,"Aftermath":38}[s]
        for p in pitches:n.append(Note(bar*BAR,BAR-35,p,vel(v,rng,3)))
    return n

def brass(rng):
    n=[]
    for bar in range(48):
        s=sec(bar)
        if s in ("Stillness","Awakening") or (s=="Build" and bar%2): continue
        _,ch=PROG[bar%8]
        v={"Build":54,"Acceleration":67,"EpicClimax":82,"Aftermath":40}.get(s,45)
        dur=BAR-80 if s!="EpicClimax" else 2*PPQ-50
        beats=[0] if s=="Build" else ([0,2] if s in ("Acceleration","EpicClimax") else [0])
        for beat in beats:
            for p in (ch[0],ch[2],ch[1]+12):
                n.append(Note(bar*BAR+beat*PPQ,dur,p,vel(v,rng,4)))
    return n

def bass(rng):
    roots={"Dm":38,"Bb":34,"F":41,"C":36,"Gm":43,"Csus":36,"A7":33}
    n=[]
    for bar in range(48):
        s=sec(bar); name,_=PROG[bar%8]; r=roots[name]
        pattern={"Stillness":[(0,3.5,r)],
        "Awakening":[(0,2,r),(2,1.7,r+7)],
        "Build":[(0,1.5,r),(2,1.5,r+7)],
        "Acceleration":[(0,.8,r),(1,.8,r+7),(2,.8,r+12),(3,.8,r+7)],
        "EpicClimax":[(0,.72,r),(1,.72,r+7),(2,.72,r+12),(3,.72,r+7)],
        "Aftermath":[(0,3.2,r)]}[s]
        for beat,d,p in pattern:n.append(Note(bar*BAR+int(beat*PPQ),int(d*PPQ),p,vel(67 if s!="EpicClimax" else 78,rng)))
    return n

def percussion(rng):
    n=[]; K,S,T1,T2,HH,OH,CR=36,38,45,47,42,46,49
    for bar in range(48):
        s=sec(bar); base=bar*BAR
        if s=="Stillness":
            if bar in (0,4): n.append(Note(base,260,T1,48,9))
            continue
        if s=="Awakening":
            for beat in (0,2): n.append(Note(base+beat*PPQ,150,K,vel(62,rng),9))
            if bar%2: n.append(Note(base+3*PPQ,180,T1,vel(54,rng),9))
        elif s=="Build":
            for beat in (0,2): n.append(Note(base+beat*PPQ,130,K,vel(72,rng),9))
            for beat in (1,3): n.append(Note(base+beat*PPQ,120,S,vel(66,rng),9))
            for t in range(0,BAR,PPQ): n.append(Note(base+t,70,HH,vel(42,rng),9))
        elif s=="Acceleration":
            for beat in (0,1.5,2,3.5): n.append(Note(base+int(beat*PPQ),120,K,vel(80,rng),9))
            for beat in (1,3): n.append(Note(base+beat*PPQ,120,S,vel(75,rng),9))
            for t in range(0,BAR,PPQ//2): n.append(Note(base+t,65,HH,vel(49,rng),9))
            if bar%2: n.append(Note(base+3*PPQ+PPQ//2,100,OH,62,9))
        elif s=="EpicClimax":
            for beat in (0,1,2,3): n.append(Note(base+beat*PPQ,120,K,vel(91,rng),9))
            for beat in (1,3): n.append(Note(base+beat*PPQ,130,S,vel(84,rng),9))
            for t in range(0,BAR,PPQ//2): n.append(Note(base+t,60,HH,vel(56,rng),9))
            # tom fill at end of every second climax bar
            if bar%2:
                for i,p in enumerate((T1,T2,T1,T2)):
                    n.append(Note(base+3*PPQ+i*(PPQ//4),90,p,vel(75+i*3,rng),9))
        else:
            if bar==44:n.append(Note(base,350,CR,62,9))
        if bar in (8,16,28,36,44): n.append(Note(base,300,CR,vel(88 if bar==36 else 72,rng),9))
    return n

def melody(rng):
    n=[]; last=65
    motif=[0,3,5,7,5,3,2,0]
    for bar in range(48):
        s=sec(bar)
        if s=="Stillness" and bar<4: continue
        _,ch=PROG[bar%8]
        count={"Stillness":2,"Awakening":3,"Build":4,"Acceleration":6,"EpicClimax":8,"Aftermath":2}[s]
        upper=[p+12 for p in ch]
        for i in range(count):
            beat=i*4/count
            if i in (0,count-1): target=upper[(bar+i)%len(upper)]
            else:
                target=min(SCALE,key=lambda p:abs(p-(last+motif[(bar+i)%len(motif)])))
            while target-last>7:target-=12
            while last-target>7:target+=12
            target=max(60,min(79,target))
            dur=(4/count)*(.82 if s in ("Stillness","Aftermath") else .68)
            v={"Stillness":47,"Awakening":55,"Build":64,"Acceleration":72,"EpicClimax":82,"Aftermath":45}[s]
            n.append(Note(bar*BAR+int(beat*PPQ),int(dur*PPQ),target,vel(v,rng)))
            last=target
    return n

def pulse(rng):
    # Ostinato enters only after the calm opening and drives perceived acceleration.
    n=[]
    for bar in range(48):
        s=sec(bar)
        if s in ("Stillness","Aftermath"):continue
        _,ch=PROG[bar%8]; tones=[ch[0]+12,ch[2]+12,ch[1]+12,ch[2]+12]
        div={"Awakening":2,"Build":4,"Acceleration":8,"EpicClimax":8}[s]
        step=BAR//div
        v={"Awakening":38,"Build":48,"Acceleration":59,"EpicClimax":68}[s]
        for i in range(div):
            n.append(Note(bar*BAR+i*step,int(step*.55),tones[i%4],vel(v,rng,3)))
    return n

def generate(folder:Path):
    rng=random.Random(SEED); folder.mkdir(parents=True,exist_ok=True)
    roles=[
      ("strings",48,0,strings(rng)),
      ("brass",61,0,brass(rng)),
      ("bass",38,0,bass(rng)),
      ("epic_percussion",0,9,percussion(rng)),
      ("lead",81,0,melody(rng)),
      ("pulse_ostinato",48,0,pulse(rng)),
    ]
    result={}
    for i,(role,program,ch,notes) in enumerate(roles,1):
        p=folder/f"{i:02d}_{role}.mid"; p.write_bytes(midi(notes,program,ch))
        result[role]={"path":str(p),"notes":len(notes)}
    return result
