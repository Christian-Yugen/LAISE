"""Freeze evidence: byte-identical visual sections, protected hashes and images."""
from pathlib import Path
import hashlib,json,difflib
from playwright.sync_api import sync_playwright
import continuity_visual_probe as r1
V=Path(__file__).resolve().parents[1]
BASE=V/'tests/fixtures/r3b-pre-continuity'
OUT=V/'reports/v1_2br3b_r1-playback-continuity'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
before=(BASE/'src/main.js').read_text(encoding='utf-8-sig')
after=(V/'src/main.js').read_text(encoding='utf-8-sig')
result={'protected':{},'visualSections':{},'captures':[]}
for name in ['index.html','src/style.css','src/audio-motion-recovery.js','src/ripple-field.js']:
 a=sha(BASE/name);b=sha(V/name);assert a==b,name
 result['protected'][name]={'before':a,'after':b,'identical':True}
for name in ['public/audio/TUKANA02_FINAL_MASTER_PCM24_48k.wav','public/audio/tukana-stem-cues.json','public/audio/tukana-visualizer-manifest.json']:
 if (V/name).exists():result['protected'][name]={'sha256':sha(V/name)}
for name,start,end in [('camera','const TERRAIN =','const smoothed ='),('rendering','function animate()',None)]:
 # Camera/material/particle sections before audio analysis are all protected.
 a=before[before.index(start):before.index(end) if end else len(before)]
 b=after[after.index(start):after.index(end) if end else len(after)]
 assert a==b,name
 result['visualSections'][name]={'identical':True,'sha256':hashlib.sha256(a.encode()).hexdigest()}
(OUT/'temporal-only.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='R3B',tofile='R3B-R1')),encoding='utf-8')
with sync_playwright() as p:
 browser=p.chromium.launch(channel='chrome',headless=True,args=['--mute-audio'])
 for stage in ['before','after']:
  page=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
  page.on('pageerror',lambda e:print('PAGE ERROR',str(e),flush=True))
  page.on('console',lambda m:print('CONSOLE ERROR',m.text,flush=True) if m.type=='error' else None)
  page.add_init_script('''let seed=12345;window.__resetParticleSeed=()=>{seed=12345};Math.random=()=>((seed=(1664525*seed+1013904223)>>>0)/4294967296);window.requestAnimationFrame=()=>0;''')
  def route(r):
   response=r.fetch(url='http://localhost:5173/tests/fixtures/r3b-pre-continuity/src/main.js') if stage=='before' else r.fetch()
   text=response.text()
   text=text.replace('const clock = new THREE.Clock();','const clock = {getElapsedTime:()=>2};').replace('const particleCount =','window.__resetParticleSeed();\nconst particleCount =')
   r.fulfill(response=response,body=text+r1.EXPOSE)
  page.route('**/src/main.js*',route)
  if stage=='before':page.route('**/src/audio-cue-timeline.js*',lambda r:r.fulfill(status=200,content_type='text/javascript',body=(BASE/'src/audio-cue-timeline.js').read_text()))
  page.goto('http://localhost:5173',wait_until='networkidle');page.wait_for_function('window.__motion');page.evaluate('window.__motion.ready')
  for t in [0,46.5,200.5]:
   page.evaluate('t=>window.__motion.reset(t)',t);page.evaluate('t=>window.__motion.frame(t)',t)
   page.screenshot(path=str(OUT/f'visual-{stage}-{t}.png'))
  page.close()
 browser.close()
for t in [0,46.5,200.5]:
 a=sha(OUT/f'visual-before-{t}.png');b=sha(OUT/f'visual-after-{t}.png')
 result['captures'].append({'time':t,'beforeSha256':a,'afterSha256':b,'identicalPng':a==b});assert a==b,t
result['pass']=True
(OUT/'visual-freeze.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('Visual freeze PASS: byte-identical visual sections and pixel-identical captures')
