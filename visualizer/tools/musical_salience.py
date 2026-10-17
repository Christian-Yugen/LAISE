"""V1.3B: auditable offline semantic fusion and source-neutral arbitration.

No Three.js dependency, physics, height conversion or runtime consumer.
"""
import math
from collections import Counter
import numpy as np
from musical_gestures import percentiles,canonical

PARAMETERS={'windowSeconds':.05,'weights':{'novelty':.15,'rhythm':.10,'persistence':.10,'isolation':.10},
 'persistenceSeconds':2.,'densityWindowSeconds':.25,'densityReferenceHz':4.,
 'referencePercentile':95,'minimumRms':1e-12,'attackTauSeconds':.04,'releaseTauSeconds':.12,
 'hysteresisRatio':.08,'minimumHoldSeconds':.15,'strongChangeRatio':1.5,'tieFraction':.01,
 'secondaryRatio':.5,'supportingRatio':.1,
 'sensitivityWeightDeltas':[-.2,-.1,.1,.2],
 'sensitivityPass':{'minimumMeanRankCorrelation':.95,'minimumDominantJaccard':.90,'maximumP99RelativeScoreChange':.10}}
SUSTAIN={'SUSTAINED_TONE','SUSTAINED_TEXTURE'}
RHYTHM={'REPEATED_PULSE','REPEATED_PULSE_SEQUENCE','ACCELERATING_SEQUENCE','DECELERATING_SEQUENCE','TREMOLO_OR_ROLL'}
MODIFIERS={'CRESCENDO','DECRESCENDO','CONTINUOUS_MOTION'}
ROLES=['background','supporting','secondary','dominant']

def overlap(a,b):return max(0,min(a['endTime'],b['endTime'])-max(a['startTime'],b['startTime']))
def contains(interval,time):return interval['startTime']-1e-8<=time<=interval['endTime']+1e-8
def intersect(a,b):
 return overlap(a,b)>1e-9 or (a['startTime']==a['endTime'] and contains(b,a['startTime'])) or (b['startTime']==b['endTime'] and contains(a,b['startTime']))

def fuse_gestures(data):
 """Connected PRIMARY intervals only; phrases/modifiers never bridge episodes.

 Every attack has exactly one owner. Context/modifier references may span several
 episodes, with explicit intersections. Different sources are NEVER fused.
 """
 all_intents=[];relations=[];owners=[None]*len(data['attacks'])
 for source in sorted(data['sources']):
  gestures=[g for g in data['gestures'] if g['source']==source]
  seeds=sorted([g for g in gestures if g['gestureType'] in SUSTAIN|RHYTHM|{'IMPULSE'}],key=lambda g:(g['startTime'],g['endTime'],g['gestureId']))
  episodes=[]
  def seed(g):return {'source':source,'startTime':g['startTime'],'endTime':g['endTime'],'seeds':[g]}
  for g in seeds:
   if episodes and g['startTime']<=episodes[-1]['endTime']+1e-8:
    episodes[-1]['endTime']=max(episodes[-1]['endTime'],g['endTime']);episodes[-1]['seeds'].append(g)
   else:episodes.append(seed(g))
  # A modifier with no causal base may be its own evolving hypothesis; no phrase
  # is ever promoted merely for being long or confident.
  for g in gestures:
   if g['gestureType'] in MODIFIERS and not any(intersect(g,e) for e in episodes):episodes.append(seed(g))
  episodes.sort(key=lambda e:(e['startTime'],e['endTime']))
  for a in [a for a in data['attacks'] if a['source']==source]:
   if not any(contains(e,a['time']) for e in episodes):episodes.append({'source':source,'startTime':a['time'],'endTime':a['time'],'seeds':[]})
  episodes.sort(key=lambda e:(e['startTime'],e['endTime']))
  for index,e in enumerate(episodes):
   e['intentId']=f'{source}:i{index:05d}';e['attackRefs']=[]
   candidates=sorted(e.pop('seeds'),key=lambda g:(-g['duration'],-g['intensity'],g['gestureId']))
   primary=candidates[0] if candidates else None;e['primaryGesture']=primary['gestureId'] if primary else None
   e['classificationConfidence']=primary['confidence'] if primary else None
   e['temporalBehavior']='sustained' if primary and primary['gestureType'] in SUSTAIN else 'repeated' if primary and primary['gestureType'] in RHYTHM else 'impulse' if not primary or primary['gestureType']=='IMPULSE' else 'evolving'
   assignments=[]
   for g in gestures:
    if not intersect(g,e):continue
    kind=g['gestureType']
    relation='parent' if g['gestureId']==e['primaryGesture'] else 'context' if kind=='PHRASE' else 'intensityModifier' if kind in {'CRESCENDO','DECRESCENDO'} else 'spatialModifier' if kind=='CONTINUOUS_MOTION' else 'reinforcement' if kind=='IMPULSE' else 'rhythmicModifier' if kind in RHYTHM else 'continuation'
    assignments.append(g['gestureId']);relations.append({'intentId':e['intentId'],'gestureId':g['gestureId'],'relation':relation,
     'startTime':max(e['startTime'],g['startTime']),'endTime':min(e['endTime'],g['endTime'])})
   e['gestureRefs']=sorted(set(assignments));e['intensityTrend']=[g['gestureId'] for g in gestures if g['gestureType'] in {'CRESCENDO','DECRESCENDO'} and g['gestureId'] in e['gestureRefs']]
   e['spatialTrajectoryRef']={'source':source,'reference':'V1.3A.spatialTrajectoryReference/T007.roles','gestureRefs':e['gestureRefs']}
   e['reason']={'rule':'same-source overlapping primary evidence fused; context and modifiers do not spawn duplicate drivers',
                'independentFromOtherSources':True,'confidenceUsedAsIntensity':False}
  for a in [a for a in data['attacks'] if a['source']==source]:
   candidates=[e for e in episodes if contains(e,a['time'])]
   assert candidates,(source,a['index'])
   e=sorted(candidates,key=lambda e:(-(e['endTime']-e['startTime']),e['intentId']))[0]
   e['attackRefs'].append(a['index']);owners[a['index']]=e['intentId']
  for before,after in zip(episodes,episodes[1:]):
   common=set(before['gestureRefs'])&set(after['gestureRefs'])
   if 0<=after['startTime']-before['endTime']<=.25 and common:
    relations.append({'fromIntent':before['intentId'],'toIntent':after['intentId'],'relation':'continuation',
                      'gapSeconds':after['startTime']-before['endTime'],'sharedGestureRefs':sorted(common)})
  all_intents.extend(episodes)
 all_intents.sort(key=lambda e:(e['startTime'],e['source'],e['endTime'],e['intentId']))
 assert all(owners)
 return all_intents,relations,owners

