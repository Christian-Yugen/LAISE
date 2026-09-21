from __future__ import annotations
import hashlib,json,subprocess,sys,wave
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
for d in (ROOT/"backend"/"composition",ROOT/"backend"/"spatial"):
 if str(d) not in sys.path:sys.path.insert(0,str(d))

from music004_phrase_composer import generate,BPM,SEED,SECTIONS
from music004_spatial import keyframes
from dearvr_adapter import DearVRRenderer

OUT=ROOT/"evidence"/"MUSIC-004"
MIDI=OUT/"midi";DRY=OUT/"dry_stems";SP=OUT/"spatial_stems"
MIX=OUT/"LAISE_Phrase_Driven_Cinematic_001.wav"
SCENE=OUT/"spatial_scene.json";MANIFEST=OUT/"generation_manifest.json"
FS=ROOT/"tools"/"fluidsynth"/"bin"/"fluidsynth.exe"
SF=ROOT/"assets"/"soundfonts"/"GeneralUser GS v1.471.sf2"
SR=48000

def readwav(p):
 with wave.open(str(p),"rb") as w:
  x=np.frombuffer(w.readframes(w.getnframes()),dtype="<i2").astype(np.float32)/32768.0
 return x.reshape(-1,2).T

def writewav(p,x):
 x=np.clip(np.nan_to_num(x),-.999,.999)
 raw=(x.T.reshape(-1)*32767).astype("<i2")
 with wave.open(str(p),"wb") as w:
  w.setnchannels(2);w.setsampwidth(2);w.setframerate(SR);w.writeframes(raw.tobytes())

def sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()

def main():
 print("="*78)
 print("LAISE — MUSIC 004 | Phrase-Driven Cinematic v0.1")
 print("="*78)
 for d in (OUT,MIDI,DRY,SP):d.mkdir(parents=True,exist_ok=True)

 roles,musical=generate(MIDI)
 dry={}
 for role,info in roles.items():
  print("Synthesizing",role,"...")
  p=DRY/f"{role}.wav"
  subprocess.run([str(FS),"-ni","-g","0.8","-r",str(SR),"-F",str(p),str(SF),info["path"]],
                 check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  dry[role]=readwav(p)

 n=max(x.shape[1] for x in dry.values());duration=n/SR
 gains={"piano":-3.0,"theme":-4.5,"strings":-7.0,"bass":-5.0,
        "ostinato":-10.0,"percussion":-7.5,"brass":-10.0}
 renderer=DearVRRenderer(SR,256)
 sources=[];spatial={}
 for role,x in dry.items():
  print("Spatializing",role,"...")
  src={"source_id":role,"trajectory":"phrase_supportive",
       "gain_db":gains[role],"keyframes":keyframes(duration,role)}
  sources.append(src)
  y=renderer.render(x,src)
  spatial[role]=y
  writewav(SP/f"{role}_spatial.wav",y)

 mix=np.zeros((2,n),np.float32)
 for x in spatial.values():mix[:,:x.shape[1]]+=x
 peak=float(np.max(np.abs(mix)))
 if peak>.90:mix*=.90/peak
 writewav(MIX,mix)

 scene={"scene_version":"LAISE MUSIC-004 Spatial v0.1","bpm":BPM,
        "duration_seconds":duration,"sections":[x[0] for x in SECTIONS],
        "distance_policy":"FIXED_CALIBRATED_3M","sources":sources}
 SCENE.write_text(json.dumps(scene,indent=2,ensure_ascii=False),encoding="utf-8")

 funcs=[p["function"] for p in musical["phrase_plan"]]
 checks={
  "seven_midi":len(list(MIDI.glob("*.mid")))==7,
  "seven_dry_stems":len(list(DRY.glob("*.wav")))==7,
  "seven_spatial_stems":len(list(SP.glob("*.wav")))==7,
  "five_emotional_sections":len(SECTIONS)==5,
  "phrase_plan_present":len(musical["phrase_plan"])>=8,
  "statement_response_development_resolution":all(x in funcs for x in ("statement","response","development","resolution")),
  "mix_finite":bool(np.isfinite(mix).all()),
  "mix_non_silent":float(np.sqrt(np.mean(mix.astype(np.float64)**2)))>1e-6,
  "mix_no_clipping":float(np.max(np.abs(mix)))<.999,
 }
 status="PASS" if all(checks.values()) else "FAIL"
 manifest={
  "work_id":"LAISE-MUSIC-004",
  "title":"Phrase-Driven Cinematic 001",
  "seed":SEED,
  "engine":"LAISE T006 Phrase Engine + procedural orchestration + spatial",
  "style":"Hopeful Inspirational Cinematic",
  "objective_result":status,
  "perceptual_result":"PENDING",
  "bpm":BPM,"duration_seconds":duration,
  "sections":[x[0] for x in SECTIONS],
  "musical_intelligence":musical,
  "checks":checks,
  "mix":str(MIX),"mix_sha256":sha(MIX),"scene":str(SCENE),
  "asset_note":"Current GeneralUser GS SoundFont remains TEST_ONLY; this render is developmental evidence, not a production rights certification."
 }
 MANIFEST.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")

 print("\nAUTOMATED VALIDATION")
 for k,v in checks.items():print(f"{k:<48}{'PASS' if v else 'FAIL'}")
 print("\nMUSIC-004 OBJECTIVE RESULT:",status)
 print("PERCEPTUAL RESULT: PENDING")
 print("Mix:",MIX)
 print("SHA256:",sha(MIX))

if __name__=="__main__":main()
