from __future__ import annotations
import hashlib,json,subprocess,sys,wave,random
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
for d in (ROOT/"backend"/"composition",ROOT/"backend"/"spatial",ROOT/"backend"/"mastering"):
    if str(d) not in sys.path:
        sys.path.insert(0,str(d))

from music005_narrative_composer import (
    build_harmonic_map, write_midi, piano, make_theme, strings, bass, ostinato,
    percussion, brass, ExpressiveTiming, BPM, SEED, PPQ, BAR
)
from music005_spatial import narrative_keyframes
from t008_orchestration import CinematicOrchestrationEngine
from t008_mix_intelligence import MixIntelligence
from t008_depth import depth_profile,apply_depth_tail
from t009_instrument_realism import InstrumentRealismEngine
from dearvr_adapter import DearVRRenderer

OUT=ROOT/"evidence"/"MUSIC-007"
MIDI=OUT/"midi";DRY=OUT/"dry_stems";SP=OUT/"spatial_stems"
MIX=OUT/"LAISE_MUSIC006_T009_AB.wav"
MAN=OUT/"generation_manifest.json"
PERF=OUT/"performance_manifest.json"
SR=48000
FS=ROOT/"tools"/"fluidsynth"/"bin"/"fluidsynth.exe"
SF=ROOT/"assets"/"soundfonts"/"GeneralUser GS v1.471.sf2"

def readwav(p):
    with wave.open(str(p),"rb") as w:
        x=np.frombuffer(w.readframes(w.getnframes()),dtype="<i2").astype(np.float32)/32768
    return x.reshape(-1,2).T

def writewav(p,x):
    x=np.clip(np.nan_to_num(x),-.999,.999)
    raw=(x.T.reshape(-1)*32767).astype("<i2")
    with wave.open(str(p),"wb") as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(SR);w.writeframes(raw.tobytes())

def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1048576),b""):
            h.update(b)
    return h.hexdigest()

def build_music006_note_map():
    curve,hevents,planner,hbars=build_harmonic_map()
    r=random.Random(SEED)
    ex=ExpressiveTiming(SEED,PPQ)
    motif,theme,_=make_theme(ex,planner)

    note_map={
        "piano":piano(r,ex,planner,hbars),
        "theme":theme,
        "strings":strings(r,planner,hbars),
        "bass":bass(r,planner,hbars),
        "ostinato":ostinato(r,planner,hbars,motif),
        "percussion":percussion(r,planner),
        "brass":brass(r,planner,hbars),
    }

    orch=CinematicOrchestrationEngine(PPQ,40)
    note_map,predrop=orch.apply_predrop(note_map)
    note_map["countermelody"]=orch.countermelody(hbars)
    note_map["brass_attack"]=orch.brass_attack_layer(hbars)
    note_map.update(orch.cinematic_punctuation(hbars,True,True))
    return curve,hevents,planner,hbars,note_map,predrop

