from __future__ import annotations
import json, subprocess, sys, wave
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
for d in (ROOT/"backend"/"composition",ROOT/"backend"/"spatial"):
    if str(d) not in sys.path:sys.path.insert(0,str(d))
from cinematic_epic_v01 import generate,BPM,SECTIONS
from cinematic_spatial_v01 import keyframes
from dearvr_adapter import DearVRRenderer

OUT=ROOT/"evidence"/"T005"; MIDI=OUT/"midi"; DRY=OUT/"dry_stems"; SP=OUT/"spatial_stems"
MIX=OUT/"laise_cinematic_epic_v01.wav"; SCENE=OUT/"cinematic_spatial_scene.json"; RES=OUT/"t005_results.json"
FS=ROOT/"tools"/"fluidsynth"/"bin"/"fluidsynth.exe"
SF=ROOT/"assets"/"soundfonts"/"GeneralUser GS v1.471.sf2"; SR=48000

def readwav(p):
    with wave.open(str(p),"rb") as w:
        x=np.frombuffer(w.readframes(w.getnframes()),dtype="<i2").astype(np.float32)/32768
    return x.reshape(-1,2).T
def writewav(p,x):
    x=np.clip(np.nan_to_num(x),-.999,.999)
    raw=(x.T.reshape(-1)*32767).astype("<i2")
    with wave.open(str(p),"wb") as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(SR);w.writeframes(raw.tobytes())

def main():
    print("="*78);print("LAISE — T005 | Cinematic Epic Grammar v0.1");print("="*78)
    for d in (OUT,MIDI,DRY,SP):d.mkdir(parents=True,exist_ok=True)
    roles=generate(MIDI); dry={}
    for role,info in roles.items():
        print("Synthesizing",role,"...")
        p=DRY/f"{role}.wav"
        subprocess.run([str(FS),"-ni","-g","0.8","-r",str(SR),"-F",str(p),str(SF),info["path"]],
                       check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        dry[role]=readwav(p)
    n=max(x.shape[1] for x in dry.values()); duration=n/SR
    gains={"strings":-7,"brass":-9,"bass":-4,"epic_percussion":-6,"lead":-4,"pulse_ostinato":-11}
    renderer=DearVRRenderer(SR,256); spatial={}; sources=[]
    for role,x in dry.items():
        print("Spatializing",role,"...")
        src={"source_id":role,"trajectory":"cinematic_section_aware","gain_db":gains[role],"keyframes":keyframes(duration,role)}
        sources.append(src);y=renderer.render(x,src);spatial[role]=y;writewav(SP/f"{role}_spatial.wav",y)
    mix=np.zeros((2,n),np.float32)
    for x in spatial.values():mix[:,:x.shape[1]]+=x
    peak=float(np.max(np.abs(mix))); gain=1 if peak<=.90 else .90/peak;mix*=gain;writewav(MIX,mix)
    scene={"scene_version":"LAISE Cinematic Spatial v0.1","style":"Cinematic Epic",
           "bpm":BPM,"duration_seconds":duration,"sections":[x[0] for x in SECTIONS],
           "distance_policy":"FIXED_CALIBRATED_3M","sources":sources}
    SCENE.write_text(json.dumps(scene,indent=2,ensure_ascii=False),encoding="utf-8")
    checks={
      "six_midi":len(list(MIDI.glob("*.mid")))==6,
      "six_dry_stems":len(list(DRY.glob("*.wav")))==6,
      "six_spatial_stems":len(list(SP.glob("*.wav")))==6,
      "six_emotional_sections":len(SECTIONS)==6,
      "mix_finite":bool(np.isfinite(mix).all()),
      "mix_non_silent":float(np.sqrt(np.mean(mix.astype(np.float64)**2)))>1e-6,
      "mix_no_clipping":float(np.max(np.abs(mix)))<.999,
    }
    status="PASS" if all(checks.values()) else "FAIL"
    RES.write_text(json.dumps({"test_id":"T005","objective_result":status,"perceptual_result":"PENDING",
       "style":"Cinematic Epic","duration_seconds":duration,"normalization_gain":gain,"checks":checks,
       "mix":str(MIX),"scene":str(SCENE)},indent=2,ensure_ascii=False),encoding="utf-8")
    print("\nAUTOMATED VALIDATION")
    for k,v in checks.items():print(f"{k:<48}{'PASS' if v else 'FAIL'}")
    print("\nT005 OBJECTIVE RESULT:",status);print("T005 PERCEPTUAL RESULT: PENDING")
    print("Mix:",MIX)

if __name__=="__main__":main()