def frame_range(start,end,hop,n):
 a=min(n-1,max(0,int(math.floor(start/hop+1e-8))))
 b=min(n,max(a+1,int(math.ceil(end/hop-1e-8))))
 return a,b

def source_features(data,features,intents,params=PARAMETERS):
 sources=sorted(data['sources']);hop=params['windowSeconds'];n=round(data['duration']/hop);m=len(sources)
 rms=np.zeros((n,m));flux=rms.copy();audio_active=np.zeros((n,m),dtype=bool);eligible=np.zeros((n,m),dtype=bool);density=rms.copy();persistence=rms.copy()
 source_ref={s:max(float(np.percentile(features[s][:,1],95)),1e-12) for s in sources}
 for j,s in enumerate(sources):
  f=features[s];bins=np.minimum(n-1,np.maximum(0,np.floor(f[:,0]/hop+1e-8).astype(int)));counts=np.bincount(bins,minlength=n)
  rms[:,j]=np.sqrt(np.bincount(bins,weights=f[:,1]**2,minlength=n)/np.maximum(1,counts))
  np.maximum.at(flux[:,j],bins,f[:,5])
  floor=next(st['activityFloor'] for st in data['stemStatistics'] if st['source']==s)
  audio_active[:,j]=rms[:,j]>=floor
  times=np.array([a['time'] for a in data['attacks'] if a['source']==s]);ends=np.round((np.arange(n)+1)*hop,6)
  starts=np.round(np.maximum(0,ends-params['densityWindowSeconds']),6)
  density[:,j]=(np.searchsorted(times,ends,side='left')-np.searchsorted(times,starts,side='left'))/params['densityWindowSeconds']
 for e in intents:
  a,b=frame_range(e['startTime'],e['endTime'],hop,n);eligible[a:b,sources.index(e['source'])]=True
 # Persistence remains the previous measurable relevance descriptor. It is NOT
 # permission to arbitrate: only the independent intent-owner mask grants that.
 measured_relevance=audio_active|eligible
 for j in range(m):
  streak=0
  for i in range(n):
   streak=streak+1 if measured_relevance[i,j] else 0;persistence[i,j]=min(1,streak*hop/params['persistenceSeconds'])
 reference=max(float(np.percentile(np.concatenate([f[:,1] for f in features.values()]),95)),1e-12)
 flux_ref=max(float(np.percentile(np.concatenate([f[:,5] for f in features.values()]),95)),1e-12)
 local=rms/np.maximum(np.sqrt(np.sum(rms**2,axis=1,keepdims=True)),1e-12)
 factors={'novelty':flux/(flux+flux_ref),'rhythm':density/(density+params['densityReferenceHz']),
          'persistence':persistence,'isolation':local}
 return {'sources':sources,'rms':rms,'flux':flux,'eligible':eligible,'audioActive':audio_active,'density':density,'local':local,'factors':factors,
         'reference':reference,'fluxReference':flux_ref,'sourceReferences':source_ref,'hop':hop,'n':n}

