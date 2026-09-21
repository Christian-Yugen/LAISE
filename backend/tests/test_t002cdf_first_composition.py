from __future__ import annotations
import hashlib,json,math,struct,subprocess,sys,wave
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"backend"/"composition"))
from composer import DEFAULT_BPM,DEFAULT_SEED,generate_midi_set
FLUIDSYNTH=ROOT/"tools"/"fluidsynth"/"bin"/"fluidsynth.exe"
SOUNDFONT=ROOT/"assets"/"soundfonts"/"GeneralUser GS v1.471.sf2"
OUT=ROOT/"evidence"/"T002"/"T002-CDF"; MIDI=OUT/"midi"; STEMS=OUT/"stems"; MANIFEST=OUT/"composition_manifest.json"
ROLES=("strings_pad","bass_sub","drums_impacts","lead_melody")

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def metrics(p):
    with wave.open(str(p),"rb") as w:
        ch,sw,sr,n=w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes(); raw=w.readframes(n)
    if sw!=2:raise RuntimeError(f"{p.name}: expected 16-bit PCM")
    s=struct.unpack("<"+"h"*(len(raw)//2),raw); peak=max(abs(x) for x in s)/32768; rms=math.sqrt(sum(float(x)*x for x in s)/len(s))/32768
    return {"channels":ch,"sample_width_bits":sw*8,"sample_rate":sr,"frames":n,"duration_seconds":n/sr,"peak":peak,"peak_dbfs":20*math.log10(max(peak,1e-12)),"rms":rms,"rms_dbfs":20*math.log10(max(rms,1e-12)),"not_silent":rms>1e-5,"no_clipping":peak<.999}
def render(mid,wav):
    c=[str(FLUIDSYNTH),"-ni","-g","0.8","-r","48000","-F",str(wav),str(SOUNDFONT),str(mid)]
    r=subprocess.run(c,cwd=str(ROOT),capture_output=True,text=True)
    if r.returncode:raise RuntimeError("FluidSynth failed\n"+r.stdout+"\n"+r.stderr)

def main():
    print("="*78);print("LAISE — T002-C/D/F | Procedural Composition Engine v0.1");print("="*78)
    if not FLUIDSYNTH.is_file():raise FileNotFoundError(FLUIDSYNTH)
    if not SOUNDFONT.is_file():raise FileNotFoundError(SOUNDFONT)
    MIDI.mkdir(parents=True,exist_ok=True);STEMS.mkdir(parents=True,exist_ok=True)
    for p in list(MIDI.glob("*.mid"))+list(STEMS.glob("*.wav")):p.unlink()
    g=generate_midi_set(MIDI,DEFAULT_SEED,DEFAULT_BPM); plan=g["plan"]; art={}
    print(f"Seed {plan['seed']} | {plan['bpm']} BPM | A natural minor | {plan['bars']} bars | {plan['duration_seconds']:.2f}s")
    print("Structure: "+" -> ".join(x["name"] for x in plan["sections"]))
    for role in ROLES:
        mid=Path(g["midi_files"][role]); wav=STEMS/(mid.stem+"_dry.wav"); print("Rendering",role,"...");render(mid,wav);m=metrics(wav)
        art[role]={"note_count":g["note_counts"][role],"midi":{"path":str(mid),"sha256":sha(mid)},"dry_wav":{"path":str(wav),"sha256":sha(wav),"metrics":m}}
        print(f"  notes={g['note_counts'][role]} duration={m['duration_seconds']:.3f}s peak={m['peak_dbfs']:.2f}dBFS rms={m['rms_dbfs']:.2f}dBFS")
    ds=[art[r]["dry_wav"]["metrics"]["duration_seconds"] for r in ROLES]
    val={"four_midi_files":len(list(MIDI.glob("*.mid")))==4,"four_dry_stems":len(list(STEMS.glob("*.wav")))==4,"all_48khz":all(art[r]["dry_wav"]["metrics"]["sample_rate"]==48000 for r in ROLES),"all_stereo":all(art[r]["dry_wav"]["metrics"]["channels"]==2 for r in ROLES),"all_non_silent":all(art[r]["dry_wav"]["metrics"]["not_silent"] for r in ROLES),"no_clipping":all(art[r]["dry_wav"]["metrics"]["no_clipping"] for r in ROLES),"duration_consistent":max(ds)-min(ds)<6,"distinct_midi_hashes":len({art[r]["midi"]["sha256"] for r in ROLES})==4}
    result="PASS" if all(val.values()) else "FAIL"
    manifest={"work_id":"LAISE-T002-CDF-0001","test_id":"T002-C/D/F","engine":"LAISE Procedural Composition Engine v0.1","created_utc":datetime.now(timezone.utc).isoformat(),"result":result,"composition":plan,"roles":list(ROLES),"synthesis":{"engine":"FluidSynth","sample_rate":48000,"soundfont":{"path":str(SOUNDFONT),"sha256":sha(SOUNDFONT),"status":"TEST_ONLY"}},"artifacts":art,"validations":val,"next_stage":"T003 Spatial Composer"}
    MANIFEST.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    print("\nAUTOMATED VALIDATION")
    for k,v in val.items():print(f"{k:<36}{'PASS' if v else 'FAIL'}")
    print("\nT002-C/D/F RESULT:",result);print("MIDI:",MIDI);print("STEMS:",STEMS);print("MANIFEST:",MANIFEST)
    print("\nAgora ouça separadamente os 4 dry stems. Eles ainda NÃO têm espacialização.")
if __name__=="__main__":main()
