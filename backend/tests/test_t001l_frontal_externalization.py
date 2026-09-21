from __future__ import annotations
import hashlib, json, math, platform, random, wave
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pedalboard
from pedalboard import load_plugin

SAMPLE_RATE=48000; DURATION_SECONDS=5.0; AMPLITUDE=0.10; BUFFER_SIZE=256; SEED=20260920
PROJECT_ROOT=Path(__file__).resolve().parents[2]
PLUGIN_PATH=Path(r"C:\Program Files\Common Files\VST3\dearVR PRO 2.vst3\Contents\x86_64-win\dearVR PRO 2.vst3")
OUTPUT_DIR=PROJECT_ROOT/"evidence"/"T001"/"T001-L"; AUDIO_DIR=OUTPUT_DIR/"audio"; PRIVATE_DIR=OUTPUT_DIR/"PRIVATE"
RESULTS_PATH=OUTPUT_DIR/"t001l_results.json"; KEY_PATH=PRIVATE_DIR/"t001l_blind_key.json"
L1=OUTPUT_DIR/"listener_01_sheet.json"; L2=OUTPUT_DIR/"listener_02_sheet.json"

def fail(m): print("\nFAIL:",m); raise SystemExit(1)
def db_to_raw(v): return (max(-96.,min(24.,v))+96.)/120.
def distance_to_raw(m): return round((max(.1,min(30.,m))-.1)/.1)/299.
def azimuth_to_raw(d): return (max(-180.,min(180.,d))+180.)/360.
def elevation_to_raw(d): return (max(-90.,min(90.,d))+90.)/180.
def set_raw(p,n,v):
    if n not in p.parameters: fail(f"Missing plugin parameter: {n}")
    p.parameters[n].raw_value=float(v)
def get_repr(p,n): return str(p.parameters[n])
def valid_values(p,n):
    try: return list(p.parameters[n].valid_values or [])
    except Exception: return []
def set_discrete(p,n,text):
    vals=[str(v).strip() for v in valid_values(p,n)]
    if text not in vals: fail(f"{text!r} not available for {n}. Available: {vals[:20]}")
    raw=0. if len(vals)==1 else vals.index(text)/(len(vals)-1)
    set_raw(p,n,raw); return raw
def write_wav(path,a,sr):
    a=np.clip(np.asarray(a,dtype=np.float32),-1,1); pcm=(a.T*32767).astype(np.int16)
    with wave.open(str(path),"wb") as w:
        w.setnchannels(a.shape[0]); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())
def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()
def metrics(a):
    l,r=a[0],a[1]; peak=float(np.max(np.abs(a)))
    lr=float(np.sqrt(np.mean(l*l))); rr=float(np.sqrt(np.mean(r*r))); rms=float(np.sqrt(np.mean(a*a))); e=1e-12
    return {"peak":peak,"overall_rms":rms,"left_rms":lr,"right_rms":rr,
            "ild_db":float(20*math.log10((lr+e)/(rr+e))),
            "lr_correlation":float(np.corrcoef(l,r)[0,1]),
            "finite":bool(np.all(np.isfinite(a))),"no_clipping":bool(peak<1)}
def stimulus():
    n=int(SAMPLE_RATE*DURATION_SECONDS); rng=np.random.default_rng(SEED)
    x=rng.normal(0,1,n).astype(np.float32); x/=max(np.max(np.abs(x)),1e-12); x*=AMPLITUDE
    return np.vstack([x,x]).astype(np.float32)
def geometry(p,az,dist):
    set_raw(p,"coordinate_system",1.0); set_raw(p,"azimuth",azimuth_to_raw(az))
    set_raw(p,"elevation",elevation_to_raw(0)); set_raw(p,"distance",distance_to_raw(dist))
    set_raw(p,"occlusion",0); set_raw(p,"performance_mode",0)