def salience(rms,reference,factors,weights=None):
 weights=PARAMETERS['weights'] if weights is None else weights
 assert reference>0 and all(weight>=0 for weight in weights.values())
 base=np.log1p(np.asarray(rms)/reference)
 bonus=sum(weights[key]*np.asarray(factors[key]) for key in weights)
 return base*(1+bonus)

def arbitrate(raw,eligible,params=PARAMETERS,trace=None):
 """Source-neutral smoothing plus set-valued dominance; no instrument cap."""
 n,m=raw.shape;hop=params['windowSeconds'];smoothed=np.zeros_like(raw);roles=np.zeros((n,m),dtype=np.int8)
 previous=np.zeros(m);dominants=set();last_switch=-math.inf;history=[]
 for i in range(n):
  target=np.where(eligible[i],raw[i],0);tau=np.where(target>=previous,params['attackTauSeconds'],params['releaseTauSeconds'])
  current=previous+(target-previous)*(1-np.exp(-hop/tau));current=np.where(eligible[i],current,0);previous=current;smoothed[i]=current
  top=float(np.max(current));old={j for j in dominants if current[j]>0};old_top=max((float(current[j]) for j in old),default=0)
  ties=set(np.flatnonzero((current>0)&(current>=top*(1-params['tieFraction']))).tolist())
  strong=top>old_top*params['strongChangeRatio']
  challenge=top>old_top*(1+params['hysteresisRatio'])
  hold_elapsed=i*hop-last_switch
  if not old or (challenge and (i*hop-last_switch>=params['minimumHoldSeconds'] or strong)):
   new=ties
  else:
   new={j for j in old if current[j]>=old_top/(1+params['hysteresisRatio'])}
   new.update(j for j in ties if current[j]>=old_top*(1-params['tieFraction']) and current[j]<=old_top*(1+params['tieFraction']))
  if trace is not None:
   trace.append({'frame':i,'previousDominants':sorted(dominants),'dominants':sorted(new),
    'inactiveIncumbents':sorted(j for j in dominants if not eligible[i,j]),'tieCandidates':sorted(ties),
    'strongChange':bool(strong and old_top>0),'strongChangeBypass':bool(old and challenge and strong and hold_elapsed<params['minimumHoldSeconds']),
    'challenge':bool(challenge and old_top>0),'holdElapsedSeconds':round(hold_elapsed,9) if math.isfinite(hold_elapsed) else None,
    'decision':'noEligibleIncumbent' if not old else 'challengeAfterHoldOrStrongChange' if challenge and (hold_elapsed>=params['minimumHoldSeconds'] or strong) else 'hysteresisOrTieContinuity'})
  if new!=dominants:last_switch=i*hop
  dominants=new;history.append(tuple(sorted(new)))
  if top>0:
   roles[i,current>=top*params['supportingRatio']]=1;roles[i,current>=top*params['secondaryRatio']]=2
   for j in new:roles[i,j]=3
 return smoothed,roles,history

def rank_vector(row):
 # Average ties so equal sources are invariant to source ordering/name.
 return np.array([np.sum(row>value)+(np.sum(row==value)-1)/2 for value in row])

