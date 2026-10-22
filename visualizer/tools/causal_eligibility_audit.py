"""Independent artifact audit: never trusts an exported eligibility flag.

Owners are reconstructed from interval intersections at integer microseconds,
then compared with activeIntentIds. This intentionally does not import the
producer's frame_range, source_features or arbitration implementation.
"""
from collections import Counter
import math

def interval_active(intent,frame):
 a,b=(round(intent[k]*1_000_000) for k in ['startTime','endTime'])
 left,right=(round(frame[k]*1_000_000) for k in ['startTime','endTime'])
 return left<=a<right if a==b else a<right and b>left

def audit(result,gestures):
 sources=result['sourceOrder'];lookup={e['intentId']:e for e in result['intents']}
 gs={g['gestureId']:g for g in gestures['gestures']};metrics=Counter({key:0 for key in [
  'inactiveSourceWithArbitrationSalience','inactiveSourceWithRawSalience','inactiveSourceWithFilteredSalience',
  'inactiveSourceWithSupportingRole','inactiveSourceWithSecondaryRole','inactiveSourceWithDominantRole',
  'zeroIntentFramesWithDominant','orphanDominants','activeIntentListMismatch','causalSourceListMismatch']})
 raw_frames=set();role_frames=set();violations=[];dominance_chains=[]
 for index,frame in enumerate(result['frames']):
  actual=[e for e in result['intents'] if interval_active(e,frame)]
  expected_ids={e['intentId'] for e in actual};owners={s:[e for e in actual if e['source']==s] for s in sources}
  if expected_ids!=set(frame['activeIntentIds']):metrics['activeIntentListMismatch']+=1
  if 'causalActiveSources' in frame and set(frame['causalActiveSources'])!={s for s in sources if owners[s]}:metrics['causalSourceListMismatch']+=1
  if not actual and frame['dominantCount']:metrics['zeroIntentFramesWithDominant']+=1
  for j,s in enumerate(sources):
   row=frame['values'][j];raw,filtered,role=row[4],row[5],row[9];owned=bool(owners[s])
   if not owned:
    if raw>0:metrics['inactiveSourceWithRawSalience']+=1;raw_frames.add(index)
    if filtered>0:metrics['inactiveSourceWithFilteredSalience']+=1
    if raw>0 or filtered>0:metrics['inactiveSourceWithArbitrationSalience']+=1
    if role in [1,2,3]:
     metrics[{1:'inactiveSourceWithSupportingRole',2:'inactiveSourceWithSecondaryRole',3:'inactiveSourceWithDominantRole'}[role]]+=1;role_frames.add(index)
    if raw>0 or filtered>0 or role:
     violations.append({'frame':index,'time':frame['startTime'],'source':s,'raw':raw,'filtered':filtered,'roleCode':role})
   if role==3:
    valid=[]
    for e in owners[s]:
     evidence=[gs[gid] for gid in e['gestureRefs'] if gid in gs and gs[gid]['source']==s]
     has_feature=any(g.get('features',{}).get('rms',-1)>=0 and math.isfinite(g.get('features',{}).get('rms',float('nan'))) for g in evidence)
     has_source=s in gestures['sources'] and bool(gestures['sources'][s].get('sha256'))
     has_space=e.get('spatialTrajectoryRef',{}).get('source')==s and bool(gestures['spatialTrajectoryReference'].get('hash'))
     attacks_ok=all(0<=i<len(gestures['attacks']) and gestures['attacks'][i]['source']==s for i in e['attackRefs'])
     if evidence and (has_feature or e['attackRefs']) and has_source and has_space and attacks_ok:valid.append(e['intentId'])
    if not valid:metrics['orphanDominants']+=1
    dominance_chains.append({'frame':index,'time':frame['startTime'],'source':s,'activeIntentIds':valid,'complete':bool(valid)})
 result_metrics=dict(metrics);result_metrics.update({'framesWithInactiveRawSalience':len(raw_frames),'framesWithInactiveNonBackgroundRole':len(role_frames),
  'inactiveNonBackgroundRecords':sum(metrics[k] for k in ['inactiveSourceWithSupportingRole','inactiveSourceWithSecondaryRole','inactiveSourceWithDominantRole'])})
 return {'pass':all(value==0 for value in metrics.values()),'metrics':result_metrics,'frames':len(result['frames']),
         'sourceFrameRows':len(result['frames'])*len(sources),'violations':violations,'dominanceChains':dominance_chains}
