from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import random, struct, math

PPQ=480
BPM=98
SEED=20260923
BAR=PPQ*4
# ~78 s + release tail. Original LAISE composition; the reference is used only
# for high-level form/energy/arrangement principles, not melody or note copying.
SECTIONS=[
 ("Intimate",0,6),
 ("Bloom",6,14),
 ("Lift",14,22),
 ("Crescendo",22,29),
 ("Peak",29,33),
]
# G major / E minor palette. Original progression with changing harmonic rhythm.
PROG=[
 ("Em7",(52,55,59,62)),("Cmaj9",(48,52,55,59)),
 ("Gadd9",(55,59,62,69)),("D/F#",(54,57,62,66)),
 ("Am7",(57,60,64,67)),("Cmaj7",(48,52,55,59)),
 ("G/B",(47,55,59,62)),("Dsus4",(50,55,57,62)),
]
SCALE=[55,57,59,60,62,64,66,67,69,71,72,74,76,78,79]
@dataclass
class Note:
 start:int; duration:int; pitch:int; velocity:int; channel:int=0

def vlq(n):
 b=[n&127];n>>=7
 while n:b.append((n&127)|128);n>>=7
 return bytes(reversed(b))

def midi(notes,program,channel):
 tempo=round(60000000/BPM)
 ev=[(0,0,b"\xff\x51\x03"+tempo.to_bytes(3,"big")),(0,1,bytes([0xC0|channel,program]))]
 for n in notes:
  ev += [(n.start,2,bytes([0x90|n.channel,n.pitch,n.velocity])),
         (n.start+n.duration,1,bytes([0x80|n.channel,n.pitch,0]))]
 ev.sort(key=lambda x:(x[0],x[1]))
 tr=bytearray();last=0
 for t,_,d in ev:tr+=vlq(t-last)+d;last=t
 tr+=b"\x00\xff\x2f\x00"
 return b"MThd"+struct.pack(">IHHH",6,0,1,PPQ)+b"MTrk"+struct.pack(">I",len(tr))+tr

def sec(bar):
 for name,a,b in SECTIONS:
  if a<=bar<b:return name
 return "Peak"

def vv(base,rng,j=3):
 return max(1,min(127,base+rng.randint(-j,j)))

# One central thematic cell. Other roles derive from this rather than inventing
# independent melodies.
THEME_DEGREES=[0,2,4,2,1,0,-2,1]
THEME_RHYTHM=[1.0,.5,.5,1.0,.5,.5,1.0,1.0]

def scale_near(target):
 return min(SCALE,key=lambda p:abs(p-target))

def theme_phrase(start_tick,root_hint,rng,variant=0,energy=.4):
 notes=[];last=root_hint+12
 degrees=THEME_DEGREES[:]
 if variant==1: degrees=[0,2,4,5,4,2,1,0]
 elif variant==2: degrees=[0,1,2,4,2,1,0,-2]
 elif variant==3: degrees=[0,2,4,7,4,2,0,1]
 cursor=start_tick
 for i,(deg,beats) in enumerate(zip(degrees,THEME_RHYTHM)):
  target=scale_near(root_hint+12+deg)
  while target-last>7:target-=12
  while last-target>7:target+=12
  # expressive overlap: legato phrases are deliberately longer than grid cells
  dur=int(beats*PPQ*(1.08 if i not in (3,7) else .88))
  shape=math.sin(math.pi*(i+1)/(len(degrees)+1))
  vel=int(43+energy*25+shape*8)
  notes.append(Note(cursor,dur,target,vv(vel,rng,2)))
  cursor += int(beats*PPQ)
  last=target
 return notes

def piano(r):
 n=[]
 for bar in range(33):
  s=sec(bar);_,ch=PROG[bar%8]
  # left hand breathes; right hand uses arpeggio only between theme statements.
  root=ch[0]-12
  n.append(Note(bar*BAR,int(3.65*PPQ),root,vv({"Intimate":38,"Bloom":42,"Lift":47,"Crescendo":51,"Peak":54}[s],r,2)))
  tones=[ch[0],ch[2],ch[1]+12,ch[3]+12]
  div={"Intimate":4,"Bloom":6,"Lift":6,"Crescendo":8,"Peak":8}[s]
  step=BAR//div
  pattern=[0,2,1,2,3,2,1,2]
  for i in range(div):
   # slight deterministic humanization; never enough to break pulse
   jitter=r.randint(-14,14)
   st=max(bar*BAR,bar*BAR+i*step+jitter)
   v={"Intimate":43,"Bloom":47,"Lift":51,"Crescendo":56,"Peak":59}[s]
   n.append(Note(st,int(step*.78),tones[pattern[i]],vv(v,r,3)))
 return n

def theme(r):
 n=[]
 starts=[(1,0,.20),(7,1,.38),(15,2,.55),(23,1,.72),(29,3,.92)]
 for bar,var,e in starts:
  _,ch=PROG[bar%8]
  n.extend(theme_phrase(bar*BAR,ch[0],r,var,e))
 return n