def sensitivity(model,baseline_raw,baseline_history,params=PARAMETERS):
 tests=[];active=np.any(model['eligible'],axis=1);base_ranks=np.array([rank_vector(row) for row in baseline_raw])
 for key in params['weights']:
  for delta in params['sensitivityWeightDeltas']:
   weights=dict(params['weights']);weights[key]*=1+delta
   score=salience(model['rms'],model['reference'],model['factors'],weights);score=np.where(model['eligible'],score,0)
   _,_,history=arbitrate(score,model['eligible'],params);correlations=[];jaccards=[]
   for i in np.flatnonzero(active):
    a=base_ranks[i];b=rank_vector(score[i]);correlations.append(1. if np.std(a)==0 or np.std(b)==0 else float(np.corrcoef(a,b)[0,1]))
    x=set(baseline_history[i]);y=set(history[i]);jaccards.append(len(x&y)/len(x|y) if x|y else 1.)
   nonzero=baseline_raw>1e-12;relative=np.abs(score-baseline_raw)[nonzero]/baseline_raw[nonzero]
   tests.append({'weight':key,'relativeDelta':delta,'meanRankCorrelation':float(np.mean(correlations)),
    'dominantJaccard':float(np.mean(jaccards)),'p99RelativeScoreChange':float(np.percentile(relative,99)),
    'maximumRelativeScoreChange':float(np.max(relative))})
 limits=params['sensitivityPass']
 passed=all(t['meanRankCorrelation']>=limits['minimumMeanRankCorrelation'] and t['dominantJaccard']>=limits['minimumDominantJaccard'] and t['p99RelativeScoreChange']<=limits['maximumP99RelativeScoreChange'] for t in tests)
 return {'pass':passed,'limits':limits,'perturbations':tests,'meaning':'local weight robustness, not proof of perceptual salience truth'}

def distributions(data,features):
 result={}
 for source in [None]+sorted(data['sources']):
  gestures=[g for g in data['gestures'] if source is None or g['source']==source]
  attacks=[a for a in data['attacks'] if source is None or a['source']==source]
  rms=np.concatenate([v[:,1] for s,v in features.items() if source is None or s==source])
  result[source or 'global']={'rms':percentiles(rms),'gestureIntensity':percentiles([g['intensity'] for g in gestures]),
   'integratedEnergy':percentiles([g['features']['integratedEnergy'] for g in gestures]),
   'attackStrength':percentiles([a['amplitude'] for a in attacks])}
 return result

def validate(result,data):
 assert result['schema']=='laise-musical-visual-intents-v1' and result['duration']==data['duration']
 gestures={g['gestureId']:g for g in data['gestures']};intents={i['intentId']:i for i in result['intents']}
 assert len(intents)==len(result['intents']);assert len(result['attackOwners'])==len(data['attacks'])
 covered_gestures=set();seen=[]
 for e in result['intents']:
  assert 0<=e['startTime']<=e['peakTime']<=e['endTime']<=data['duration']
  assert e['source'] in data['sources'] and e['absoluteIntensity']>=0 and e['visualEnergyCandidate']>=0
  assert e['classificationConfidence'] is None or 0<=e['classificationConfidence']<=1
  for gid in e['gestureRefs']:assert gid in gestures and gestures[gid]['source']==e['source'];covered_gestures.add(gid)
  if e['primaryGesture']:
   assert e['classificationConfidence']==gestures[e['primaryGesture']]['confidence']
   assert gestures[e['primaryGesture']]['gestureType']!='PHRASE'
  for index in e['attackRefs']:
   assert data['attacks'][index]['source']==e['source'] and contains(e,data['attacks'][index]['time'])
   assert result['attackOwners'][index]==e['intentId'];seen.append(index)
 assert sorted(seen)==list(range(len(data['attacks']))),'each attack exactly one causal owner'
 assert covered_gestures==set(gestures),'all gesture evidence retained'
 assert result['intents']==sorted(result['intents'],key=lambda e:(e['startTime'],e['source'],e['endTime'],e['intentId']))
 for relation in result['relationships']:
  if 'intentId' in relation:
   intent=intents[relation['intentId']];gesture=gestures[relation['gestureId']]
   assert intent['source']==gesture['source'] and relation['startTime']<=relation['endTime']
  else:assert intents[relation['fromIntent']]['source']==intents[relation['toIntent']]['source']
 assert len(result['frames'])==round(data['duration']/result['analysisParameters']['windowSeconds'])
 for frame in result['frames']:
  assert frame['dominantCount']==sum(v[9]==3 for v in frame['values'])
  assert frame['activeVisualIntents']==len(frame['activeIntentIds'])
  assert len(frame['values'])==len(data['sources'])
  assert all(0<=row[9]<=3 for row in frame['values'])
  assert all(intent in intents for intent in frame['activeIntentIds'])
  causal_sources={intents[identifier]['source'] for identifier in frame['activeIntentIds']}
  assert set(frame['causalActiveSources'])==causal_sources
  assert frame['activeSources']==frame['causalActiveSources']
  if not frame['activeIntentIds']:assert frame['dominantCount']==0
  for source,row in zip(result['sourceOrder'],frame['values']):
   if source not in causal_sources:assert row[4]==row[5]==row[9]==0,'no arbitration salience without a causal owner'
  assert all(all(math.isfinite(float(x)) for x in row) for row in frame['values'])
 canonical(result)
 return True
