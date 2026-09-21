from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import random,struct
PPQ=480; BPM=88; SEED=20260922; BAR=PPQ*4
SECTIONS=[("Reflection",0,7),("Determination",7,15),("Triumph",15,27),("Release",27,33),("Finale",33,36)]
PROG=[("Bm7",(47,50,54,57)),("Gmaj7",(43,47,50,54)),("Dadd9",(50,54,57,64)),("A",(45,49,52,57)),("Em7",(52,55,59,62)),("G",(43,47,50,55)),("D/F#",(42,50,54,57)),("AsusA",(45,50,52,57))]
SCALE=[54,55,57,59,61,62,64,66,67,69,71,73,74,76,78]
@dataclass
class Note: start:int; duration:int; pitch:int; velocity:int; channel:int=0
def vlq(n):
 b=[n&127];n>>=7
 while n:b.append((n&127)|128);n>>=7
 return bytes(reversed(b))
def midi(notes,program,channel):
 tempo=round(60000000/BPM);ev=[(0,0,b"\xff\x51\x03"+tempo.to_bytes(3,"big")),(0,1,bytes([0xC0|channel,program]))]
 for n in notes:ev += [(n.start,2,bytes([0x90|n.channel,n.pitch,n.velocity])),(n.start+n.duration,1,bytes([0x80|n.channel,n.pitch,0]))]
 ev.sort(key=lambda x:(x[0],x[1]));tr=bytearray();last=0
 for t,_,d in ev:tr+=vlq(t-last)+d;last=t
 tr+=b"\x00\xff\x2f\x00"
 return b"MThd"+struct.pack(">IHHH",6,0,1,PPQ)+b"MTrk"+struct.pack(">I",len(tr))+tr
def sec(bar):
 for name,a,b in SECTIONS:
  if a<=bar<b:return name
 return "Finale"
def vv(x,r,j=3):return max(1,min(127,x+r.randint(-j,j)))
def piano(r):
 n=[]
 for bar in range(36):
  s=sec(bar);_,ch=PROG[bar%8];tones=[ch[0],ch[2],ch[1]+12,ch[3]+12]
  pat={"Reflection":[0,1,2,1],"Determination":[0,2,1,3,2,1],"Triumph":[0,2,1,3,2,1,3,2],"Release":[0,1,2,1],"Finale":[0,1,2,1]}[s]
  step=BAR//len(pat);v={"Reflection":49,"Determination":55,"Triumph":61,"Release":48,"Finale":43}[s]
  for i,k in enumerate(pat):n.append(Note(bar*BAR+i*step,int(step*.72),tones[k],vv(v,r)))
 return n
def pads(r):
 n=[]
 for bar in range(36):
  s=sec(bar);_,ch=PROG[bar%8]
  if s=="Triumph" and bar%2:continue
  v={"Reflection":27,"Determination":31,"Triumph":35,"Release":25,"Finale":21}[s]
  for p in (ch[0]+12,ch[2]+12):n.append(Note(bar*BAR,BAR-50,p,vv(v,r,2)))
 return n
def strings(r):
 n=[]
 for bar in range(36):
  s=sec(bar)
  if s=="Reflection" and bar<3:continue
  _,ch=PROG[bar%8];ps=[ch[0],ch[2],ch[1]+12,ch[3]+12]
  if s=="Reflection":ps=ps[1:3]
  if s=="Triumph":ps+=[ch[2]+12]
  v={"Reflection":34,"Determination":48,"Triumph":67,"Release":45,"Finale":32}[s]
  for p in ps:n.append(Note(bar*BAR,BAR-35,p,vv(v,r)))
 return n
def bass(r):
 roots={"Bm7":35,"Gmaj7":31,"Dadd9":38,"A":33,"Em7":40,"G":31,"D/F#":30,"AsusA":33};n=[]
 for bar in range(36):
  s=sec(bar)
  if s=="Reflection" and bar<4:continue
  name,_=PROG[bar%8];root=roots[name]
  pat={"Reflection":[(0,3.4,root)],"Determination":[(0,1.8,root),(2,1.6,root+7)],"Triumph":[(0,.85,root),(1,.85,root+7),(2,.85,root+12),(3,.85,root+7)],"Release":[(0,1.8,root),(2,1.6,root+7)],"Finale":[(0,3.4,root)]}[s]
  for b,d,p in pat:n.append(Note(bar*BAR+int(b*PPQ),int(d*PPQ),p,vv(73 if s=="Triumph" else 61,r,4)))
 return n
