from __future__ import annotations
import hashlib,json,subprocess,sys,wave
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
for d in (ROOT/"backend"/"composition",ROOT/"backend"/"spatial",ROOT/"backend"/"mastering"):
 if str(d) not in sys.path:sys.path.insert(0,str(d))

from music005_narrative_composer import generate,build_harmonic_map,write_midi,BPM,SEED
from music005_spatial import narrative_keyframes
from t008_orchestration import CinematicOrchestrationEngine
from t008_mix_intelligence import MixIntelligence
from t008_depth import depth_profile,apply_depth_tail
from dearvr_adapter import DearVRRenderer

OUT=ROOT/"evidence"/"MUSIC-006";MIDI=OUT/"midi";DRY=OUT/"dry_stems";SP=OUT/"spatial_stems"
MIX=OUT/"LAISE_MUSIC005_T008_AB.wav";MAN=OUT/"generation_manifest.json";SR=48000
FS=ROOT/"tools"/"fluidsynth"/"bin"/"fluidsynth.exe";SF=ROOT/"assets"/"soundfonts"/"GeneralUser GS v1.471.sf2"

def rw(p):
 with wave.open(str(p),"rb") as w:x=np.frombuffer(w.readframes(w.getnframes()),dtype="<i2").astype(np.float32)/32768
 return x.reshape(-1,2).T
def ww(p,x):
 x=np.clip(np.nan_to_num(x),-.999,.999);raw=(x.T.reshape(-1)*32767).astype("<i2")
 with wave.open(str(p),"wb") as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(SR);w.writeframes(raw.tobytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 print("="*78);print("LAISE — MUSIC 006 | MUSIC-005 + T008 A/B");print("="*78)
 for d in (OUT,MIDI,DRY,SP):d.mkdir(parents=True,exist_ok=True)

 roles,meta=generate(MIDI)
 curve,hevents,planner,hbars=build_harmonic_map()
 orch=CinematicOrchestrationEngine()
 # Rebuild note data from frozen MUSIC-005 score, then add only T008 transformations.
 from music005_narrative_composer import piano,make_theme,strings,bass,ostinato,percussion,brass,ExpressiveTiming,random
 r=random.Random(SEED);ex=ExpressiveTiming(SEED,480)
 motif,theme,_=make_theme(ex,planner)
 note_map={"piano":piano(r,ex,planner,hbars),"theme":theme,"strings":strings(r,planner,hbars),
 "bass":bass(r,planner,hbars),"ostinato":ostinato(r,planner,hbars,motif),
 "percussion":percussion(r,planner),"brass":brass(r,planner,hbars)}
 note_map,predrop=orch.apply_predrop(note_map)
 note_map["countermelody"]=orch.countermelody(hbars)
 note_map["brass_attack"]=orch.brass_attack_layer(hbars)
 punct=orch.cinematic_punctuation(hbars,True,True);note_map.update(punct)

 programs={"piano":0,"theme":73,"strings":48,"bass":42,"ostinato":48,"percussion":0,
 "brass":61,"countermelody":40,"brass_attack":61,"braam":61,"ping":0}
 channels={k:(9 if k=="percussion" else 0) for k in note_map}
 for i,(role,notes) in enumerate(note_map.items(),1):
  write_midi(MIDI/f"{i:02d}_{role}.mid",notes,programs[role],channels[role])

 dry={}
 for role in note_map:
  print("Synthesizing",role,"...");p=DRY/f"{role}.wav"
  subprocess.run([str(FS),"-ni","-g","0.8","-r",str(SR),"-F",str(p),str(SF),str(next(MIDI.glob(f"*_{role}.mid")))],
   check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);dry[role]=rw(p)

 n=max(x.shape[1] for x in dry.values());duration=n/SR;renderer=DearVRRenderer(SR,256)
 gains={"piano":-3,"theme":-4.5,"strings":-7,"bass":-5,"ostinato":-10,"percussion":-7.5,
 "brass":-10,"countermelody":-8,"brass_attack":-9,"braam":-11,"ping":-10}
 spatial={}
 for role,x in dry.items():
  print("Spatializing",role,"...")
  frames=narrative_keyframes(duration,role if role in ("piano","theme","strings","bass","ostinato","percussion","brass") else ("theme" if role=="countermelody" else "brass"),planner)
  prof=depth_profile(role)
  for f in frames:f["distance_m"]=prof["distance_m"]
  src={"source_id":role,"trajectory":"T008_depth_hierarchy","gain_db":gains[role],"keyframes":frames}
  y=renderer.render(x,src);y=apply_depth_tail(y,SR,role);spatial[role]=y

 mixai=MixIntelligence(SR);cleanup_frames=0;cleanup_analysis={}
 for role in ("strings","bass","brass"):
  spatial[role],c,diag=mixai.conditional_lowmid_cleanup(spatial[role])
  cleanup_frames+=c
  cleanup_analysis[role]={"processed_frames":c,**diag}
 trigger=spatial["percussion"]
 min_duck=1.0
 for role in ("bass","strings"):
  spatial[role],g=mixai.percussion_duck(spatial[role],trigger);min_duck=min(min_duck,g)

 for role,y in spatial.items():ww(SP/f"{role}_spatial.wav",y)
 mix=np.zeros((2,n),np.float32)
 for y in spatial.values():mix[:,:y.shape[1]]+=y
 mix=mixai.preserve_dynamic_range(mix,.90);ww(MIX,mix)

 checks={"frozen_music005_core_roles":all(k in note_map for k in ("piano","theme","strings","bass","ostinato","percussion","brass")),
 "predrop_created":predrop["silence_beats"]>=1.0,"countermelody_added":len(note_map["countermelody"])>0,
 "brass_attack_layer_added":len(note_map["brass_attack"])>0,"optional_punctuation_added":len(note_map["braam"])+len(note_map["ping"])>0,
 "conditional_lowmid_processing_active":cleanup_frames>0,"percussion_ducking_active":min_duck<.999,
 "three_depth_planes":len({depth_profile(k)["distance_m"] for k in note_map})>=3,
 "mix_finite":bool(np.isfinite(mix).all()),"mix_non_silent":float(np.sqrt(np.mean(mix.astype(np.float64)**2)))>1e-6,
 "mix_no_clipping":float(np.max(np.abs(mix)))<.999}
 status="PASS" if all(checks.values()) else "FAIL"
 payload={"work_id":"LAISE-MUSIC-006","comparison_basis":"MUSIC-005 thematic/harmonic structure",
 "engine":"T006 + T007 frozen core + T008 Orchestration/Mix Intelligence","seed":SEED,
 "t008":{"predrop":predrop,"lowmid_processed_frames":cleanup_frames,
 "lowmid_analysis":cleanup_analysis,"minimum_duck_gain":min_duck,
 "depth_profiles":{k:depth_profile(k) for k in note_map}},"checks":checks,"objective_result":status,
 "perceptual_result":"PENDING","mix":str(MIX),"mix_sha256":sha(MIX),
 "asset_note":"GeneralUser GS remains TEST_ONLY; developmental A/B render only."}
 MAN.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
 print("\nAUTOMATED VALIDATION")
 for k,v in checks.items():print(f"{k:<48}{'PASS' if v else 'FAIL'}")
 print("\nMUSIC-006 / T008 OBJECTIVE RESULT:",status);print("PERCEPTUAL RESULT: PENDING")
 print("Mix:",MIX);print("SHA256:",sha(MIX))
if __name__=="__main__":main()
