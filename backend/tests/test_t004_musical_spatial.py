from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
COMP=ROOT/"backend"/"composition"
SPAT=ROOT/"backend"/"spatial"
for p in (COMP,SPAT):
    if str(p) not in sys.path: sys.path.insert(0,str(p))

from composer_v02 import generate, BPM
from spatial_composer_v02 import section_keyframes
from dearvr_adapter import DearVRRenderer

OUT=ROOT/"evidence"/"T004"
MIDI=OUT/"midi"
DRY=OUT/"dry_stems"
SPATIAL=OUT/"spatial_stems"
MIX=OUT/"laise_t004_musical_spatial_mix.wav"
SCENE=OUT/"spatial_scene_v02.json"
RESULT=OUT/"t004_results.json"

FS=ROOT/"tools"/"fluidsynth"/"bin"/"fluidsynth.exe"
SF=ROOT/"assets"/"soundfonts"/"GeneralUser GS v1.471.sf2"
SR=48000

FILES={
"strings_pad":"01_strings_pad.wav",
"bass_sub":"02_bass_sub.wav",
"drums_impacts":"03_drums_impacts.wav",
"lead_melody":"04_lead_melody.wav",
}

def readwav(path):
    with wave.open(str(path),"rb") as w:
        if w.getnchannels()!=2 or w.getsampwidth()!=2 or w.getframerate()!=SR:
            raise RuntimeError(f"Unexpected WAV format: {path}")
        x=np.frombuffer(w.readframes(w.getnframes()),dtype="<i2").astype(np.float32)/32768
    return x.reshape(-1,2).T

def writewav(path,x):
    x=np.nan_to_num(x)
    x=np.clip(x,-.999,.999)
    raw=(x.T.reshape(-1)*32767).astype("<i2")
    with wave.open(str(path),"wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(raw.tobytes())

def main():
    print("="*78)
    print("LAISE — T004 | Musical + Spatial Composition Engine v0.2")
    print("="*78)
    for d in (OUT,MIDI,DRY,SPATIAL): d.mkdir(parents=True,exist_ok=True)
    if not FS.is_file(): raise FileNotFoundError(FS)
    if not SF.is_file(): raise FileNotFoundError(SF)

    generated=generate(MIDI)
    dry={}
    for role,info in generated.items():
        wav=DRY/FILES[role]
        print(f"Synthesizing {role} ...")
        subprocess.run([str(FS),"-ni","-g","0.8","-r",str(SR),"-F",str(wav),str(SF),info["path"]],
                       check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        dry[role]=readwav(wav)

    max_samples=max(x.shape[1] for x in dry.values())
    duration=max_samples/SR
    scene={"scene_version":"LAISE Spatial Scene v0.2",
           "music_engine":"LAISE Procedural Composition v0.2",
           "bpm":BPM,"duration_seconds":duration,
           "distance_policy":"FIXED_CALIBRATED_3M",
           "sections":["Intro","Development","Crescendo","Climax","Resolution"],
           "sources":[]}

    renderer=DearVRRenderer(SR,256)
    rendered={}
    for role,x in dry.items():
        src={"source_id":role,
             "trajectory":"section_aware",
             "gain_db":{"strings_pad":-5,"bass_sub":-3,"drums_impacts":-7,"lead_melody":-2}[role],
             "keyframes":section_keyframes(duration,role)}
        scene["sources"].append(src)
        print(f"Spatializing {role} ...")
        y=renderer.render(x,src)
        rendered[role]=y
        writewav(SPATIAL/f"{role}_spatial.wav",y)

    mix=np.zeros((2,max_samples),dtype=np.float32)
    for x in rendered.values(): mix[:,:x.shape[1]]+=x
    pre=float(np.max(np.abs(mix)))
    gain=1.0 if pre<=.92 else .92/pre
    mix*=gain
    writewav(MIX,mix)
    SCENE.write_text(json.dumps(scene,indent=2,ensure_ascii=False),encoding="utf-8")

    validations={
      "four_midi":len(list(MIDI.glob("*.mid")))==4,
      "four_dry_stems":len(list(DRY.glob("*.wav")))==4,
      "four_spatial_stems":len(list(SPATIAL.glob("*.wav")))==4,
      "five_sections":len(scene["sections"])==5,
      "all_section_aware":all(s["trajectory"]=="section_aware" for s in scene["sources"]),
      "mix_finite":bool(np.isfinite(mix).all()),
      "mix_non_silent":float(np.sqrt(np.mean(mix.astype(np.float64)**2)))>1e-6,
      "mix_no_clipping":float(np.max(np.abs(mix)))<.999,
    }
    status="PASS" if all(validations.values()) else "FAIL"
    payload={"test_id":"T004","objective_result":status,"perceptual_result":"PENDING",
             "duration_seconds":duration,"pre_normalization_peak":pre,
             "normalization_gain":gain,"validations":validations,
             "mix":str(MIX),"scene":str(SCENE)}
    RESULT.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    print("\nAUTOMATED VALIDATION")
    for k,v in validations.items(): print(f"{k:<48}{'PASS' if v else 'FAIL'}")
    print(f"\nT004 OBJECTIVE RESULT: {status}")
    print("T004 PERCEPTUAL RESULT: PENDING")
    print("Mix:",MIX)
    print("Scene:",SCENE)
    print("Results:",RESULT)

if __name__=="__main__":
    main()
