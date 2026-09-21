from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import math, random, struct

from phrase_engine import PhraseEngine, Phrase
from motif_development import MotifDeveloper
from voice_interaction import VoiceInteractionEngine
from expressive_timing import ExpressiveTiming

PPQ=480
BPM=96
SEED=20260925
BAR=PPQ*4

# 40 bars ≈ 100 seconds before synth release tail.
SECTIONS=[
 ("Opening",0,8),
 ("Connection",8,16),
 ("Ascent",16,26),
 ("Breakthrough",26,34),
 ("Home",34,40),
]

# Original LAISE harmonic field: G major / E minor.
# Harmonic rhythm changes with narrative intensity.
PROG=[
 ("Em7",(52,55,59,62)),
 ("Cmaj9",(48,52,55,59,62)),
 ("Gadd9",(55,59,62,69)),
 ("Dadd4/F#",(54,57,62,67)),
 ("Am7",(57,60,64,67)),
 ("Cmaj7",(48,52,55,59)),
 ("G/B",(47,55,59,62)),
 ("D",(50,54,57,62)),
]
SCALE=[43,45,47,48,50,52,54,55,57,59,60,62,64,66,67,69,71,72,74,76,78,79,81]

@dataclass
class Note:
 start:int
 duration:int
 pitch:int
 velocity:int
 channel:int=0

def vlq(n:int)->bytes:
 b=[n&127]; n>>=7
 while n:
  b.append((n&127)|128); n>>=7
 return bytes(reversed(b))

def write_midi(path:Path,notes:list[Note],program:int,channel:int):
 tempo=round(60000000/BPM)
 events=[(0,0,b"\xff\x51\x03"+tempo.to_bytes(3,"big")),(0,1,bytes([0xC0|channel,program]))]
 for n in notes:
  events.append((max(0,n.start),2,bytes([0x90|n.channel,n.pitch,n.velocity])))
  events.append((max(1,n.start+n.duration),1,bytes([0x80|n.channel,n.pitch,0])))
 events.sort(key=lambda x:(x[0],x[1]))
 tr=bytearray();last=0
 for t,_,data in events:
  tr += vlq(t-last)+data; last=t
 tr += b"\x00\xff\x2f\x00"
 blob=b"MThd"+struct.pack(">IHHH",6,0,1,PPQ)+b"MTrk"+struct.pack(">I",len(tr))+tr
 path.write_bytes(blob)

def section(bar:int)->str:
 for name,a,b in SECTIONS:
  if a<=bar<b:return name
 return "Home"

def nearest_scale(target:int)->int:
 return min(SCALE,key=lambda p:abs(p-target))

def chord(bar:int):
 return PROG[bar%len(PROG)][1]

def root_for_bar(bar:int)->int:
 return chord(bar)[0]

def expressive_phrase_notes(phrase:Phrase,start_bar:int,base_pitch:int,
                            ex:ExpressiveTiming,velocity_bias:int=0)->list[Note]:
 out=[]
 total_beats=phrase.bars*4
 for i,pn in enumerate(phrase.notes):
  pitch=nearest_scale(base_pitch+pn.degree)
  off=ex.timing_offset_ticks(pn.beat,total_beats,pn.articulation)
  start=start_bar*BAR+round(pn.beat*PPQ)+off
  dur=round(pn.duration*PPQ*ex.duration_factor(pn.articulation))
  vel=max(1,min(127,pn.velocity+velocity_bias))
  out.append(Note(start,dur,pitch,vel))
 return out

def phrase_plan():
 pe=PhraseEngine(SEED)
 md=MotifDeveloper()
 # Central original motif; every melodic family below is derived from it.
 motif=[0,2,4,2,1,0,-2,1]
 base_arc=pe.make_arc(motif)
 # Narrative uses recurring/varied phrase functions, not isolated melodies.
 plan=[
  (0,base_arc[0],0,-7),       # statement
  (4,base_arc[1],0,-6),       # response
  (8,pe.statement(md.transpose(motif,2),"P5"),2,-3),
  (12,pe.response(pe.statement(md.transpose(motif,2),"tmp"),"P6"),2,-2),
  (16,base_arc[2],0,2),       # development
  (20,pe.develop(pe.statement(md.transpose(motif,-1),"tmp2"),"P7"),-1,4),
  (24,pe.response(base_arc[0],"P8"),0,2),
  (26,pe.develop(pe.statement(md.transpose(motif,2),"tmp3"),"P9"),2,8),
  (30,pe.develop(pe.statement(md.transpose(motif,4),"tmp4"),"P10"),4,11),
  (34,base_arc[3],0,-1),      # resolution
  (38,pe.resolve(base_arc[0],0,"P11"),0,-5),
 ]
 return motif,plan

def make_theme(ex):
 motif,plan=phrase_plan(); notes=[]
 for bar,p,shift,vbias in plan:
  base=55+shift
  notes.extend(expressive_phrase_notes(p,bar,base,ex,vbias))
 return motif,plan,notes

def make_piano(r,ex,plan):
 n=[]
 # Piano accompaniment follows phrase boundaries and leaves breath around cadences.
 for bar in range(40):
  s=section(bar); ch=chord(bar)
  intensity={"Opening":.28,"Connection":.40,"Ascent":.57,"Breakthrough":.78,"Home":.34}[s]
  tones=[ch[0],ch[2],ch[1]+12,ch[-1]+12]
  div=4 if s in ("Opening","Home") else 6 if s=="Connection" else 8
  step=BAR/div
  pattern=[0,2,1,2,3,2,1,2]
  # Bass note anchors harmony without becoming another melody.
  n.append(Note(bar*BAR,int(BAR*.86),ch[0]-12,round(35+intensity*18+r.randint(-2,2))))
  for i in range(div):
   # Phrase-aware microtiming; small enough to preserve ensemble.
   pos=i*(4/div)
   off=ex.timing_offset_ticks(pos,4,"legato")
   vel=round(39+intensity*23+6*math.sin(math.pi*(i+1)/(div+1))+r.randint(-2,2))
   dur=round(step*(.73 if s!="Home" else .88))
   n.append(Note(max(bar*BAR,bar*BAR+round(i*step)+off),dur,tones[pattern[i]],vel))
 return n