def main():
    print("="*78)
    print("LAISE — MUSIC 007 | MUSIC-006 + T009 Instrument Realism A/B")
    print("="*78)

    for d in (OUT,MIDI,DRY,SP):
        d.mkdir(parents=True,exist_ok=True)

    curve,hevents,planner,hbars,note_map,predrop=build_music006_note_map()

    realism=InstrumentRealismEngine(PPQ,BPM,20260928)
    performed,performance_diag=realism.apply(note_map,planner,BAR)

    programs={
        "piano":0,"theme":73,"strings":48,"bass":42,"ostinato":48,
        "percussion":0,"brass":61,"countermelody":40,"brass_attack":61,
        "braam":61,"ping":0
    }
    channels={k:(9 if k=="percussion" else 0) for k in performed}

    for i,(role,notes) in enumerate(performed.items(),1):
        write_midi(MIDI/f"{i:02d}_{role}.mid",notes,programs[role],channels[role])

    dry={}
    for role in performed:
        print("Synthesizing",role,"...")
        p=DRY/f"{role}.wav"
        midi_path=next(MIDI.glob(f"*_{role}.mid"))
        subprocess.run(
            [str(FS),"-ni","-g","0.8","-r",str(SR),"-F",str(p),str(SF),str(midi_path)],
            check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL
        )
        dry[role]=readwav(p)

    n=max(x.shape[1] for x in dry.values())
    duration=n/SR
    renderer=DearVRRenderer(SR,256)
    gains={
        "piano":-3,"theme":-4.5,"strings":-7,"bass":-5,"ostinato":-10,
        "percussion":-7.5,"brass":-10,"countermelody":-8,
        "brass_attack":-9,"braam":-11,"ping":-10
    }

    spatial={}
    for role,x in dry.items():
        print("Spatializing",role,"...")
        base_role=role if role in ("piano","theme","strings","bass","ostinato","percussion","brass") else (
            "theme" if role=="countermelody" else "brass"
        )
        frames=narrative_keyframes(duration,base_role,planner)
        prof=depth_profile(role)
        for f in frames:
            f["distance_m"]=prof["distance_m"]
        src={
            "source_id":role,
            "trajectory":"T008_depth + T009_performance",
            "gain_db":gains[role],
            "keyframes":frames
        }
        y=renderer.render(x,src)
        y=apply_depth_tail(y,SR,role)
        spatial[role]=y

    mixai=MixIntelligence(SR)
    cleanup_frames=0
    cleanup_analysis={}
    for role in ("strings","bass","brass"):
        spatial[role],c,diag=mixai.conditional_lowmid_cleanup(spatial[role])
        cleanup_frames+=c
        cleanup_analysis[role]={"processed_frames":c,**diag}

    trigger=spatial["percussion"]
    min_duck=1.0
    for role in ("bass","strings"):
        spatial[role],g=mixai.percussion_duck(spatial[role],trigger)
        min_duck=min(min_duck,g)

    for role,y in spatial.items():
        writewav(SP/f"{role}_spatial.wav",y)

    mix=np.zeros((2,n),np.float32)
    for y in spatial.values():
        mix[:,:y.shape[1]]+=y
    mix=mixai.preserve_dynamic_range(mix,.90)
    writewav(MIX,mix)

    PERF.write_text(json.dumps({
        "engine":"LAISE T009 Instrument Realism & Articulation Intelligence v0.1",
        "seed":20260928,
        "roles":performance_diag
    },indent=2,ensure_ascii=False),encoding="utf-8")

    timing_changed=sum(x["timing_changes"] for x in performance_diag.values())
    velocity_changed=sum(x["velocity_changes"] for x in performance_diag.values())
    duration_changed=sum(x["duration_changes"] for x in performance_diag.values())
    breaths=sum(x["phrase_breaths"] for x in performance_diag.values())
    families={x["family"] for x in performance_diag.values()}

    checks={
        "music006_core_preserved":all(k in performed for k in (
            "piano","theme","strings","bass","ostinato","percussion","brass",
            "countermelody","brass_attack","braam","ping")),
        "role_specific_articulation_profiles":len(families)>=7,
        "timing_humanization_active":timing_changed>0,
        "velocity_humanization_active":velocity_changed>0,
        "duration_articulation_active":duration_changed>0,
        "phrase_breathing_active":breaths>0,
        "strings_legato_profile_active":performance_diag["strings"]["profile"]["overlap_ms"]>0,
        "brass_attack_short_profile_active":performance_diag["brass_attack"]["profile"]["duration_factor"]<.60,
        "t008_lowmid_cleanup_preserved":cleanup_frames>0,
        "t008_percussion_ducking_preserved":min_duck<.999,
        "three_depth_planes_preserved":len({depth_profile(k)["distance_m"] for k in performed})>=3,
        "mix_finite":bool(np.isfinite(mix).all()),
        "mix_non_silent":float(np.sqrt(np.mean(mix.astype(np.float64)**2)))>1e-6,
        "mix_no_clipping":float(np.max(np.abs(mix)))<.999,
    }
    status="PASS" if all(checks.values()) else "FAIL"

    payload={
        "work_id":"LAISE-MUSIC-007",
        "comparison_basis":"MUSIC-006 frozen composition + T008 mix/orchestration",
        "engine":"T006 + T007 + T008 frozen core + T009 Instrument Realism",
        "seed":20260928,
        "objective_result":status,
        "perceptual_result":"PENDING",
        "t009_summary":{
            "families":sorted(families),
            "timing_changes":timing_changed,
            "velocity_changes":velocity_changed,
            "duration_changes":duration_changed,
            "phrase_breaths":breaths,
            "performance_manifest":str(PERF)
        },
        "t008_preserved":{
            "predrop":predrop,
            "lowmid_processed_frames":cleanup_frames,
            "lowmid_analysis":cleanup_analysis,
            "minimum_duck_gain":min_duck
        },
        "checks":checks,
        "mix":str(MIX),
        "mix_sha256":sha(MIX),
        "asset_note":"GeneralUser GS remains TEST_ONLY; T009 validates performance intelligence, not final production timbre."
    }
    MAN.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")

    print("\nT009 PERFORMANCE SUMMARY")
    print("instrument families:",len(families))
    print("timing changes:",timing_changed)
    print("velocity changes:",velocity_changed)
    print("duration changes:",duration_changed)
    print("phrase breaths:",breaths)

    print("\nAUTOMATED VALIDATION")
    for k,v in checks.items():
        print(f"{k:<48}{'PASS' if v else 'FAIL'}")

    print("\nMUSIC-007 / T009 OBJECTIVE RESULT:",status)
    print("PERCEPTUAL RESULT: PENDING")
    print("Mix:",MIX)
    print("SHA256:",sha(MIX))

if __name__=="__main__":
    main()