def strings(r):
 n=[]
 for bar in range(33):
  s=sec(bar)
  if s=="Intimate" and bar<4:continue
  _,ch=PROG[bar%8]
  # voice-led sustained harmony: common tones overlap across bar boundaries
  ps=[ch[2],ch[1]+12,ch[3]+12]
  if s in ("Crescendo","Peak"):ps=[ch[0],ch[2],ch[1]+12,ch[3]+12]
  v={"Intimate":28,"Bloom":39,"Lift":48,"Crescendo":59,"Peak":67}[s]
  for p in ps:n.append(Note(bar*BAR-20 if bar else 0,BAR+70,p,vv(v,r,2)))
 return n

def cello(r):
 n=[]
 for bar in range(33):
  s=sec(bar)
  if s=="Intimate" and bar<5:continue
  _,ch=PROG[bar%8];root=ch[0]-12
  if s=="Bloom":pat=[(0,root,2.8)]
  elif s=="Lift":pat=[(0,root,1.7),(2,root+7,1.6)]
  elif s in ("Crescendo","Peak"):pat=[(0,root,1.25),(1.5,root+7,1.0),(3,root+12,.8)]
  else:pat=[(0,root,3.0)]
  for beat,p,d in pat:n.append(Note(bar*BAR+int(beat*PPQ),int(d*PPQ),p,vv(50+(8 if s=="Peak" else 0),r,3)))
 return n

def ostinato(r):
 n=[]
 for bar in range(14,33):
  s=sec(bar);_,ch=PROG[bar%8]
  tones=[ch[0]+12,ch[2]+12,ch[1]+12,ch[2]+12]
  div=4 if s=="Lift" else 8
  step=BAR//div
  for i in range(div):
   # derived from chord and theme contour, not an unrelated line
   idx=[0,2,1,2,0,2,3,2][i%8]
   n.append(Note(bar*BAR+i*step,int(step*.62),tones[idx],vv(39+(10 if s=="Crescendo" else 16 if s=="Peak" else 0),r,2)))
 return n

def percussion(r):
 n=[];K,S,T1,T2,HH,CR=36,38,45,47,42,49
 for bar in range(33):
  s=sec(bar);base=bar*BAR
  if s=="Intimate":continue
  if s=="Bloom":
   if bar in (8,10,12):n.append(Note(base,170,T1,vv(43,r),9))
  elif s=="Lift":
   for b in (0,2):n.append(Note(base+b*PPQ,110,K,vv(57,r),9))
   if bar>=18:
    for t in range(0,BAR,PPQ):n.append(Note(base+t,55,HH,vv(33,r),9))
  elif s=="Crescendo":
   for b in (0,2,3):n.append(Note(base+b*PPQ,115,K,vv(69,r,4),9))
   for b in (1,3):n.append(Note(base+b*PPQ,115,S,vv(63,r,3),9))
   for t in range(0,BAR,PPQ//2):n.append(Note(base+t,50,HH,vv(40,r,3),9))
   if bar in (22,26):n.append(Note(base,240,CR,vv(70,r),9))
  else:
   for b in (0,1,2,3):n.append(Note(base+b*PPQ,120,K,vv(79,r,4),9))
   for b in (1,3):n.append(Note(base+b*PPQ,120,S,vv(72,r,3),9))
   for t in range(0,BAR,PPQ//2):n.append(Note(base+t,50,HH,vv(47,r,3),9))
   if bar==29:n.append(Note(base,280,CR,82,9))
   if bar in (30,32):
    for i,p in enumerate((T1,T1,T2,T2)):n.append(Note(base+3*PPQ+i*PPQ//4,80,p,64+i*3,9))
 return n

def brass(r):
 n=[]
 for bar in range(22,33):
  s=sec(bar);_,ch=PROG[bar%8]
  # phrase punctuation rather than continuous block chords
  if bar%2==0 or s=="Peak":
   for p in (ch[0],ch[2],ch[1]+12):
    n.append(Note(bar*BAR,int((1.55 if s=="Crescendo" else 1.8)*PPQ),p,vv(55 if s=="Crescendo" else 68,r,3)))
 return n

def generate(folder:Path):
 r=random.Random(SEED);folder.mkdir(parents=True,exist_ok=True)
 roles=[("piano",0,0,piano(r)),("theme",73,0,theme(r)),("strings",48,0,strings(r)),("cello_bass",42,0,cello(r)),("ostinato",48,0,ostinato(r)),("percussion",0,9,percussion(r)),("brass",61,0,brass(r))]
 out={}
 for i,(role,program,ch,notes) in enumerate(roles,1):
  p=folder/f"{i:02d}_{role}.mid";p.write_bytes(midi(notes,program,ch));out[role]={"path":str(p),"notes":len(notes)}
 return out
