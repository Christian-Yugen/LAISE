from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import random
import struct

PPQ = 480
BPM = 92
SEED = 20260921
BAR_BEATS = 4
BAR_TICKS = PPQ * BAR_BEATS

SECTIONS = [
    ("Intro", 4),
    ("Development", 8),
    ("Crescendo", 8),
    ("Climax", 8),
    ("Resolution", 4),
]

# A minor with smoother functional motion than T002.
PROGRESSION = [
    ("Am9", (57, 60, 64, 71)),
    ("Fmaj7", (53, 57, 60, 64)),
    ("Cmaj7", (48, 52, 55, 59)),
    ("Gadd9", (55, 59, 62, 69)),
    ("Dm7", (50, 53, 57, 60)),
    ("Am/C", (48, 57, 60, 64)),
    ("Fmaj7", (53, 57, 60, 64)),
    ("E7", (52, 56, 59, 62)),
]

SCALE = [57, 59, 60, 62, 64, 65, 67, 69, 71, 72, 74, 76]


@dataclass
class Note:
    start: int
    duration: int
    pitch: int
    velocity: int
    channel: int = 0


def vlq(n: int) -> bytes:
    b = [n & 0x7F]
    n >>= 7
    while n:
        b.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(b))


def midi_file(notes, program, channel, bpm=BPM):
    tempo = round(60_000_000 / bpm)
    events = []
    events.append((0, 0, b"\xFF\x51\x03" + tempo.to_bytes(3, "big")))
    events.append((0, 1, bytes([0xC0 | channel, program])))
    for n in notes:
        events.append((n.start, 2, bytes([0x90 | n.channel, n.pitch, n.velocity])))
        events.append((n.start+n.duration, 1, bytes([0x80 | n.channel, n.pitch, 0])))
    events.sort(key=lambda x:(x[0],x[1]))
    track = bytearray()
    last=0
    for tick,_,data in events:
        track += vlq(tick-last)+data
        last=tick
    track += b"\x00\xFF\x2F\x00"
    header=b"MThd"+struct.pack(">IHHH",6,0,1,PPQ)
    return header+b"MTrk"+struct.pack(">I",len(track))+track


def section_for_bar(bar):
    cursor=0
    for name,bars in SECTIONS:
        if cursor <= bar < cursor+bars:
            return name
        cursor += bars
    return "Resolution"


def velocity(base, rng, amount=5):
    return max(1,min(127,base+rng.randint(-amount,amount)))


def pad_notes(rng):
    notes=[]
    for bar in range(32):
        sec=section_for_bar(bar)
        _, chord=PROGRESSION[bar % len(PROGRESSION)]
        # airy voicing: root lower, remaining chord tones spread upward
        pitches=[chord[0], chord[1]+12, chord[2]+12, chord[3]+12]
        if sec=="Intro" and bar<2:
            pitches=pitches[:3]
        if sec=="Climax":
            pitches += [chord[0]+24]
        vel={"Intro":42,"Development":48,"Crescendo":55,"Climax":62,"Resolution":43}[sec]
        for p in pitches:
            notes.append(Note(bar*BAR_TICKS, BAR_TICKS-40, p, velocity(vel,rng,3)))
    return notes


def bass_notes(rng):
    notes=[]
    roots={"Am9":45,"Fmaj7":41,"Cmaj7":36,"Gadd9":43,"Dm7":38,"Am/C":36,"E7":40}
    for bar in range(32):
        sec=section_for_bar(bar)
        name,_=PROGRESSION[bar%len(PROGRESSION)]
        root=roots[name]
        if sec=="Intro":
            pattern=[(0,2.8,root)]
        elif sec=="Development":
            pattern=[(0,1.5,root),(2,1.5,root+7)]
        elif sec=="Crescendo":
            pattern=[(0,0.9,root),(1,0.9,root+7),(2,0.9,root),(3,0.9,root+12)]
        elif sec=="Climax":
            pattern=[(0,0.8,root),(1,0.8,root+7),(2,0.8,root+12),(3,0.8,root+7)]
        else:
            pattern=[(0,1.8,root),(2,1.6,root+7)]
        for beat,dur,p in pattern:
            notes.append(Note(bar*BAR_TICKS+int(beat*PPQ),int(dur*PPQ),p,velocity(68,rng,4)))
    return notes


def drum_notes(rng):
    notes=[]
    K,S,H,OH,CR=36,38,42,46,49
    for bar in range(32):
        sec=section_for_bar(bar)
        base=bar*BAR_TICKS
        # musical backbeat, less machine-gun than v0.1
        for beat in [0,2]:
            notes.append(Note(base+beat*PPQ,120,K,velocity(82,rng,6),9))
        if sec in ("Crescendo","Climax"):
            notes.append(Note(base+3*PPQ,120,K,velocity(72,rng,6),9))
        for beat in [1,3]:
            notes.append(Note(base+beat*PPQ,120,S,velocity(76,rng,5),9))
        step = PPQ if sec=="Intro" else PPQ//2
        if sec=="Resolution": step=PPQ
        for t in range(0,BAR_TICKS,step):
            accent=8 if (t//step)%2==0 else -5
            notes.append(Note(base+t,80,H,velocity(48+accent,rng,4),9))
        if bar in (4,12,20,28):
            notes.append(Note(base,220,CR,88,9))
        if sec=="Climax" and bar%2==1:
            notes.append(Note(base+3*PPQ+PPQ//2,100,OH,65,9))
    return notes


def nearest_scale(target):
    return min(SCALE,key=lambda p:abs(p-target))


def lead_notes(rng):
    notes=[]
    last=69
    motifs=[
        [0,3,7,5],
        [0,2,3,7],
        [7,5,3,2],
        [0,3,2,-2],
    ]
    for bar in range(32):
        sec=section_for_bar(bar)
        if sec=="Intro" and bar<2: continue
        name,chord=PROGRESSION[bar%len(PROGRESSION)]
        chord_upper=[p+12 for p in chord]
        motif=motifs[(bar//2)%len(motifs)]
        density={"Intro":2,"Development":4,"Crescendo":6,"Climax":8,"Resolution":3}[sec]
        for i in range(density):
            beat=i*(4/density)
            if i%2==0:
                target=chord_upper[(i//2)%len(chord_upper)]
            else:
                target=nearest_scale(last+motif[i%len(motif)])
            # constrain melodic leaps
            while target-last>7: target-=12
            while last-target>7: target+=12
            target=max(60,min(81,target))
            dur=(4/density)*0.72
            vel={"Intro":55,"Development":62,"Crescendo":69,"Climax":76,"Resolution":54}[sec]
            notes.append(Note(bar*BAR_TICKS+int(beat*PPQ),int(dur*PPQ),target,velocity(vel,rng,4)))
            last=target
    return notes


def generate(output_dir: Path):
    rng=random.Random(SEED)
    output_dir.mkdir(parents=True,exist_ok=True)
    roles=[
        ("strings_pad",48,0,pad_notes(rng)),
        ("bass_sub",38,0,bass_notes(rng)),
        ("drums_impacts",0,9,drum_notes(rng)),
        ("lead_melody",81,0,lead_notes(rng)),
    ]
    result={}
    for idx,(role,program,ch,notes) in enumerate(roles,1):
        path=output_dir/f"{idx:02d}_{role}.mid"
        path.write_bytes(midi_file(notes,program,ch))
        result[role]={"path":str(path),"notes":len(notes)}
    return result
