"""Offline V1.3B partitura: immutable V1.3A -> source-neutral visual intents."""
from pathlib import Path
from collections import Counter
import argparse,json,math
import numpy as np
from musical_gestures import canonical,sha256,percentiles
from musical_salience import PARAMETERS,ROLES,fuse_gestures,frame_range,source_features,salience,arbitrate,sensitivity,distributions,validate

V=Path(__file__).resolve().parents[1];A=V/'reports/v1_3a-musical-gesture-intelligence';OUT=V/'reports/v1_3b-musical-salience-arbitration'

def build(output=None,evidence=None):
 output=Path(output) if output else V/'public/audio/tukana-musical-visual-intents-v1.json'
 evidence=Path(evidence) if evidence else OUT;evidence.mkdir(parents=True,exist_ok=True)
 path=V/'public/audio/tukana-musical-gestures-v1.json';data=json.loads(path.read_text(encoding='utf-8'))
 approved=json.loads((V/'reports/LAISE_VISUALIZER_V1_3A_APPROVED_BASELINE.json').read_text())
 assert sha256(path)==approved['gestureJsonSha256'] and len(data['gestures'])==2583
 features={s:np.array(json.loads((A/f'features/{s}.json').read_text())['rows']) for s in data['sources']}
 intents,relations,owners=fuse_gestures(data);model=source_features(data,features,intents);n=model['n'];hop=model['hop'];sources=model['sources']
 raw=np.where(model['eligible'],salience(model['rms'],model['reference'],model['factors']),0)
 arbitration_trace=[]
 smooth,roles,dominants=arbitrate(raw,model['eligible'],trace=arbitration_trace)
 (evidence/'arbitration-decisions.json').write_bytes(canonical({'sourceOrder':sources,'decisions':arbitration_trace}))
 print(f'Fused {len(data["gestures"])} gesture descriptions -> {len(intents)} causal episodes; all {len(owners)} attacks owned',flush=True)
 stability=sensitivity(model,raw,dominants);(evidence/'sensitivity.json').write_bytes(canonical(stability));assert stability['pass'],stability
 # Ablations are diagnostics, not small-perturbation PASS gates.
 ablations=[]
 for factor in PARAMETERS['weights']:
  weights=dict(PARAMETERS['weights']);weights[factor]=0
  scores=np.where(model['eligible'],salience(model['rms'],model['reference'],model['factors'],weights),0)
  _,_,hist=arbitrate(scores,model['eligible']);active=np.any(model['eligible'],axis=1)
  overlap=[len(set(a)&set(b))/len(set(a)|set(b)) if set(a)|set(b) else 1 for a,b,on in zip(hist,dominants,active) if on]
  ablations.append({'removed':factor,'dominantJaccard':float(np.mean(overlap))})
 frame_intents=[[] for _ in range(n)];gesture_counts=np.zeros(n,dtype=int)
 for g in data['gestures']:
  a,b=frame_range(g['startTime'],g['endTime'],hop,n);gesture_counts[a:b]+=1
 gesture_lookup={g['gestureId']:g for g in data['gestures']}
 for e in intents:
  source=e['source'];j=sources.index(source);a,b=frame_range(e['startTime'],e['endTime'],hop,n)
  for i in range(a,b):frame_intents[i].append(e['intentId'])
  f=features[source];left=int(np.searchsorted(f[:,0],e['startTime']));right=max(left+1,int(np.searchsorted(f[:,0],e['endTime'],side='right')));right=min(len(f),right);left=min(left,right-1)
  absolute=float(np.sqrt(np.mean(f[left:right,1]**2)));peak=float(f[left+int(np.argmax(f[left:right,1])),0]);e['peakTime']=max(e['startTime'],min(e['endTime'],peak))
  peak_frame=min(b-1,max(a,int(e['peakTime']/hop)));context=float(model['local'][peak_frame,j])
  e.update({'absoluteIntensity':absolute,'sourceRelativeIntensity':absolute/model['sourceReferences'][source],
   'trackRelativeIntensity':absolute/model['reference'],'localContextIntensity':context,
   'visualEnergyCandidate':(absolute/model['reference'])**2,'musicalSalience':float(np.max(smooth[a:b,j])),
   'role':ROLES[int(roles[peak_frame,j])],'integratedEnergy':float(np.sum(f[left:right,1]**2)*.02),
   'evolutionRef':{'firstFrame':a,'endFrameExclusive':b,'sourceColumn':j},
   'rhythmicStructures':[gid for gid in e['gestureRefs'] if gesture_lookup[gid]['gestureType'] in {'REPEATED_PULSE','REPEATED_PULSE_SEQUENCE','TREMOLO_OR_ROLL','ACCELERATING_SEQUENCE','DECELERATING_SEQUENCE'}]})
  segments=[]
  for i in range(a,b):
   role=ROLES[int(roles[i,j])];start=max(e['startTime'],i*hop);end=min(e['endTime'],(i+1)*hop)
   if segments and segments[-1]['role']==role:segments[-1]['endTime']=round(end,6)
   else:segments.append({'startTime':round(start,6),'endTime':round(end,6),'role':role})
  e['roleSegments']=segments
 frames=[]
 for i in range(n):
  values=[]
  for j,s in enumerate(sources):
   intensity=float(model['rms'][i,j]);values.append([round(intensity,12),round(intensity/model['sourceReferences'][s],9),
    round(intensity/model['reference'],9),round(float(model['local'][i,j]),9),round(float(raw[i,j]),9),
    round(float(smooth[i,j]),9),round((intensity/model['reference'])**2,9),round(float(model['factors']['novelty'][i,j]),9),
    round(float(model['factors']['persistence'][i,j]),9),int(roles[i,j])])
  frame={'startTime':round(i*hop,6),'endTime':round((i+1)*hop,6),'activeSources':[s for j,s in enumerate(sources) if model['eligible'][i,j]],
   'audioActiveSources':[s for j,s in enumerate(sources) if model['audioActive'][i,j]],
   'causalActiveSources':[s for j,s in enumerate(sources) if model['eligible'][i,j]],
   'activeGestures':int(gesture_counts[i]),'activeVisualIntents':len(frame_intents[i]),'activeIntentIds':frame_intents[i],
   'dominantCount':len(dominants[i]),'salienceDistribution':percentiles(smooth[i]),'values':values}
  frames.append(frame)
 distributions_result=distributions(data,features)
 source_stats=[]
 for j,s in enumerate(sources):
  source_stats.append({'source':s,'intentCount':sum(e['source']==s for e in intents),
   'rolesSeconds':{role:round(float(np.count_nonzero(roles[:,j]==k)*hop),6) for k,role in enumerate(ROLES)},
   'activeSeconds':round(float(np.count_nonzero(model['eligible'][:,j])*hop),6),
   'salienceDistribution':percentiles(smooth[:,j]),'meanSalience':float(np.mean(smooth[:,j])),
   'absoluteRmsP95':model['sourceReferences'][s]})
 activity=np.any(model['eligible'],axis=1);before=np.array([f['activeGestures'] for f in frames]);after=np.array([f['activeVisualIntents'] for f in frames]);dominant_counts=np.array([f['dominantCount'] for f in frames])
 effective=np.sum(smooth,axis=1)**2/np.maximum(np.sum(smooth**2,axis=1),1e-20)
 worst=sorted(range(n),key=lambda i:(-before[i],-len(frames[i]['activeSources']),i))[:20]
 chaos={'maximumActiveSources':max(len(f['activeSources']) for f in frames),'maximumActiveGestures':int(np.max(before)),
  'maximumActiveVisualIntents':int(np.max(after)),'maximumDominantCount':int(np.max(dominant_counts)),
  'meanGestureDescriptions':float(np.mean(before[activity])),'meanIntentDrivers':float(np.mean(after[activity])),
  'descriptionRedundancyReduction':float(1-np.sum(after)/max(1,np.sum(before))),
  'meanDominantCount':float(np.mean(dominant_counts[activity])),'effectiveSalientSourceCount':percentiles(effective[activity]),
  'worstConcurrencyFrames':[{'index':i,**{k:frames[i][k] for k in ['startTime','activeSources','activeGestures','activeVisualIntents','dominantCount']}} for i in worst],
  'meaning':'description/driver concurrency proxies; not proof of future rendered legibility; no source-count cap'}
 report={'sources':source_stats,'chaos':chaos,'sensitivity':stability,'ablations':ablations,
         'dominanceSetChanges':sum(a!=b for a,b in zip(dominants,dominants[1:])),
         'rawTopChanges':int(np.count_nonzero(np.argmax(raw[1:],axis=1)!=np.argmax(raw[:-1],axis=1))),
         'inputGestures':len(data['gestures']),'outputIntents':len(intents),'ownedAttacks':len(owners)}
 result={'schema':'laise-musical-visual-intents-v1','version':'1.3B-R1.1','duration':data['duration'],
  'metadata':{'foundationTag':'LAISE_VISUALIZER_V1_3A_APPROVED','v12Tag':'LAISE_VISUALIZER_V1_2_APPROVED',
   'runtimeConsumer':None,'classificationMeaning':'traceable heuristics, not musical ground truth',
   'causalEligibilityRule':'NO VISUAL SALIENCE WITHOUT A CAUSAL OWNER: an active intent of this source must intersect the analysis interval',
   'activeSourcesMeaning':'compatibility alias of causalActiveSources; audioActiveSources independently records measured energy',
   'continuationRelationsGrantEligibility':False,
   'futureRoleUsage':'priority/arbitration annotation, never a raw binary visual gain switch',
   'futureVisualEnergyRule':'V1.3C must NOT map visualEnergyCandidate directly to Y; perceptual/dynamic calibration is required',
   'intensityUnit':'absolute stereo RMS FS in V1.3A analysis band; source-relative values are diagnostic only',
   'visualEnergyUnit':'dimensionless ratio of mean-square energy to common P95 RMS squared; NOT mesh height',
   'formula':'log1p(rms/commonRmsP95) * (1 + .15*novelty + .10*rhythm + .10*persistence + .10*isolation)',
   'confidenceUsedAsIntensity':False,'staticIntentStatistics':'overall RMS, peak salience; query frames/evolutionRef for time-varying values'},
  'sourceHashes':{'gesturesV13A':sha256(path),'analyzer':sha256(Path(__file__).with_name('musical_salience.py')),
    'builder':sha256(Path(__file__)),'features':{s:sha256(A/f'features/{s}.json') for s in sorted(features)},
    **{k:v for k,v in data['sourceHashes'].items() if k in ['master','cueDataset','t007Automation']}},
  'analysisParameters':PARAMETERS,'calibration':{'commonRmsP95':model['reference'],'commonFluxP95':model['fluxReference'],
    'sourceRmsP95':model['sourceReferences'],'meaning':'common robust scale, no peak reference and no per-source gain applied'},
  'distributions':distributions_result,'sourceOrder':sources,
  'frameColumns':['absoluteIntensity','sourceRelativeIntensity','trackRelativeIntensity','localContextIntensity','rawMusicalSalience','musicalSalience','visualEnergyCandidate','novelty','persistence','roleCode'],
  'roleCodes':ROLES,'intents':intents,'relationships':relations,'attackOwners':owners,'frames':frames,
  'spatialTrajectoryReference':data['spatialTrajectoryReference'],'audit':report}
 validate(result,data);output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(canonical(result))
 (evidence/'analysis-summary.json').write_bytes(canonical(report));(evidence/'intensity-distributions.json').write_bytes(canonical(distributions_result))
 print(f'PASS: {len(intents)} intents, {n} windows, {len(owners)} exact causal owners; SHA256 {sha256(output)}',flush=True)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path);p.add_argument('--evidence',type=Path);a=p.parse_args();build(a.output,a.evidence)