def percussion(r):
 n=[];K,S,T1,T2,HH,CR=36,38,45,47,42,49
 for bar in range(36):
  s=sec(bar);base=bar*BAR
  if s=="Reflection":
   if bar in (5,6):n.append(Note(base,180,T1,vv(40,r),9))
  elif s=="Determination":
   for b in (0,2):n.append(Note(base+b*PPQ,120,K,vv(60,r,4),9))
   if bar>=11:
    for t in range(0,BAR,PPQ):n.append(Note(base+t,65,HH,vv(37,r),9))
   if bar in (13,14):n.append(Note(base+3*PPQ,130,T1,vv(54,r),9))
  elif s=="Triumph":
   for b in (0,1,2,3):n.append(Note(base+b*PPQ,120,K,vv(82,r,5),9))
   for b in (1,3):n.append(Note(base+b*PPQ,130,S,vv(76,r,4),9))
   for t in range(0,BAR,PPQ//2):n.append(Note(base+t,55,HH,vv(49,r,4),9))
   if bar%2:
    for i,p in enumerate((T1,T1,T2,T2)):n.append(Note(base+3*PPQ+i*PPQ//4,85,p,vv(64+i*3,r),9))
   if bar in (15,19,23):n.append(Note(base,260,CR,vv(84,r),9))
  elif s=="Release" and bar<30:
   for b in (0,2):n.append(Note(base+b*PPQ,120,K,vv(55,r),9))
 return n
def lead(r):
 n=[];last=66;mot=[0,2,4,7,4,2,0,-2]
 for bar in range(36):
  s=sec(bar)
  if s=="Reflection" and bar<3:continue
  _,ch=PROG[bar%8];count={"Reflection":2,"Determination":4,"Triumph":6,"Release":3,"Finale":2}[s];up=[p+12 for p in ch]
  for i in range(count):
   beat=i*4/count;target=up[(i+bar)%len(up)] if i in (0,count-1) else min(SCALE,key=lambda p:abs(p-(last+mot[(bar+i)%8])))
   while target-last>7:target-=12
   while last-target>7:target+=12
   target=max(62,min(81,target));v={"Reflection":45,"Determination":57,"Triumph":72,"Release":51,"Finale":42}[s]
   n.append(Note(bar*BAR+int(beat*PPQ),int((4/count)*.74*PPQ),target,vv(v,r)));last=target
 return n
def ostinato(r):
 n=[]
 for bar in range(36):
  s=sec(bar)
  if s not in ("Determination","Triumph"):continue
  _,ch=PROG[bar%8];tones=[ch[0]+12,ch[2]+12,ch[1]+12,ch[2]+12];div=4 if s=="Determination" else 8;step=BAR//div;v=39 if s=="Determination" else 57
  for i in range(div):n.append(Note(bar*BAR+i*step,int(step*.52),tones[i%4],vv(v,r,2)))
 return n
def brass(r):
 n=[]
 for bar in range(15,27):
  _,ch=PROG[bar%8]
  for beat in ([0] if bar<19 else [0,2]):
   for p in (ch[0],ch[2],ch[1]+12):n.append(Note(bar*BAR+beat*PPQ,int(1.75*PPQ),p,vv(64 if bar<19 else 75,r,4)))
 return n
def generate(folder:Path):
 r=random.Random(SEED);folder.mkdir(parents=True,exist_ok=True)
 roles=[("piano",0,0,piano(r)),("soft_synth",89,0,pads(r)),("strings",48,0,strings(r)),("bass",38,0,bass(r)),("percussion",0,9,percussion(r)),("lead",81,0,lead(r)),("ostinato",48,0,ostinato(r)),("brass",61,0,brass(r))]
 out={}
 for i,(role,program,ch,notes) in enumerate(roles,1):
  p=folder/f"{i:02d}_{role}.mid";p.write_bytes(midi(notes,program,ch));out[role]={"path":str(p),"notes":len(notes)}
 return out
