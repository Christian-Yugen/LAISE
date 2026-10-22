"""Independent full-track causal and dominance-run evidence for V1.3B-R1."""
from pathlib import Path
import collections,json
from causal_eligibility_audit import audit
V=Path(__file__).resolve().parents[1]
OUT=V/'reports/v1_3br1-causal-eligibility'
def main():
 d=json.loads((V/'public/audio/tukana-musical-visual-intents-v1.json').read_text(encoding='utf-8'))
 a=json.loads((V/'public/audio/tukana-musical-gestures-v1.json').read_text(encoding='utf-8'))
 evidence=audit(d,a)
 (OUT/'causal-after.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
 trace=json.loads((OUT/'arbitration-decisions.json').read_text(encoding='utf-8'))['decisions']
 sets=[tuple(s for s,row in zip(d['sourceOrder'],f['values']) if row[9]==3) for f in d['frames']]
 boundaries=[0]+[i for i in range(1,len(sets)) if sets[i]!=sets[i-1]]+[len(sets)]
 runs=[]
 for lo,hi in zip(boundaries,boundaries[1:]):
  f=d['frames'][lo];t=f['startTime'];decision=trace[lo]
  nearby=[{'source':x['source'],'time':x['time']} for x in a['attacks'] if abs(x['time']-t)<=.05]
  prev=d['frames'][max(0,lo-1)]
  changes=[{'source':s,'rmsBefore':p[0],'rmsAfter':r[0],'salienceBefore':p[5],'salienceAfter':r[5]} for s,p,r in zip(d['sourceOrder'],prev['values'],f['values']) if s in set(sets[lo])|set(sets[max(0,lo-1)])]
  top=max((r[5] for r in f['values']),default=0)
  fractions=[r[5]/top for r in f['values'] if r[5]>0 and top>0]
  near_tie=any(abs(x-(1-d['analysisParameters']['tieFraction']))<=.002 for x in fractions if x<1)
  labels=['50ms-grid-quantized']
  if nearby:labels.append('measured-attack-within-50ms-not-proof-of-musical-importance')
  if len(sets[lo])>1:labels.append('causally-owned-co-dominance-under-existing-tie-hysteresis-rule')
  if decision['strongChangeBypass']:labels.append('strong-change-bypass')
  if decision['inactiveIncumbents']:labels.append('causal-owner-ended')
  if near_tie:labels.append('near-tie-threshold-sensitive')
  runs.append({'startTime':t,'endTime':d['frames'][hi-1]['endTime'],'durationMs':(hi-lo)*50,'dominants':sets[lo],
   'evidenceLabels':labels,'nearTieBoundary002':near_tie,
   'activeIntentIdsAtStart':f['activeIntentIds'],'nearbyMeasuredAttacks':nearby,'boundaryMeasurements':changes,'arbitrationDecision':decision,
   'interpretation':'measured boundary evidence only; 50 ms quantization and threshold/tie sensitivity remain; musical significance requires listening'})
 histogram=collections.Counter(r['durationMs'] for r in runs if r['dominants'])
 result={'pass':evidence['pass'],'runCount':len(runs),'nonemptyRunDurationHistogramMs':dict(sorted(histogram.items())),
  'shortNonemptyRunsAtMost200ms':sum(bool(r['dominants']) and r['durationMs']<=200 for r in runs),
  'strongChangeBypassFrames':sum(bool(x['strongChangeBypass']) for x in trace),
  'tieFrames':sum(len(x['tieCandidates'])>1 for x in trace),
  'shortRunEvidenceCounts':dict(collections.Counter(label for r in runs if r['dominants'] and r['durationMs']<=200 for label in r['evidenceLabels'])),
  'note':'Short runs are not automatically musical changes or errors. No smoothing, hold, thresholds or calibration retuned. Roles are priority annotations, never binary gain switches. visualEnergyCandidate requires perceptual/dynamic calibration before any V1.3C Y mapping.', 'runs':runs}
 (OUT/'dominance-runs.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 assert evidence['pass'],evidence['metrics']
 print(json.dumps({'causal':evidence['metrics'],'runs':len(runs),'histogram':dict(sorted(histogram.items())),'shortRuns':result['shortNonemptyRunsAtMost200ms']},indent=2))
if __name__=='__main__':main()
