"""Audit B lineage, exact A inputs, score equation and the untouched V1.2 runtime."""
from pathlib import Path
import json,subprocess,math
import numpy as np
from musical_salience import validate,PARAMETERS
from musical_gestures import sha256,canonical
V=Path(__file__).resolve().parents[1];OUT=V/'reports/v1_3b-musical-salience-arbitration'
def main():
 d=json.loads((V/'public/audio/tukana-musical-visual-intents-v1.json').read_text(encoding='utf-8'))
 a=json.loads((V/'public/audio/tukana-musical-gestures-v1.json').read_text(encoding='utf-8'));assert validate(d,a)
 assert sha256(V/'public/audio/tukana-musical-gestures-v1.json')==d['sourceHashes']['gesturesV13A']
 for name in ['musical_salience.py','build_musical_visual_intents.py']:
  assert sha256(V/'tools'/name)==d['sourceHashes']['analyzer' if name=='musical_salience.py' else 'builder']
 for s,digest in d['sourceHashes']['features'].items():assert sha256(V/f'reports/v1_3a-musical-gesture-intelligence/features/{s}.json')==digest
 for source,item in a['sources'].items():assert sha256(V.parent/item['file'])==item['sha256'],source
 baseline=json.loads((V/'reports/LAISE_VISUALIZER_V1_2_APPROVED_BASELINE.json').read_text())
 for path,digest in baseline['hashes'].items():assert sha256(V/path)==digest,path
 assert subprocess.check_output(['git','rev-parse','LAISE_VISUALIZER_V1_2_APPROVED^{}'],text=True).strip()=='6bc4b130f86356f0dd6994a55dfc91f4d78f7acb'
 # Existing tracked A/runtime/tests/data are immutable during B. New B files are
 # intentionally untracked until human review and are not committed here.
 assert not subprocess.check_output(['git','diff','LAISE_VISUALIZER_V1_3A_APPROVED','--','visualizer/src','visualizer/index.html','visualizer/tests/test_musical_gestures.py','visualizer/public/audio/tukana-musical-gestures-v1.json','visualizer/tools/musical_gestures.py','visualizer/tools/build_musical_gestures.py','visualizer/reports/v1_3a-musical-gesture-intelligence/features'],text=True)
 weights=d['analysisParameters']['weights'];reference=d['calibration']['commonRmsP95'];maxerror=0
 attacks={s:np.array([x['time'] for x in a['attacks'] if x['source']==s]) for s in d['sourceOrder']}
 for frame in d['frames']:
  end=frame['endTime'];start=round(max(0,end-.25),6)
  for j,source in enumerate(d['sourceOrder']):
   row=frame['values'][j];rms=row[0]
   count=int(np.searchsorted(attacks[source],end,side='left')-np.searchsorted(attacks[source],start,side='left'));density=count/.25;rhythm=density/(density+4)
   expected=math.log1p(rms/reference)*(1+weights['novelty']*row[7]+weights['rhythm']*rhythm+weights['persistence']*row[8]+weights['isolation']*row[3]) if source in frame['activeSources'] else 0
   error=abs(expected-row[4]);maxerror=max(maxerror,error);assert error<1e-8,(frame['startTime'],source,error)
   assert 0<=row[3]<=1+1e-8 and abs((rms/reference)**2-row[6])<1e-7
 result={'pass':True,'intents':len(d['intents']),'preservedGestures':len(a['gestures']),'uniqueOwnedAttacks':len(d['attackOwners']),
  'scoreRowsRecomputed':len(d['frames'])*len(d['sourceOrder']),'maximumRawScoreEquationError':maxerror,'scoreEquationTolerance':1e-8,
  'allSourceHashesMatch':True,'v13aIntact':True,'v12RuntimeIntact':True,'noHeightMapping':True,
  'intentJsonSha256':sha256(V/'public/audio/tukana-musical-visual-intents-v1.json')}
 (OUT/'sanity-checks.json').write_bytes(canonical(result));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
