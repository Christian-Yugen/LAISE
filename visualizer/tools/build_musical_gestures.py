"""V1.3A: read-only T007 audio -> separate offline semantic JSON and evidence."""
from pathlib import Path
import argparse,json,subprocess,platform
import numpy as np
from musical_gestures import PARAMETERS,SOURCE_CLASSES,TYPES,features,analyze_source,validate,sha256,canonical,percentiles

V=Path(__file__).resolve().parents[1];ROOT=V.parent
OUT=V/'reports/v1_3a-musical-gesture-intelligence'
MANIFEST=ROOT/'projects/tukana_02_a_mata_se_move/experiments/TUK2_T007/spatial_scenes/TUK2_T007_automation_manifest.json'
def build(output=None,evidence=None):
 output=Path(output) if output else V/'public/audio/tukana-musical-gestures-v1.json'
 evidence=Path(evidence) if evidence else OUT;evidence.mkdir(parents=True,exist_ok=True)
 cues_path=V/'public/audio/tukana-stem-cues.json';cues=json.loads(cues_path.read_text())
 manifest=json.loads(MANIFEST.read_text(encoding='utf-8'));roles={r['source_id']:r for r in manifest['roles']}
 assert set(roles)==set(SOURCE_CLASSES) and manifest['frames']/manifest['rate']==cues['duration']==330
 assert sha256(MANIFEST)==cues['analysis']['manifestSha256']
 master=V/('public'+cues['master']['url']);assert sha256(master)==cues['master']['sha256']
 attacks=[{'index':i,**{key:c[key] for key in ['source','time','amplitude','strength']}} for i,c in enumerate(cues['events'])]
 all_gestures=[];relationships=[];statistics=[];sources={};all_rms=[];all_peaks=[]
 feature_dir=evidence/'features';feature_dir.mkdir(exist_ok=True)
 for stem in cues['stems']:
  source=stem['id'];path=ROOT/stem['file'];digest=sha256(path);assert digest==stem['sha256'],source
  raw=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-ar',str(PARAMETERS['sampleRate']),'-ac','2','-f','f32le','-'],check=True,capture_output=True).stdout
  samples=np.frombuffer(raw,dtype='<f4').reshape(-1,2);assert abs(len(samples)/PARAMETERS['sampleRate']-330)<1/PARAMETERS['sampleRate']
  f=features(samples);selected=[a for a in attacks if a['source']==source]
  gestures,relations,stats=analyze_source(source,f,selected,roles[source],330)
  sources[source]={'sha256':digest,'file':stem['file'],'sourceClass':SOURCE_CLASSES[source],
                   'spatialRoleRef':f'T007.roles/{source}','rawSampleRms':float(np.sqrt(np.mean(samples.astype(np.float64)**2))),
                   'rawSamplePeak':float(np.max(np.abs(samples)))}
  all_gestures.extend(gestures);relationships.extend(relations);statistics.append(stats);all_rms.append(f['rms']);all_peaks.append(f['peak'])
  columns=['time','rms','peak','envelope','centroid','flux','flatness']
  feature_data={'source':source,'columns':columns,'hopSeconds':f['hop'],'rows':np.round(np.column_stack([f[k] for k in columns]),9).tolist()}
  (feature_dir/f'{source}.json').write_bytes(canonical(feature_data))
  print(f'{source}: {len(selected)} preserved attacks, {len(gestures)} gestures; {stats["types"]}',flush=True)
  del raw,samples,f
 all_gestures.sort(key=lambda g:(g['startTime'],g['source'],g['endTime'],g['gestureType']))
 relationships.sort(key=lambda r:(r['parent'],r['relation'],r.get('child',''),r.get('childAttack',-1)))
 ffmpeg=subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0]
 data={'schema':'laise-musical-gestures-v1','version':'1.3A.1','duration':330,
       'metadata':{'baselineCommit':'6bc4b130f86356f0dd6994a55dfc91f4d78f7acb','runtimeConsumer':None,
        'confidenceMeaning':'heuristic rule support, not calibrated probability','intensityUnit':'absolute stereo RMS full scale; no per-stem gain normalization',
        'environment':{'python':platform.python_version(),'numpy':np.__version__,'ffmpeg':ffmpeg}},
       'sourceHashes':{'master':sha256(master),'cueDataset':sha256(cues_path),'t007Automation':sha256(MANIFEST),
        'analyzer':sha256(Path(__file__).with_name('musical_gestures.py')),'builder':sha256(Path(__file__))},
       'analysisParameters':PARAMETERS,'sources':sources,'stemStatistics':statistics,
       'globalStatistics':{'frameRmsDistribution':percentiles(np.concatenate(all_rms)),
         'framePeakDistribution':percentiles(np.concatenate(all_peaks)),
         'gestureIntensityDistribution':percentiles([g['intensity'] for g in all_gestures]),
         'meaning':'pooled per-source frame/gesture distribution; not mixed-master loudness'},
       'attacks':attacks,'gestures':all_gestures,'relationships':relationships,
       'spatialTrajectoryReference':{'manifest':str(MANIFEST.relative_to(ROOT)).replace('\\','/'),'hash':sha256(MANIFEST),
         'method':'original T007 floor_position interpolation, last same-time key wins, unwrapped azimuth; 250 ms samples plus automation knots/start/peak/end'},
       'taxonomy':{t:{'count':sum(g['gestureType']==t for g in all_gestures),
         'limitation':'not inferred: no validated transition/section model' if t=='TRANSITION' else 'rule-based evidence hypothesis; inspect before behavior mapping'} for t in TYPES}}
 validate(data,cues);output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(canonical(data))
 (evidence/'analysis-summary.json').write_bytes(canonical({'sources':sources,'stemStatistics':statistics,'taxonomy':data['taxonomy'],'globalStatistics':data['globalStatistics'],'gestures':len(all_gestures),'attacks':len(attacks),'sanityChecks':'PASS','sha256':sha256(output)}))
 print(f'PASS: {len(all_gestures)} gestures, 12 stems, {len(attacks)} preserved attacks -> {output}',flush=True)
 return data
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path);p.add_argument('--evidence',type=Path);a=p.parse_args();build(a.output,a.evidence)
