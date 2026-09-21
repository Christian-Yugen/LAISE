from __future__ import annotations
import hashlib,json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
COMP=ROOT/"backend"/"composition"
if str(COMP) not in sys.path:sys.path.insert(0,str(COMP))

from emotional_narrative import EmotionalNarrative
from harmonic_narrative import HarmonicNarrativeEngine
from narrative_planner import NarrativePlanner

OUT=ROOT/"evidence"/"T007";OUT.mkdir(parents=True,exist_ok=True)
RESULT=OUT/"t007_harmonic_emotional_narrative.json"
SEED=20260926

def main():
 print("="*78)
 print("LAISE — T007 | Harmonic & Emotional Narrative Engine v0.1")
 print("="*78)

 curve=EmotionalNarrative().hopeful_cinematic(40)
 harmony=HarmonicNarrativeEngine(SEED).compose(curve)
 plan=NarrativePlanner().build(curve)

 tensions=[x["target_tension"] for x in curve]
 phases=[x["phase"] for x in curve]
 chords=[x.chord for x in harmony]
 funcs=[x.function for x in harmony]

 pre_peak=max(tensions[:9])
 final=tensions[-1]

 checks={
   "emotional_curve_present":len(curve)>=10,
   "contains_stability": "stability" in phases,
   "contains_suspension": "suspension" in phases,
   "contains_breakthrough":"breakthrough" in phases,
   "contains_resolution":"resolution" in phases,
   "tension_builds_before_breakthrough":pre_peak>=.80,
   "resolution_reduces_tension":final<=.20,
   "harmony_not_fixed_single_chord":len(set(chords))>=4,
   "functional_harmony_present":len(set(funcs))>=3,
   "planner_maps_phrase_functions":len({x["phrase_function"] for x in plan})>=3,
   "density_tracks_energy":plan[9]["density"]>plan[0]["density"],
   "spatial_width_tracks_energy":plan[9]["spatial_width"]>plan[0]["spatial_width"],
 }
 status="PASS" if all(checks.values()) else "FAIL"

 payload={
   "test":"T007",
   "engine":"LAISE Harmonic & Emotional Narrative Engine v0.1",
   "seed":SEED,
   "emotional_curve":curve,
   "harmonic_events":[x.__dict__ for x in harmony],
   "narrative_plan":plan,
   "checks":checks,
   "objective_result":status,
   "next_gate":"MUSIC-005 integration"
 }
 RESULT.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
 digest=hashlib.sha256(RESULT.read_bytes()).hexdigest()

 print("\nNARRATIVE")
 for p,h,n in zip(curve,harmony,plan):
  print(f"bar {p['bar']:>2} | {p['phase']:<12} | target={p['target_tension']:.2f} "
        f"| {h.chord:<7} {h.function:<20} | phrase={n['phrase_function']}")
 print("\nAUTOMATED VALIDATION")
 for k,v in checks.items():print(f"{k:<48}{'PASS' if v else 'FAIL'}")
 print("\nT007 OBJECTIVE RESULT:",status)
 print("Evidence:",RESULT)
 print("SHA256:",digest)

if __name__=="__main__":main()
