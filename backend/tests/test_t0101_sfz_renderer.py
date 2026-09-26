from __future__ import annotations
import hashlib, json, struct, subprocess, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PIPE = ROOT / "backend" / "asset_pipeline"
if str(PIPE) not in sys.path:
    sys.path.insert(0, str(PIPE))

from renderer_adapter import RenderJob, RendererRouter, SfizzRenderAdapter

OUT = ROOT / "evidence" / "T010.1"
MIDI_DIR = OUT / "midi"
WAV_DIR = OUT / "wav"
RESULT = OUT / "t0101_sfz_renderer_onboarding.json"

SFIZZ_CANDIDATES = [
    ROOT / "tools" / "sfizz" / "bin" / "Release" / "sfizz_render.exe",
    ROOT / "tools" / "sfizz" / "sfizz-1.2.3-win64" / "bin" / "Release" / "sfizz_render.exe",
]
VSCO_ROOT = ROOT / "assets" / "sfz" / "VSCO-2-CE-1.1.0"
SALAMANDER_ROOT = ROOT / "assets" / "sfz" / "SalamanderGrandPiano-master"
PPQ, BPM, SR = 480, 92, 48000


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def vlq(n: int) -> bytes:
    b = [n & 0x7F]
    n >>= 7
    while n:
        b.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(b))


def write_midi(path: Path, notes):
    tempo = round(60_000_000 / BPM)
    events = [(0, 0, b"\xff\x51\x03" + tempo.to_bytes(3, "big"))]
    for start, dur, pitch, vel in notes:
        events.append((start, 2, bytes([0x90, pitch, vel])))
        events.append((start + dur, 1, bytes([0x80, pitch, 0])))
    events.sort(key=lambda x: (x[0], x[1]))
    track = bytearray(); last = 0
    for tick, _, data in events:
        track += vlq(tick - last) + data; last = tick
    track += b"\x00\xff\x2f\x00"
    path.write_bytes(
        b"MThd" + struct.pack(">IHHH", 6, 0, 1, PPQ) +
        b"MTrk" + struct.pack(">I", len(track)) + track
    )


def locate_sfizz():
    for p in SFIZZ_CANDIDATES:
        if p.is_file(): return p
    raise FileNotFoundError("sfizz_render.exe not found in expected LAISE tools paths.")


def locate_salamander():
    exact = SALAMANDER_ROOT / "Salamander Grand Piano V3.sfz"
    if exact.is_file(): return exact
    found = sorted(SALAMANDER_ROOT.rglob("*.sfz"))
    if not found: raise FileNotFoundError("No Salamander SFZ found.")
    return found[0]


def score_vsco_string(path: Path):
    name, parent = path.stem.lower(), str(path.parent).lower()
    score = 0
    if "string" in parent: score += 30
    if "violin" in name: score += 25
    if "string" in name: score += 20
    if "sus" in name or "sustain" in name: score += 18
    if "section" in name or "ensemble" in name: score += 8
    for bad in ("stac", "stacc", "pizz", "trem", "spic", "marc"):
        if bad in name: score -= 25
    return (-score, len(str(path)), str(path).lower())


def locate_vsco_strings():
    if not VSCO_ROOT.is_dir():
        raise FileNotFoundError(f"VSCO root not found: {VSCO_ROOT}")
    candidates = list(VSCO_ROOT.rglob("*.sfz"))
    if not candidates: raise FileNotFoundError("No VSCO SFZ files found.")
    selected = sorted(candidates, key=score_vsco_string)[0]
    n, p = selected.stem.lower(), str(selected.parent).lower()
    if not ("string" in p or "violin" in n or "string" in n):
        raise LookupError("No convincing VSCO strings candidate was identified.")
    return selected


def piano_notes():
    bar = PPQ * 4
    chords = [(48,55,60,64),(45,52,57,60),(41,48,53,57),(43,50,55,59)]
    out=[]
    for bi,chord in enumerate(chords):
        for i,p in enumerate(chord):
            out.append((bi*bar+i*18, int(bar*.88), p, 64+i*3))
    return out


