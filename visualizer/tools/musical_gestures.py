"""Deterministic offline gesture hypotheses. Never imported by the visualizer.

Absolute stereo energy is retained; thresholds segment evidence, not visual gain.
Confidence is a transparent rule score, NOT a calibrated probability.
"""
from pathlib import Path
from collections import Counter
import hashlib,json,math
import numpy as np
from build_audio_cues import floor_position

PARAMETERS={
 'sampleRate':16000,'windowSamples':1024,'hopSamples':320,
 'envelopeWindowSeconds':.1,'activityRelativeP95':.06,'activityAbsoluteFloor':1e-6,
 'bridgeSilenceSeconds':.12,'sustainMinimumSeconds':.6,'maximumSustainSeconds':8,
 'phraseGapSeconds':1.4,'maximumPhraseSeconds':12,
 'sequenceGapSeconds':1.25,'maximumSequenceSeconds':8,'regularIoiCv':.18,
 'trendIoiCorrelation':.65,'trendIoiRatio':1.3,'rollMinimumRateHz':8,
 'rollMinimumAttacks':6,'rollMaximumCv':.35,
 'rollMaximumInternalGapSeconds':.18,'rollMaximumWindowSeconds':2,
 'rollMinimumMedianRmsContrast':.15,
 'energyTrendWindowSeconds':2,'energyTrendMinimumDb':6,'energyTrendCorrelation':.8,
 'motionMinimumAzimuthDegrees':10,'motionMinimumElevationDegrees':5,
 'motionMinimumDistanceMeters':.15,'trajectorySampleSeconds':.25,
 'toneFlatnessMaximum':.08,'toneCentroidCvMaximum':.35,
 'impulseMaximumTailSeconds':.35,'impulseReleaseRatio':.25,
}
SOURCE_CLASSES={'lead_vocal':'voice','backing_vocals':'voice','drums':'percussive',
 'bass':'pitched','guitar':'pitched','keyboards':'pitched','percussion':'percussive',
 'strings':'pitched','synth':'electronic','other':'unspecified','brass':'pitched','woodwinds':'pitched'}
TYPES=['IMPULSE','REPEATED_PULSE','REPEATED_PULSE_SEQUENCE','SUSTAINED_TONE',
 'SUSTAINED_TEXTURE','CRESCENDO','DECRESCENDO','ACCELERATING_SEQUENCE',
 'DECELERATING_SEQUENCE','TREMOLO_OR_ROLL','PHRASE','CONTINUOUS_MOTION','TRANSITION']

