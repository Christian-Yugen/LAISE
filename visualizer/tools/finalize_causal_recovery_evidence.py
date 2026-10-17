"""Verify R1 evidence and run existing suites; performs no Git mutations."""
from pathlib import Path
import concurrent.futures,hashlib,json,re,shutil,subprocess,sys
V=Path(__file__).resolve().parents[1];OUT=V/'reports/v1_3br1-causal-eligibility';B=V/'reports/v1_3b-musical-salience-arbitration'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
 first=V/'public/audio/tukana-musical-visual-intents-v1.json';second=OUT/'determinism-run-2.json'
 assert first.read_bytes()==second.read_bytes()
 paired={n:(OUT/n).read_bytes()==(OUT/'run-2'/n).read_bytes() for n in ['analysis-summary.json','sensitivity.json','intensity-distributions.json','arbitration-decisions.json']}
 assert all(paired.values())
 det={'pass':True,'byteIdentical':True,'sha256':digest(first),'independentFullRuns':2,'pairedEvidence':paired}
 write('determinism.json',det)
 # Keep the original tests untouched: their current-artifact alias must now
 # reference R1. The original B artifact/evidence remain in before/rollback.
 shutil.copyfile(second,B/'determinism-run-2.json')
 for n in ['analysis-summary.json','sensitivity.json','intensity-distributions.json','arbitration-decisions.json','determinism.json']:shutil.copyfile(OUT/n,B/n)
 import validate_musical_salience as validator
 validator.OUT=OUT;validator.main()
 shutil.copyfile(OUT/'sanity-checks.json',B/'sanity-checks.json')
 commands={'javascript-tests':['node','--test','--test-reporter=tap',*[str(p.relative_to(V)) for p in sorted((V/'tests').glob('*.test.js'))]],
  'python-tests':[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_*.py'],
  'build':['npm.cmd','run','build'],'diff-check':['git','diff','--check']}
 def run(item):
  name,cmd=item;p=subprocess.run(cmd,cwd=V,capture_output=True,text=True,encoding='utf-8',errors='replace');log=p.stdout+p.stderr
  (OUT/(name+'.txt')).write_text(log,encoding='utf-8')
  return name,{'pass':p.returncode==0,'exitCode':p.returncode,'command':cmd,'log':name+'.txt'}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:checks=dict(pool.map(run,commands.items()))
 js=(OUT/'javascript-tests.txt').read_text(encoding='utf-8');py=(OUT/'python-tests.txt').read_text(encoding='utf-8')
 counts={'javascript':int(re.search(r'# tests (\d+)',js).group(1)),'python':int(re.search(r'Ran (\d+) tests',py).group(1))}
 counts['total']=sum(counts.values());assert counts['total']==152,counts
 checks['testCounts']=counts
 playback=json.loads((OUT/'real-run-v13br1.json').read_text());pixels=json.loads((OUT/'pixel-regression.json').read_text())
 checks['playback']={'pass':playback['pass'],'unique':playback['state']['uniqueAppliedCues'],'dropped':playback['droppedCues'],'duplicate':playback['duplicateCues'],'unexpectedReset':playback['state']['unexpectedResetCount']}
 checks['pixels']={'pass':all(p['pixelIdentical'] for p in pixels),'times':[p['time'] for p in pixels]}
 checks['causalAudit']=json.loads((OUT/'causal-after.json').read_text())['metrics']
 checks['determinism']=det
 baseline=json.loads((V/'reports/LAISE_VISUALIZER_V1_2_APPROVED_BASELINE.json').read_text())
 checks['protectedHashes']={p:{'sha256':digest(V/p),'matches':digest(V/p)==h} for p,h in baseline['hashes'].items()}
 checks['pass']=all(checks[k]['pass'] for k in [*commands,'playback','pixels']) and not any(checks['causalAudit'].values()) and all(x['matches'] for x in checks['protectedHashes'].values())
 write('final-checks.json',checks);print(json.dumps(checks,ensure_ascii=False,indent=2));assert checks['pass']
if __name__=='__main__':main()