def render_single(inp,az,dist,va="DirectSignal",reflection=False,reverb=False,reflection_gain_db=None):
    p=load_plugin(str(PLUGIN_PATH)); geometry(p,az,dist); ar=set_discrete(p,"virtual_acoustics",va)
    set_raw(p,"reflection",1 if reflection else 0); set_raw(p,"reverb",1 if reverb else 0)
    if reflection_gain_db is not None: set_raw(p,"reflection_gain",db_to_raw(reflection_gain_db))
    out=np.asarray(p.process(inp,sample_rate=SAMPLE_RATE,buffer_size=BUFFER_SIZE,reset=True),dtype=np.float32)
    if out.ndim!=2 or out.shape[0]!=2: fail(f"Expected stereo output, got {out.shape}")
    state={n:get_repr(p,n) for n in ["coordinate_system","azimuth","elevation","distance","virtual_acoustics","reflection","reverb","reflection_gain"]}
    state["virtual_acoustics_raw"]=ar
    return out,state
def render_bilateral(inp,angle,dist=3.0):
    a,sa=render_single(inp,-angle,dist); b,sb=render_single(inp,+angle,dist)
    return (0.5*a+0.5*b).astype(np.float32),{"type":"bilateral_symmetric_sum","angle_deg":angle,"branch_gain_linear":0.5,"left_branch":sa,"right_branch":sb}

CANDIDATES=[
{"id":"FRONT_DIRECT_CONTROL","family":"control","type":"single","az":0.,"dist":3.,"va":"DirectSignal","reflection":False,"reverb":False,"rg":None},
{"id":"FRONT_CLOSE_DIRECT","family":"distance","type":"single","az":0.,"dist":1.,"va":"DirectSignal","reflection":False,"reverb":False,"rg":None},
{"id":"FRONT_FAR_DIRECT","family":"distance","type":"single","az":0.,"dist":6.,"va":"DirectSignal","reflection":False,"reverb":False,"rg":None},
{"id":"FRONT_REFLECTION","family":"acoustics","type":"single","az":0.,"dist":3.,"va":"MediumRecordingHall","reflection":True,"reverb":False,"rg":None},
{"id":"FRONT_REFLECTION_REDUCED","family":"acoustics","type":"single","az":0.,"dist":3.,"va":"MediumRecordingHall","reflection":True,"reverb":False,"rg":-12.},
{"id":"BILATERAL_15","family":"bilateral","type":"bilateral","angle":15.,"dist":3.},
{"id":"BILATERAL_30","family":"bilateral","type":"bilateral","angle":30.,"dist":3.},
{"id":"BILATERAL_45","family":"bilateral","type":"bilateral","angle":45.,"dist":3.},
]

print("\n"+"="*78+"\nLAISE — T001-L\nFrontal Externalization Calibration\n"+"="*78)
print("Python:    ",platform.python_version()); print("Pedalboard:",pedalboard.__version__); print("Plugin:    ",PLUGIN_PATH)
if not PLUGIN_PATH.is_file(): fail(f"Plugin not found:\n{PLUGIN_PATH}")
for d in [OUTPUT_DIR,AUDIO_DIR,PRIVATE_DIR]: d.mkdir(parents=True,exist_ok=True)
inp=stimulus(); print("\nInput shape:",inp.shape); print("Input peak: ",f"{np.max(np.abs(inp)):.8f}")