def strings_notes():
    bar = PPQ * 4
    line=[(67,62),(69,65),(71,68),(72,72),(71,70),(69,66),(67,64),(64,60)]
    return [(i*(bar//2), int((bar//2)*1.08), p, v) for i,(p,v) in enumerate(line)]


def parse_wav(path: Path):
    raw = path.read_bytes()
    if len(raw) < 44 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError(f"Invalid WAV: {path}")
    pos=12; fmt=None; data=None
    while pos+8 <= len(raw):
        cid=raw[pos:pos+4]; size=struct.unpack_from("<I",raw,pos+4)[0]
        body=raw[pos+8:pos+8+size]; pos += 8+size+(size&1)
        if cid == b"fmt ": fmt=body
        elif cid == b"data": data=body
    if fmt is None or data is None or len(fmt)<16: raise ValueError("Missing WAV chunks")
    af,ch,sr,_,_,bits = struct.unpack_from("<HHIIHH",fmt,0)
    if af==1 and bits==16:
        s=np.frombuffer(data,dtype="<i2").astype(np.float32)/32768.0
    elif af==1 and bits==24:
        b=np.frombuffer(data,dtype=np.uint8).reshape(-1,3)
        v=(b[:,0].astype(np.int32)|(b[:,1].astype(np.int32)<<8)|(b[:,2].astype(np.int32)<<16))
        v=v-((v&0x800000)<<1); s=v.astype(np.float32)/8388608.0
    elif af==1 and bits==32:
        s=np.frombuffer(data,dtype="<i4").astype(np.float32)/2147483648.0
    elif af==3 and bits==32:
        s=np.frombuffer(data,dtype="<f4").astype(np.float32)
    else:
        raise ValueError(f"Unsupported WAV format={af} bits={bits}")
    frames=len(s)//ch; s=s[:frames*ch].reshape(frames,ch)
    peak=float(np.max(np.abs(s))) if s.size else 0.0
    rms=float(np.sqrt(np.mean(s.astype(np.float64)**2))) if s.size else 0.0
    return {"channels":ch,"sample_rate":sr,"bits_per_sample":bits,"frames":frames,
            "duration_seconds":frames/sr if sr else 0.0,"peak":peak,"rms":rms,
            "finite":bool(np.isfinite(s).all()),"non_silent":rms>1e-7}


def render(adapter, sfz, midi, wav):
    cmd = adapter.command(RenderJob(
        renderer="sfizz_render", asset_path=str(sfz), midi_path=str(midi),
        output_path=str(wav), sample_rate=SR
    ))
    p = subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return {"returncode":p.returncode,"command":cmd,"console_tail":p.stdout[-4000:]}


def main():
    print("="*78)
    print("LAISE — T010.1 | SFZ Production Renderer + Asset Onboarding")
    print("="*78)
    for d in (OUT,MIDI_DIR,WAV_DIR): d.mkdir(parents=True,exist_ok=True)

    sfizz=locate_sfizz(); salamander=locate_salamander(); vsco=locate_vsco_strings()
    RendererRouter.ensure_supported("sfizz_render")
    adapter=SfizzRenderAdapter(sfizz)

    pm=MIDI_DIR/"01_piano_test.mid"; sm=MIDI_DIR/"02_strings_test.mid"
    pw=WAV_DIR/"01_salamander_piano.wav"; sw=WAV_DIR/"02_vsco_strings.wav"
    write_midi(pm,piano_notes()); write_midi(sm,strings_notes())

    print("\nDISCOVERY")
    print("sfizz_render:",sfizz)
    print("Salamander:",salamander)
    print("VSCO strings:",vsco)

    print("\nRENDER")
    print("Rendering Salamander piano ...")
    pr=render(adapter,salamander,pm,pw); print("return code:",pr["returncode"])
    print("Rendering VSCO strings ...")
    srend=render(adapter,vsco,sm,sw); print("return code:",srend["returncode"])

    pa=parse_wav(pw) if pw.is_file() else None
    sa=parse_wav(sw) if sw.is_file() else None

    assets=[
        {"candidate_asset_id":"LAISE-SFZ-PIANO-SALAMANDER-V3","role":"piano",
         "sfz":str(salamander),"sfz_sha256":sha256_file(salamander),"status":"ONBOARDING",
         "production_approved":False},
        {"candidate_asset_id":"LAISE-SFZ-VSCO2CE-STRINGS-001","role":"strings",
         "sfz":str(vsco),"sfz_sha256":sha256_file(vsco),"status":"ONBOARDING",
         "production_approved":False},
    ]
    checks={
        "sfizz_renderer_found":sfizz.is_file(),
        "salamander_sfz_found":salamander.is_file(),
        "vsco_strings_sfz_found":vsco.is_file(),
        "sfizz_piano_render_exit_zero":pr["returncode"]==0,
        "sfizz_strings_render_exit_zero":srend["returncode"]==0,
        "piano_wav_created":pw.is_file(),
        "strings_wav_created":sw.is_file(),
        "piano_48khz":bool(pa and pa["sample_rate"]==SR),
        "strings_48khz":bool(sa and sa["sample_rate"]==SR),
        "piano_non_silent":bool(pa and pa["non_silent"]),
        "strings_non_silent":bool(sa and sa["non_silent"]),
        "piano_finite":bool(pa and pa["finite"]),
        "strings_finite":bool(sa and sa["finite"]),
        "onboarding_not_auto_approved":all(not a["production_approved"] for a in assets),
    }
    status="PASS" if all(checks.values()) else "FAIL"
    payload={
        "test":"T010.1","engine":"LAISE SFZ Production Renderer + Asset Onboarding v0.1",
        "objective_result":status,
        "renderer":{"path":str(sfizz),"sha256":sha256_file(sfizz)},
        "assets":assets,
        "renders":{"piano":{"process":pr,"audio":pa,"wav":str(pw),"wav_sha256":sha256_file(pw) if pw.is_file() else None},
                   "strings":{"process":srend,"audio":sa,"wav":str(sw),"wav_sha256":sha256_file(sw) if sw.is_file() else None}},
        "checks":checks,
        "next_gate":"listen to dry piano/strings, then freeze exact bundle hashes and license evidence"
    }
    RESULT.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    print("\nAUDIO")
    if pa: print(f"piano   | {pa['channels']}ch | {pa['sample_rate']} Hz | {pa['duration_seconds']:.2f}s | RMS={pa['rms']:.6f}")
    if sa: print(f"strings | {sa['channels']}ch | {sa['sample_rate']} Hz | {sa['duration_seconds']:.2f}s | RMS={sa['rms']:.6f}")
    print("\nAUTOMATED VALIDATION")
    for k,v in checks.items(): print(f"{k:<48}{'PASS' if v else 'FAIL'}")
    print("\nT010.1 OBJECTIVE RESULT:",status)
    print("Evidence:",RESULT)
    print("SHA256:",sha256_file(RESULT))

if __name__=="__main__": main()
