from pathlib import Path
import sys,json,random,wave,platform,hashlib
import numpy as np, pedalboard
from pedalboard import load_plugin
ROOT=Path(__file__).resolve().parents[2]; O=ROOT/"backend"/"spatial"/"optimization"; sys.path.insert(0,str(O))
from search_space import build_search_space
from optimizer import score,cluster,select
from acoustic_features import extract_features
from perceptual_dataset import save_sheet
SR=48000; DUR=3; AMP=.1; BUF=256; SEED=20260920
PLUGIN=Path(r"C:\Program Files\Common Files\VST3\dearVR PRO 2.vst3\Contents\x86_64-win\dearVR PRO 2.vst3")
OUT=ROOT/"evidence"/"T001"/"T001-N"; CACHE=OUT/"render_cache"; SHORT=OUT/"blind_finalists"; PRIVATE=OUT/"PRIVATE"
for d in [OUT,CACHE,SHORT,PRIVATE]: d.mkdir(parents=True,exist_ok=True)
def rawaz(x): return (x+180)/360
def rawel(x): return (x+90)/180
def rawdist(x): return round((max(.1,min(30,x))-.1)/.1)/299
def rawdb(x): return (max(-96,min(24,x))+96)/120
def setr(p,n,v): p.parameters[n].raw_value=float(v)
def disc(p,n,t):
    v=[str(x).strip() for x in p.parameters[n].valid_values]; setr(p,n,0 if len(v)==1 else v.index(t)/(len(v)-1))
def stim():
    r=np.random.default_rng(SEED); x=r.normal(0,1,int(SR*DUR)).astype(np.float32); x/=np.max(np.abs(x)); x*=AMP; return np.vstack([x,x])
def render(x,c):
    p=load_plugin(str(PLUGIN)); setr(p,"coordinate_system",1); setr(p,"azimuth",rawaz(c["azimuth_deg"])); setr(p,"elevation",rawel(c["elevation_deg"])); setr(p,"distance",rawdist(c["distance_m"])); setr(p,"occlusion",0); setr(p,"performance_mode",0); disc(p,"virtual_acoustics",c["virtual_acoustics"]); setr(p,"reflection",int(c["reflection"])); setr(p,"reverb",int(c["reverb"]))
    if c["reflection_gain_db"] is not None: setr(p,"reflection_gain",rawdb(c["reflection_gain_db"]))
    return np.asarray(p.process(x,sample_rate=SR,buffer_size=BUF,reset=True),dtype=np.float32)
def wav(path,a):
    pcm=(np.clip(a,-1,1).T*32767).astype(np.int16)
    with wave.open(str(path),"wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print("="*78,"\nLAISE — T001-N | Automated Spatial Search Engine v1.0\n","="*78,sep="")
print("Python:",platform.python_version()," Pedalboard:",pedalboard.__version__); cs=build_search_space(); print("Candidates:",len(cs)); x=stim()
dry=next(c for c in cs if c["family"]=="dry_control" and c["distance_m"]==3); ref=extract_features(render(x,dry),SR); records=[]
for i,c in enumerate(cs,1):
    a=render(x,c); f=extract_features(a,SR); total,ac,h=score(c,f,ref); path=CACHE/f'{c["candidate_id"]}.wav'; wav(path,a); records.append({"candidate":c,"features":f,"combined_score":total,"acoustic_score":ac,"human_prior_score":h,"wav":str(path)})
    if i==1 or i%25==0 or i==len(cs): print(f"{i:03d}/{len(cs)}")
valid=[r for r in records if r["features"]["finite"] and r["features"]["no_clipping"]]; reps=cluster(valid); finals=select(reps); print("Valid:",len(valid)," Cluster reps:",len(reps)," Finalists:",len(finals))
blind=list("ABCDEFGH"); sh=finals.copy(); random.Random(SEED+1400).shuffle(sh); mapping={}
for b,r in zip(blind,sh):
    dst=SHORT/f"t001n_{b}.wav"; dst.write_bytes(Path(r["wav"]).read_bytes()); mapping[b]={k:r[k] for k in ["candidate","features","combined_score","acoustic_score","human_prior_score"]}
(PRIVATE/"t001n_blind_key.json").write_text(json.dumps({"WARNING":"DO NOT OPEN BEFORE HUMAN RATINGS ARE FROZEN.","mapping":mapping},indent=2),encoding="utf-8"); save_sheet(OUT/"listener_sheet.json",blind)
checks={"candidate_count_278":len(cs)==278,"all_valid":len(valid)==278,"cluster_reduction":len(reps)<278,"eight_finalists":len(finals)==8,"unique_pairs":len({(r["candidate"]["distance_m"],r["candidate"]["reflection_gain_db"]) for r in finals})==8}
(OUT/"t001n_results.json").write_text(json.dumps({"validations":checks,"finalists":finals,"top30":sorted(valid,key=lambda r:r["combined_score"],reverse=True)[:30]},indent=2),encoding="utf-8")
print("\nAUTOMATED AUDIT"); [print(f"{k:<30}{'PASS' if v else 'FAIL'}") for k,v in checks.items()]; print("\nT001-N OBJECTIVE RESULT:","PASS" if all(checks.values()) else "FAIL"); print("T001-N HUMAN RESULT: PENDING"); print("Blind finalists:",SHORT)
