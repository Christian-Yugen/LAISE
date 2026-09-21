from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import math, random, struct

from phrase_engine import PhraseEngine
from motif_development import MotifDeveloper
from expressive_timing import ExpressiveTiming
from emotional_narrative import EmotionalNarrative
from harmonic_narrative import HarmonicNarrativeEngine
from narrative_planner import NarrativePlanner

PPQ=480
BPM=96
SEED=20260927
BAR=PPQ*4
TOTAL_BARS=40
SCALE=[43,45,47,48,50,52,54,55,57,59,60,62,64,66,67,69,71,72,74,76,78,79,81]

@dataclass
class Note:
 start:int; duration:int; pitch:int; velocity:int; channel:int=0

def vlq(n):
 b=[n&127];n>>=7
 while n:b.append((n&127)|128);n>>=7
 return bytes(reversed(b))

def write_midi(path,notes,program,channel):
 tempo=round(60000000/BPM)
 ev=[(0,0,b"\xff\x51\x03"+tempo.to_bytes(3,"big")),(0,1,bytes([0xC0|channel,program]))]
 for n in notes:
  ev += [(max(0,n.start),2,bytes([0x90|n.channel,n.pitch,n.velocity])),
         (max(1,n.start+n.duration),1,bytes([0x80|n.channel,n.pitch,0]))]
 ev.sort(key=lambda x:(x[0],x[1]))
 tr=bytearray();last=0
 for t,_,d in ev:tr+=vlq(t-last)+d;last=t
 tr+=b"\x00\xff\x2f\x00"
 path.write_bytes(b"MThd"+struct.pack(">IHHH",6,0,1,PPQ)+b"MTrk"+struct.pack(">I",len(tr))+tr)

def nearest(p):return min(SCALE,key=lambda x:abs(x-p))

def build_harmonic_map():
 curve=EmotionalNarrative().hopeful_cinematic(TOTAL_BARS)
 engine=HarmonicNarrativeEngine(SEED)
 events=engine.compose(curve)
 planner=NarrativePlanner().build(curve)

 # HarmonicEvent is the narrative/audit record and intentionally does not
 # duplicate MIDI pitches. Resolve its symbolic state back to the canonical
 # HarmonicState owned by HarmonicNarrativeEngine before orchestration.
 bars={}
 for i,event in enumerate(events):
  end=events[i+1].bar if i+1<len(events) else TOTAL_BARS
  state=engine.by_name[event.state]
  for b in range(event.bar,end):
   bars[b]=state

 return curve,events,planner,bars

def phrase_for(function,pe,md,motif,idx):
 shift=(idx%3)-1
 src=pe.statement(md.transpose(motif,shift),f"S{idx}")
 if function=="statement":return src
 if function=="response":return pe.response(src,f"R{idx}")
 if function=="development":return pe.develop(src,f"D{idx}")
 return pe.resolve(src,0,f"Z{idx}")

def make_theme(ex,planner):
 pe=PhraseEngine(SEED);md=MotifDeveloper();motif=[0,2,4,2,1,0,-2,1];notes=[];meta=[]
 for i,p in enumerate(planner):
  bar=p["bar"]
  if bar>=TOTAL_BARS:continue
  phr=phrase_for(p["phrase_function"],pe,md,motif,i)
  base=55 + (2 if p["phase"]=="breakthrough" else 0)
  for j,pn in enumerate(phr.notes):
   beat=pn.beat
   if bar*BAR+beat*PPQ>=TOTAL_BARS*BAR:continue
   off=ex.timing_offset_ticks(beat,phr.bars*4,pn.articulation)
   pitch=nearest(base+pn.degree)
   vel=max(1,min(127,round(pn.velocity*(.76+.34*p["energy"]))))
   dur=round(pn.duration*PPQ*ex.duration_factor(pn.articulation))
   notes.append(Note(bar*BAR+round(beat*PPQ)+off,dur,pitch,vel))
  meta.append({"bar":bar,"phrase_id":phr.phrase_id,"function":phr.function,"phase":p["phase"]})
 return motif,notes,meta

def piano(r,ex,planner,bars):
 n=[]
 density_by_bar={}
 for i,p in enumerate(planner):
  end=planner[i+1]["bar"] if i+1<len(planner) else TOTAL_BARS
  for b in range(p["bar"],end):density_by_bar[b]=p["density"]
 for bar in range(TOTAL_BARS):
  e=bars[bar];ch=e.pitches;density=density_by_bar.get(bar,.35)
  div=4 if density<.48 else 6 if density<.70 else 8
  step=BAR/div; tones=[ch[0],ch[min(2,len(ch)-1)],ch[1]+12,ch[-1]+12]
  n.append(Note(bar*BAR,int(BAR*.84),ch[0]-12,round(34+24*density+r.randint(-2,2))))
  pat=[0,2,1,2,3,2,1,2]
  for i in range(div):
   off=ex.timing_offset_ticks(i*4/div,4,"legato")
   arch=math.sin(math.pi*(i+1)/(div+1))
   vel=round(38+22*density+5*arch+r.randint(-2,2))
   n.append(Note(max(bar*BAR,bar*BAR+round(i*step)+off),round(step*.76),tones[pat[i]],vel))
 return n

