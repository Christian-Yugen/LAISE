from __future__ import annotations
import json, sys, hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
COMP=ROOT/"backend"/"composition"
if str(COMP) not in sys.path:sys.path.insert(0,str(COMP))

from phrase_engine import PhraseEngine
from motif_development import MotifDeveloper
from voice_interaction import VoiceInteractionEngine
from expressive_timing import ExpressiveTiming

OUT=ROOT/"evidence"/"T006"
OUT.mkdir(parents=True,exist_ok=True)
RESULT=OUT/"t006_phrase_engine_result.json"

SEED=20260924
MOTIF=[0,2,4,2,1,0,-2,1]

def main():
 print("="*78)
 print("LAISE — T006 | Musical Intelligence / Phrase Engine v0.1")
 print("="*78)

 pe=PhraseEngine(SEED)
 md=MotifDeveloper()
 vi=VoiceInteractionEngine()
 ex=ExpressiveTiming(SEED)

 arc=pe.make_arc(MOTIF)
 transformed={
   "transpose_up_2":md.transpose(MOTIF,2),
   "inversion":md.invert(MOTIF),
   "sequence_fragment":md.sequence(md.fragment(MOTIF,4),(0,2,4)),
   "answer":md.answer(MOTIF),
 }
 phrase_data=[]
 for p in arc:
  pd=p.to_dict()
  pd["roles"]=[x.__dict__ for x in vi.instructions(p.function)]
  pd["expressive_events"]=[]
  for i,n in enumerate(p.notes):
   pd["expressive_events"].append({
     "beat":n.beat,
     "timing_offset_ticks":ex.timing_offset_ticks(n.beat,p.bars*4,n.articulation),
     "duration_factor":ex.duration_factor(n.articulation),
     "dynamic_velocity":ex.dynamic_arch(i,len(p.notes),p.notes[0].velocity,p.notes[-1].velocity)
   })
  phrase_data.append(pd)

 funcs=[p.function for p in arc]
 checks={
   "four_phrase_functions":funcs==["statement","response","development","resolution"],
   "development_has_more_events":len(arc[2].notes)>len(arc[0].notes),
   "development_increases_tension":arc[2].tension_end>arc[0].tension_end,
   "resolution_reduces_tension":arc[3].tension_end<arc[2].tension_end,
   "motif_transformations_distinct":len({tuple(v) for v in transformed.values()})==4,
   "voice_roles_change_by_phrase":len({tuple(x.role for x in vi.instructions(f)) for f in funcs})>1,
   "expressive_timing_nonzero":any(abs(e["timing_offset_ticks"])>0 for p in phrase_data for e in p["expressive_events"]),
   "articulation_changes_duration":any(abs(e["duration_factor"]-1)>1e-6 for p in phrase_data for e in p["expressive_events"]),
 }
 status="PASS" if all(checks.values()) else "FAIL"
 payload={
   "test":"T006",
   "engine":"LAISE Musical Intelligence / Phrase Engine v0.1",
   "seed":SEED,
   "motif":MOTIF,
   "transformations":transformed,
   "phrases":phrase_data,
   "checks":checks,
   "objective_result":status,
   "next_gate":"MUSIC-004 integration/perceptual comparison"
 }
 raw=json.dumps(payload,indent=2,ensure_ascii=False)
 RESULT.write_text(raw,encoding="utf-8")
 digest=hashlib.sha256(RESULT.read_bytes()).hexdigest()

 print("\nPHRASE ARC")
 for p in arc:
  roles=", ".join(x.role for x in vi.instructions(p.function))
  print(f"{p.phrase_id:<4} {p.function:<12} notes={len(p.notes):<2} tension={p.tension_start:.2f}->{p.tension_end:.2f} roles=[{roles}]")
 print("\nAUTOMATED VALIDATION")
 for k,v in checks.items():print(f"{k:<48}{'PASS' if v else 'FAIL'}")
 print("\nT006 OBJECTIVE RESULT:",status)
 print("Evidence:",RESULT)
 print("SHA256:",digest)

if __name__=="__main__":main()