def make_strings(r,plan):
 n=[]
 phrase_starts={bar:p.function for bar,p,_,_ in plan}
 for bar in range(40):
  s=section(bar)
  if bar<3: continue
  ch=chord(bar)
  v={"Opening":27,"Connection":38,"Ascent":50,"Breakthrough":64,"Home":34}[s]
  # In response/resolution, strings enter a little before the phrase to "inhale".
  anticipation=-55 if phrase_starts.get(bar) in ("response","resolution") else -24
  pitches=[ch[2],ch[1]+12,ch[-1]+12]
  if s=="Breakthrough": pitches=[ch[0],ch[2],ch[1]+12,ch[-1]+12]
  for p in pitches:
   n.append(Note(max(0,bar*BAR+anticipation),BAR+105,p,max(1,v+r.randint(-2,2))))
 return n

def make_bass(r):
 n=[]
 for bar in range(40):
  s=section(bar)
  if bar<6:continue
  root=chord(bar)[0]-12
  if s=="Connection":pat=[(0,root,3.2)]
  elif s=="Ascent":pat=[(0,root,1.7),(2,nearest_scale(root+7),1.55)]
  elif s=="Breakthrough":pat=[(0,root,1.2),(1.5,nearest_scale(root+7),.9),(3,root+12,.75)]
  else:pat=[(0,root,3.3)]
  base={"Connection":43,"Ascent":52,"Breakthrough":62,"Home":39}.get(s,40)
  for beat,p,d in pat:n.append(Note(bar*BAR+round(beat*PPQ),round(d*PPQ),p,base+r.randint(-2,2)))
 return n

def make_ostinato(r,md,motif):
 n=[]
 frag=md.fragment(motif,4)
 for bar in range(16,34):
  s=section(bar);ch=chord(bar)
  div=4 if bar<22 else 8
  step=BAR/div
  chordtones=[ch[0]+12,ch[1]+12,ch[2]+12,ch[-1]+12]
  for i in range(div):
   # Contour selection is derived from motif fragment.
   deg=frag[i%len(frag)]
   idx=abs(deg)%len(chordtones)
   vel=(40 if s=="Ascent" else 51)+r.randint(-2,2)
   n.append(Note(bar*BAR+round(i*step),round(step*.58),chordtones[idx],vel))
 return n

def make_percussion(r):
 n=[];K,S,HH,T1,T2,CR=36,38,42,45,47,49
 for bar in range(40):
  s=section(bar);base=bar*BAR
  if s=="Opening" or s=="Home":continue
  if s=="Connection":
   if bar in (10,14):n.append(Note(base,180,T1,43+r.randint(-2,2),9))
  elif s=="Ascent":
   for b in (0,2):n.append(Note(base+b*PPQ,105,K,55+r.randint(-3,3),9))
   if bar>=20:
    for t in range(0,BAR,PPQ):n.append(Note(base+t,50,HH,34+r.randint(-2,2),9))
  else:
   for b in (0,2,3):n.append(Note(base+b*PPQ,110,K,70+r.randint(-3,3),9))
   for b in (1,3):n.append(Note(base+b*PPQ,105,S,64+r.randint(-3,3),9))
   for t in range(0,BAR,PPQ//2):n.append(Note(base+t,48,HH,42+r.randint(-2,2),9))
   if bar in (26,30):n.append(Note(base,250,CR,75+r.randint(-2,2),9))
   if bar in (29,33):
    for i,p in enumerate((T1,T1,T2,T2)):
     n.append(Note(base+3*PPQ+i*PPQ//4,75,p,58+i*4,9))
 return n

def make_brass(r):
 n=[]
 # Brass is rhetorical punctuation, not a continuous independent layer.
 for bar in (22,26,28,30,32):
  ch=chord(bar);s=section(bar)
  v=54 if s=="Ascent" else 66
  for p in (ch[0],ch[2],ch[1]+12):
   n.append(Note(bar*BAR,round(1.55*PPQ),p,v+r.randint(-2,2)))
 return n

def generate(folder:Path):
 folder.mkdir(parents=True,exist_ok=True)
 r=random.Random(SEED)
 ex=ExpressiveTiming(SEED,PPQ)
 md=MotifDeveloper()
 motif,plan,theme=make_theme(ex)
 roles=[
  ("piano",0,0,make_piano(r,ex,plan)),
  ("theme",73,0,theme),
  ("strings",48,0,make_strings(r,plan)),
  ("bass",42,0,make_bass(r)),
  ("ostinato",48,0,make_ostinato(r,md,motif)),
  ("percussion",0,9,make_percussion(r)),
  ("brass",61,0,make_brass(r)),
 ]
 result={}
 for i,(role,program,ch,notes) in enumerate(roles,1):
  p=folder/f"{i:02d}_{role}.mid"
  write_midi(p,notes,program,ch)
  result[role]={"path":str(p),"notes":len(notes)}
 phrase_meta=[{"bar":bar,"phrase_id":p.phrase_id,"function":p.function,
               "tension_start":p.tension_start,"tension_end":p.tension_end}
              for bar,p,_,_ in plan]
 return result,{"motif":motif,"phrase_plan":phrase_meta}