def strings(r,planner,bars):
 n=[];energy={}
 for i,p in enumerate(planner):
  end=planner[i+1]["bar"] if i+1<len(planner) else TOTAL_BARS
  for b in range(p["bar"],end):energy[b]=(p["energy"],p["phase"])
 for bar in range(TOTAL_BARS):
  en,phase=energy.get(bar,(.2,"stability"))
  if bar<3:continue
  ch=bars[bar].pitches
  ps=[ch[min(2,len(ch)-1)],ch[1]+12,ch[-1]+12]
  if en>.78:ps=[ch[0],ch[min(2,len(ch)-1)],ch[1]+12,ch[-1]+12]
  v=round(26+43*en)+r.randint(-2,2)
  ant=-65 if phase in ("preparation","resolution") else -25
  for p in ps:n.append(Note(max(0,bar*BAR+ant),BAR+110,p,v))
 return n

def bass(r,planner,bars):
 n=[];energy={}
 for i,p in enumerate(planner):
  end=planner[i+1]["bar"] if i+1<len(planner) else TOTAL_BARS
  for b in range(p["bar"],end):energy[b]=p["energy"]
 for bar in range(5,TOTAL_BARS):
  en=energy.get(bar,.3);root=bars[bar].pitches[0]-12
  pat=[(0,root,3.1)] if en<.5 else [(0,root,1.7),(2,nearest(root+7),1.5)]
  if en>.8:pat=[(0,root,1.15),(1.5,nearest(root+7),.9),(3,root+12,.75)]
  for beat,p,d in pat:n.append(Note(bar*BAR+round(beat*PPQ),round(d*PPQ),p,round(39+25*en)+r.randint(-2,2)))
 return n

def ostinato(r,planner,bars,motif):
 n=[];md=MotifDeveloper();frag=md.fragment(motif,4);energy={}
 for i,p in enumerate(planner):
  end=planner[i+1]["bar"] if i+1<len(planner) else TOTAL_BARS
  for b in range(p["bar"],end):energy[b]=p["energy"]
 for bar in range(TOTAL_BARS):
  en=energy.get(bar,.2)
  if en<.52:continue
  ch=bars[bar].pitches;tones=[ch[0]+12,ch[1]+12,ch[min(2,len(ch)-1)]+12,ch[-1]+12]
  div=4 if en<.76 else 8;step=BAR/div
  for i in range(div):
   idx=abs(frag[i%4])%len(tones)
   n.append(Note(bar*BAR+round(i*step),round(step*.58),tones[idx],round(34+23*en)+r.randint(-2,2)))
 return n

def percussion(r,planner):
 n=[];K,S,HH,T1,T2,CR=36,38,42,45,47,49;energy={}
 for i,p in enumerate(planner):
  end=planner[i+1]["bar"] if i+1<len(planner) else TOTAL_BARS
  for b in range(p["bar"],end):energy[b]=(p["energy"],p["phase"])
 for bar in range(TOTAL_BARS):
  en,phase=energy.get(bar,(.2,"stability"));base=bar*BAR
  if en<.38:continue
  if en<.58:
   if bar%2==0:n.append(Note(base,160,T1,42+r.randint(-2,2),9))
  elif en<.80:
   for b in (0,2):n.append(Note(base+b*PPQ,105,K,round(48+20*en)+r.randint(-3,3),9))
   for t in range(0,BAR,PPQ):n.append(Note(base+t,48,HH,31+r.randint(-2,2),9))
  else:
   for b in (0,2,3):n.append(Note(base+b*PPQ,110,K,round(57+22*en)+r.randint(-3,3),9))
   for b in (1,3):n.append(Note(base+b*PPQ,105,S,round(52+20*en)+r.randint(-3,3),9))
   for t in range(0,BAR,PPQ//2):n.append(Note(base+t,45,HH,40+r.randint(-2,2),9))
   if phase in ("suspension","breakthrough"):n.append(Note(base,240,CR,72+r.randint(-2,2),9))
 return n

def brass(r,planner,bars):
 n=[]
 for p in planner:
  if p["energy"]<.72:continue
  bar=p["bar"];ch=bars[bar].pitches
  v=round(48+22*p["energy"])+r.randint(-2,2)
  for pitch in (ch[0],ch[min(2,len(ch)-1)],ch[1]+12):
   n.append(Note(bar*BAR,round(1.5*PPQ),pitch,v))
 return n

def generate(folder:Path):
 folder.mkdir(parents=True,exist_ok=True)
 r=random.Random(SEED);ex=ExpressiveTiming(SEED,PPQ)
 curve,hevents,planner,bars=build_harmonic_map()
 motif,theme,phrase_meta=make_theme(ex,planner)
 roles=[
  ("piano",0,0,piano(r,ex,planner,bars)),
  ("theme",73,0,theme),
  ("strings",48,0,strings(r,planner,bars)),
  ("bass",42,0,bass(r,planner,bars)),
  ("ostinato",48,0,ostinato(r,planner,bars,motif)),
  ("percussion",0,9,percussion(r,planner)),
  ("brass",61,0,brass(r,planner,bars)),
 ]
 result={}
 for i,(role,program,ch,notes) in enumerate(roles,1):
  p=folder/f"{i:02d}_{role}.mid";write_midi(p,notes,program,ch)
  result[role]={"path":str(p),"notes":len(notes)}
 meta={"motif":motif,"emotional_curve":curve,
       "harmonic_events":[x.__dict__ for x in hevents],
       "narrative_plan":planner,"phrase_plan":phrase_meta}
 return result,meta