def sha256(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()

def canonical(data):
 return json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

def percentiles(values):
 a=np.asarray(values,dtype=float)
 if not len(a):return {key:0. for key in ['P50','P75','P90','P95','P99','MAX']}
 return {key:float(x) for key,x in zip(['P50','P75','P90','P95','P99','MAX'],np.percentile(a,[50,75,90,95,99,100]))}

def features(samples,rate=16000):
 """Centered 64 ms windows / 20 ms hop; stereo power prevents cancellation."""
 if samples.ndim==1:samples=samples[:,None]
 n=PARAMETERS['windowSamples'];hop=PARAMETERS['hopSamples']
 padded=np.pad(samples,((n//2,n//2),(0,0)))
 frames=np.lib.stride_tricks.sliding_window_view(padded,n,axis=0)[::hop].swapaxes(1,2)
 count=len(frames);rms=np.empty(count);peak=np.empty(count);flux=np.empty(count);centroid=np.empty(count);flatness=np.empty(count)
 previous=np.zeros(n//2+1);window=np.hanning(n);freq=np.fft.rfftfreq(n,1/rate)
 for start in range(0,count,512):
  chunk=frames[start:start+512];stop=start+len(chunk)
  rms[start:stop]=np.sqrt(np.mean(chunk.astype(np.float64)**2,axis=(1,2)))
  peak[start:stop]=np.max(np.abs(chunk),axis=(1,2))
  spectrum=np.fft.rfft(chunk*window[None,:,None],axis=1)
  mag=np.sqrt(np.mean(np.abs(spectrum)**2,axis=2))/n
  flux[start:stop]=np.mean(np.maximum(0,np.diff(mag,axis=0,prepend=previous[None,:])),axis=1);previous=mag[-1]
  total=np.sum(mag,axis=1);centroid[start:stop]=np.sum(mag*freq,axis=1)/(total+1e-20)
  power=mag[:,1:]**2
  flatness[start:stop]=np.exp(np.mean(np.log(power+1e-20),axis=1))/(np.mean(power,axis=1)+1e-20)
 flatness[rms<1e-9]=0
 envelope=np.convolve(np.pad(rms,(2,2),mode='edge'),np.ones(5)/5,mode='valid')
 return {'time':np.arange(count)*hop/rate,'rms':rms,'peak':peak,'flux':flux,
         'centroid':centroid,'flatness':flatness,'envelope':envelope,'hop':hop/rate}

def active_regions(f):
 envelope=f['envelope'];floor=max(PARAMETERS['activityAbsoluteFloor'],float(np.percentile(envelope,95))*PARAMETERS['activityRelativeP95'])
 active=envelope>=floor
 # Close only bounded short internal holes. Leading/trailing silence stays silent.
 i=0
 while i<len(active):
  if active[i]:i+=1;continue
  j=i
  while j<len(active) and not active[j]:j+=1
  if i>0 and j<len(active) and (j-i)*f['hop']<=PARAMETERS['bridgeSilenceSeconds']:active[i:j]=True
  i=j
 edges=np.diff(np.r_[False,active,False].astype(int));spans=list(zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)))
 return spans,floor

def repetition(times):
 if len(times)<2:return None
 ioi=np.diff(times);mean=float(np.mean(ioi));cv=float(np.std(ioi)/max(mean,1e-12));rate=1/max(mean,1e-12)
 evidence={'attackCount':len(times),'ioiMean':mean,'ioiVariance':float(np.var(ioi)),
           'ioiCv':cv,'rateHz':rate,'ioiSeconds':[float(x) for x in ioi]}
 correlation=0.
 if len(ioi)>=3 and np.std(ioi)>1e-9:correlation=float(np.corrcoef(np.arange(len(ioi)),ioi)[0,1])
 third=max(1,len(ioi)//3);first=float(np.mean(ioi[:third]));last=float(np.mean(ioi[-third:]));evidence['ioiTrendCorrelation']=correlation
 if len(times)>=4 and abs(correlation)>=PARAMETERS['trendIoiCorrelation'] and max(first,last)/max(min(first,last),1e-12)>=PARAMETERS['trendIoiRatio']:
  return ('ACCELERATING_SEQUENCE' if correlation<0 else 'DECELERATING_SEQUENCE',min(.95,.6+.3*abs(correlation)),evidence)
 if len(times)>=PARAMETERS['rollMinimumAttacks'] and rate>=PARAMETERS['rollMinimumRateHz'] and cv<=PARAMETERS['rollMaximumCv']:
  return 'TREMOLO_OR_ROLL',min(.85,.6+.25*(1-cv)),evidence
 if cv<=PARAMETERS['regularIoiCv'] and (len(times)>=3 or .12<=mean<=1.25):
  return ('REPEATED_PULSE_SEQUENCE' if len(times)>=4 else 'REPEATED_PULSE'),min(.9,.55+.35*(1-cv)),evidence
 return None

def energy_trend(envelope,hop):
 if len(envelope)*hop<PARAMETERS['energyTrendWindowSeconds']-.001 or np.min(envelope)<=1e-8:return None
 db=20*np.log10(envelope);corr=0. if np.std(db)<1e-9 else float(np.corrcoef(np.arange(len(db)),db)[0,1])
 n=max(1,len(db)//5);change=float(np.median(db[-n:])-np.median(db[:n]))
 if abs(change)<PARAMETERS['energyTrendMinimumDb'] or abs(corr)<PARAMETERS['energyTrendCorrelation'] or change*corr<=0:return None
 return ('CRESCENDO' if change>0 else 'DECRESCENDO',min(.95,.6+.35*abs(corr)),{'energyChangeDb':change,'energyTimeCorrelation':corr})

def roll_groups(attacks):
 """Find dense local runs even inside a slower/irregular surrounding sequence."""
 groups=[];group=[]
 for a in attacks:
  if group and (a['time']-group[-1]['time']>PARAMETERS['rollMaximumInternalGapSeconds'] or a['time']-group[0]['time']>PARAMETERS['rollMaximumWindowSeconds']):groups.append(group);group=[]
  group.append(a)
 if group:groups.append(group)
 found=[]
 for group in groups:
  if len(group)<PARAMETERS['rollMinimumAttacks']:continue
  ioi=np.diff([a['time'] for a in group]);mean=float(np.mean(ioi));cv=float(np.std(ioi)/mean)
  if 1/mean>=PARAMETERS['rollMinimumRateHz'] and cv<=PARAMETERS['rollMaximumCv']:
   found.append((group,min(.85,.6+.25*(1-cv)),{'attackCount':len(group),'rateHz':1/mean,'ioiCv':cv,
     'ioiMean':mean,'ioiVariance':float(np.var(ioi)),'ioiSeconds':ioi.tolist(),
     'method':'local dense onset run; tremolo/roll candidate, not instrument-technique certainty'}))
 return found

def roll_modulation(f,group):
 """Independent signal support: median within-IOI RMS peak/trough contrast.

 Dense legacy timestamps alone cannot distinguish roll from spectral flutter.
 Contrast is analysis evidence only; absolute intensity is never rescaled.
 """
 contrasts=[]
 for left,right in zip(group,group[1:]):
  a=int(np.searchsorted(f['time'],left['time']));b=int(np.searchsorted(f['time'],right['time'],side='right'))
  signal=f['rms'][a:b]
  if len(signal)>=2:
   high=float(np.max(signal));contrasts.append((high-float(np.min(signal)))/max(high,1e-12))
 median=float(np.median(contrasts)) if contrasts else 0.
 return median>=PARAMETERS['rollMinimumMedianRmsContrast'],{'medianWithinIoiRmsContrast':median,
   'contrastThreshold':PARAMETERS['rollMinimumMedianRmsContrast'],'intervalsMeasured':len(contrasts)}

def trajectory(role,start,peak,end):
 times={float(start),float(peak),float(end)}
 times.update(float(k['time_seconds']) for k in role['keyframes']+role['distance_keyframes'] if start<float(k['time_seconds'])<end)
 times.update(float(t) for t in np.arange(start,end,PARAMETERS['trajectorySampleSeconds']))
 rows=[]
 for t in sorted(times):
  x,z,az,el,distance=floor_position(role,t)
  rows.append({'time':round(t,6),'azimuth':round(az,6),'elevation':round(el,6),
               'distance':round(distance,6),'x':round(x,6),'z':round(z,6)})
 return rows

def summarize(f,start,end):
 a=max(0,int(np.searchsorted(f['time'],start)));b=max(a+1,int(np.searchsorted(f['time'],end,side='right')));b=min(b,len(f['rms']))
 rms=f['rms'][a:b];peak=float(np.max(f['peak'][a:b]));absolute=float(np.sqrt(np.mean(rms**2)))
 energy=float(np.sum(rms**2)*f['hop'])
 return {'rms':absolute,'localPeak':peak,'crestFactor':peak/max(absolute,1e-12),'integratedEnergy':energy,
         'spectralCentroid':float(np.mean(f['centroid'][a:b])), 'spectralFlux':float(np.mean(f['flux'][a:b])),
         'spectralFlatness':float(np.median(f['flatness'][a:b])),
         'sustainRms':float(np.sqrt(np.mean(rms[min(len(rms)-1,round(.15/f['hop'])):]**2))),
         'peakTime':float(f['time'][a+int(np.argmax(rms))])}

def analyze_source(source,f,attacks,role,duration):
 """Independent parallel evidence layers; no cross-stem grouping or new attacks."""
 gestures=[];spans,floor=active_regions(f);amplitudes={a['index']:a['amplitude'] for a in attacks}
 def add(kind,start,end,confidence,evidence,refs=None):
  start=round(max(0,float(start)),6);end=round(min(duration,float(end)),6)
  if end<start:return None
  metrics=summarize(f,start,end);peak=min(end,max(start,metrics.pop('peakTime')))
  support_start=int(np.searchsorted(f['time'],min(end,start+.15)))
  support_end=int(np.searchsorted(f['time'],end,side='right'))
  support=float(np.count_nonzero(f['envelope'][support_start:support_end]>=floor)*f['hop'])
  metrics.update({'timeToRmsPeak':peak-start,'timeAfterRmsPeak':end-peak,
                  'sustainAboveActivityFloorSeconds':min(max(0,end-start-.15),support)})
  refs=[a['index'] for a in attacks if start<=a['time']<=end] if refs is None else refs
  g={'source':source,'sourceClass':SOURCE_CLASSES[source],'startTime':start,'peakTime':peak,
     'endTime':end,'duration':round(end-start,6),'gestureType':kind,'intensity':metrics['rms'],
     'attackStrength':max((amplitudes[i] for i in refs),default=0),
     'sustainStrength':metrics['sustainRms'],'onsetDensity':len(refs)/max(end-start,.02),
     'repetitionRate':evidence.get('rateHz',0),'trend':evidence.get('energyChangeDb',evidence.get('ioiTrendCorrelation',0)),
     'features':metrics,'attackRefs':refs,'confidence':round(float(confidence),6),'evidence':evidence,
     'trajectory':trajectory(role,start,peak,end)}
  gestures.append(g);return g
 # Silence-delimited coarse temporal phrases. A duration cap is explicit evidence.
 chunks=[];current=[]
 for attack in attacks:
  if current and (attack['time']-current[-1]['time']>PARAMETERS['phraseGapSeconds'] or attack['time']-current[0]['time']>PARAMETERS['maximumPhraseSeconds']):chunks.append(current);current=[]
  current.append(attack)
 if current:chunks.append(current)
 for chunk in chunks:
  add('PHRASE',chunk[0]['time'],min(duration,chunk[-1]['time']+.12),.6,
      {'method':'same-source attack-gap grouping; temporal phrase proxy, not score segmentation',
       'gapSeconds':PARAMETERS['phraseGapSeconds'],'maximumSeconds':PARAMETERS['maximumPhraseSeconds']},[a['index'] for a in chunk])
 # Short decays qualify as impulses. Existing onset references are never removed.
 for a in attacks:
  i=int(np.searchsorted(f['time'],a['time']));j=min(len(f['envelope']),i+round(.7/f['hop'])+1)
  if j<=i:continue
  signal=f['envelope'][i:j];p=int(np.argmax(signal[:min(len(signal),6)]));threshold=max(floor,float(signal[p])*.25)
  hits=np.flatnonzero(signal[p:]<=threshold)
  if len(hits):
   release=(p+int(hits[0]))*f['hop']
   if .02<=release<=PARAMETERS['impulseMaximumTailSeconds']:
    add('IMPULSE',a['time'],a['time']+release,.8,{'releaseSeconds':release,'releaseRatio':.25,'activityFloor':floor},[a['index']])
 # Group only within this source and bounded windows, retaining every child hit.
 groups=[];group=[]
 for a in attacks:
  if group and (a['time']-group[-1]['time']>PARAMETERS['sequenceGapSeconds'] or a['time']-group[0]['time']>PARAMETERS['maximumSequenceSeconds']):groups.append(group);group=[]
  group.append(a)
 if group:groups.append(group)
 for group in groups:
  found=repetition([a['time'] for a in group])
  if found:
   kind,confidence,evidence=found
   if kind=='TREMOLO_OR_ROLL':
    supported,modulation=roll_modulation(f,group);evidence.update(modulation)
    if not supported:
     kind='REPEATED_PULSE_SEQUENCE';confidence=.55
     evidence['limitation']='dense legacy cue sequence; insufficient independent RMS modulation for roll'
   add(kind,group[0]['time'],group[-1]['time'],confidence,evidence,[a['index'] for a in group])
 for group,confidence,evidence in roll_groups(attacks):
  supported,modulation=roll_modulation(f,group)
  if not supported:continue
  evidence.update(modulation)
  refs=[a['index'] for a in group]
  if not any(g['gestureType']=='TREMOLO_OR_ROLL' and g['attackRefs']==refs for g in gestures):
   add('TREMOLO_OR_ROLL',group[0]['time'],group[-1]['time'],confidence,evidence,refs)
 # Continuous energy intervals, separated from onset counting.
 for a,b in spans:
  if (b-a)*f['hop']<PARAMETERS['sustainMinimumSeconds']:continue
  for left in range(a,b,max(1,round(PARAMETERS['maximumSustainSeconds']/f['hop']))):
   right=min(b,left+round(PARAMETERS['maximumSustainSeconds']/f['hop']))
   if (right-left)*f['hop']<PARAMETERS['sustainMinimumSeconds']:continue
   start=float(f['time'][left]);end=min(duration,right*f['hop']);flat=float(np.median(f['flatness'][left:right]));cent=f['centroid'][left:right];cv=float(np.std(cent)/max(float(np.mean(cent)),1e-12))
   kind='SUSTAINED_TONE' if flat<PARAMETERS['toneFlatnessMaximum'] and cv<PARAMETERS['toneCentroidCvMaximum'] else 'SUSTAINED_TEXTURE'
   g=add(kind,start,end,.72,{'method':'continuous energy support; tone/texture is spectral proxy, not pitch transcription','activityFloor':floor,'spectralFlatnessMedian':flat,'centroidCv':cv})
   if g:
    tr=g['trajectory'];az=np.ptp([p['azimuth'] for p in tr]);el=np.ptp([p['elevation'] for p in tr]);dist=np.ptp([p['distance'] for p in tr])
    if az>=PARAMETERS['motionMinimumAzimuthDegrees'] or el>=PARAMETERS['motionMinimumElevationDegrees'] or dist>=PARAMETERS['motionMinimumDistanceMeters']:
     add('CONTINUOUS_MOTION',start,end,.95,{'method':'known T007 automation during measured active energy','azimuthRange':float(az),'elevationRange':float(el),'distanceRange':float(dist)})
 # Two-second energy trends, merged only if overlapping with the same sign.
 trends=[];window=round(PARAMETERS['energyTrendWindowSeconds']/f['hop']);stride=round(1/f['hop'])
 for a in range(0,len(f['envelope'])-window+1,stride):
  env=f['envelope'][a:a+window]
  if np.mean(env>=floor)<.9:continue
  found=energy_trend(env,f['hop'])
  if found:
   kind,confidence,evidence=found;start=a*f['hop'];end=min(duration,(a+window)*f['hop'])
   if trends and trends[-1][0]==kind and start<trends[-1][2]:
    old=trends.pop();start=old[1]
    full=f['envelope'][round(start/f['hop']):round(end/f['hop'])];found=energy_trend(full,f['hop'])
    if found:kind,confidence,evidence=found
    else:trends.append(old);start=a*f['hop']
   trends.append((kind,start,end,confidence,evidence))
 for kind,start,end,confidence,evidence in trends:add(kind,start,end,confidence,evidence)
 gestures.sort(key=lambda g:(g['startTime'],g['endTime'],g['gestureType']))
 for i,g in enumerate(gestures):g['gestureId']=f'{source}:g{i:05d}'
 relationships=[]
 for g in gestures:
  relationships.extend({'parent':g['gestureId'],'childAttack':i,'relation':'containsAttack'} for i in g['attackRefs'])
  if g['gestureType']!='PHRASE':
   parents=[p for p in gestures if p['gestureType']=='PHRASE' and p['startTime']<=g['startTime'] and g['endTime']<=p['endTime']]
   if parents:relationships.append({'parent':parents[0]['gestureId'],'child':g['gestureId'],'relation':'containsGesture'})
 stats={'source':source,'attackCount':len(attacks),'gestureCount':len(gestures),'types':dict(sorted(Counter(g['gestureType'] for g in gestures).items())),
        'meanDuration':float(np.mean([g['duration'] for g in gestures])) if gestures else 0,
        'meanConfidence':float(np.mean([g['confidence'] for g in gestures])) if gestures else 0,
        'rmsDistribution':percentiles(f['rms']),'peakDistribution':percentiles(f['peak']),
        'gestureIntensityDistribution':percentiles([g['intensity'] for g in gestures]),
        'integratedEnergy':float(np.sum(f['rms']**2)*f['hop']),'activityFloor':floor,
        'activeSeconds':float(sum(b-a for a,b in spans)*f['hop'])}
 return gestures,relationships,stats

def validate(data,cues):
 assert data['schema']=='laise-musical-gestures-v1'
 assert len(data['sources'])==12 and set(data['sources'])==set(SOURCE_CLASSES)
 assert len(data['attacks'])==len(cues['events'])==10282
 for i,a in enumerate(data['attacks']):
  cue=cues['events'][i];assert a=={'index':i,**{key:cue[key] for key in ['source','time','amplitude','strength']}}
 ids={g['gestureId']:g for g in data['gestures']};assert len(ids)==len(data['gestures'])
 assert data['gestures']==sorted(data['gestures'],key=lambda g:(g['startTime'],g['source'],g['endTime'],g['gestureType']))
 for g in data['gestures']:
  assert g['source'] in SOURCE_CLASSES and g['gestureType'] in TYPES
  assert 0<=g['startTime']<=g['peakTime']<=g['endTime']<=data['duration'] and g['duration']>=0
  assert abs(g['duration']-(g['endTime']-g['startTime']))<1e-5 and 0<=g['confidence']<=1
  assert g['intensity']>=0 and g['features']['integratedEnergy']>=0
  assert g['trajectory'] and g['trajectory']==sorted(g['trajectory'],key=lambda p:p['time'])
  for p in g['trajectory']:
   assert g['startTime']-1e-6<=p['time']<=g['endTime']+1e-6 and p['distance']>=0 and -90<=p['elevation']<=90 and abs(p['x'])<=.8 and abs(p['z'])<=.8
  for i in g['attackRefs']:assert 0<=i<len(data['attacks']) and data['attacks'][i]['source']==g['source']
 for r in data['relationships']:
  parent=ids[r['parent']]
  if 'child' in r:
   child=ids[r['child']];assert parent['gestureType']=='PHRASE' and child['gestureType']!='PHRASE' and parent['source']==child['source'] and parent['startTime']<=child['startTime']<=child['endTime']<=parent['endTime']
  else:assert r['childAttack'] in parent['attackRefs']
 canonical(data) # rejects NaN / Infinity anywhere, including evidence and statistics.
 return True