ids=list("ABCDEFGH"); rng=random.Random(SEED+1200); shuffled=CANDIDATES.copy(); rng.shuffle(shuffled); mapping=dict(zip(ids,shuffled))
records=[]
print("\n"+"-"*78+"\nRENDERING BLIND FRONTAL-EXTERNALIZATION CANDIDATES\n"+"-"*78)
for bid in ids:
    c=mapping[bid]; print(f"\nRendering candidate {bid}")
    if c["type"]=="single":
        out,state=render_single(inp,c["az"],c["dist"],c["va"],c["reflection"],c["reverb"],c["rg"])
    else: out,state=render_bilateral(inp,c["angle"],c["dist"])
    m=metrics(out); path=AUDIO_DIR/f"t001l_{bid}.wav"; write_wav(path,out,SAMPLE_RATE)
    records.append({"blind_id":bid,"wav":str(path),"sha256":sha256(path),"metrics":m,"observed_plugin_state":state})
    print("  peak:       ",f"{m['peak']:.8f}"); print("  RMS:        ",f"{m['overall_rms']:.8f}")
    print("  ILD L/R:    ",f"{m['ild_db']:+.4f} dB"); print("  correlation:",f"{m['lr_correlation']:+.6f}")
    print("  finite:     ","PASS" if m["finite"] else "FAIL"); print("  no clipping:","PASS" if m["no_clipping"] else "FAIL")

hashes=[r["sha256"] for r in records]
checks={"plugin_exists":PLUGIN_PATH.is_file(),"eight_audio_files_created":len(records)==8,
"all_outputs_finite":all(r["metrics"]["finite"] for r in records),
"all_outputs_non_silent":all(r["metrics"]["overall_rms"]>1e-7 for r in records),
"no_clipping":all(r["metrics"]["no_clipping"] for r in records),
"all_outputs_distinct":len(set(hashes))==8}
print("\n"+"-"*78+"\nVALIDATIONS\n"+"-"*78)
for n,v in checks.items(): print(f"{n:<46}{'PASS' if v else 'FAIL'}")

with KEY_PATH.open("w",encoding="utf-8") as f:
    json.dump({"WARNING":"DO NOT OPEN BEFORE BOTH LISTENERS COMPLETE T001-L.","seed":SEED+1200,"mapping":mapping},f,indent=2,ensure_ascii=False)

instructions=["Use the same headphones and normal L/R orientation.","Do not open PRIVATE/t001l_blind_key.json.",
"Do not discuss ratings with the other listener until both finish.",
"Rate perception, not what you think FRONT should sound like.",
"Externalization: 0=inside head; 5=convincingly outside and in front.",
"Centrality: 0=clearly lateral; 5=perfectly centered."]
def sheet(listener):
    return {"test_id":"T001-L","listener_id":listener,"instructions":instructions,
    "samples":[{"blind_id":i,"file":f"audio/t001l_{i}.wav","externalization_0_to_5":None,
    "centrality_0_to_5":None,"perceived_position":None,"confidence_0_to_5":None,"notes":None} for i in ids]}
for path,lid in [(L1,"listener_01"),(L2,"listener_02")]:
    with path.open("w",encoding="utf-8") as f: json.dump(sheet(lid),f,indent=2,ensure_ascii=False)

ok=all(checks.values())
with RESULTS_PATH.open("w",encoding="utf-8") as f:
    json.dump({"test_id":"T001-L","timestamp_utc":datetime.now(timezone.utc).isoformat(),
    "objective_result":"PASS" if ok else "FAIL","perceptual_result":"PENDING",
    "environment":{"python":platform.python_version(),"pedalboard":pedalboard.__version__,"sample_rate":SAMPLE_RATE,
    "buffer_size":BUFFER_SIZE,"duration_seconds":DURATION_SECONDS,"seed":SEED},
    "render_records":records,"validations":checks,"listener_01_sheet":str(L1),"listener_02_sheet":str(L2),
    "blind_key_file":str(KEY_PATH)},f,indent=2,ensure_ascii=False)

print("\n"+"="*78); print("T001-L OBJECTIVE RESULT:","PASS" if ok else "FAIL"); print("T001-L PERCEPTUAL RESULT: PENDING"); print("="*78)
print("\nBLIND AUDIO:"); [print(f"  t001l_{i}.wav") for i in ids]
print("\nListener 01 sheet:\n",L1); print("\nListener 02 sheet:\n",L2)
print("\nDO NOT OPEN BEFORE BOTH LISTENERS FINISH:\n",KEY_PATH); print("\nResults:\n",RESULTS_PATH)
if not ok: raise SystemExit(1)
