"""V1.3A audits V1.2 playback and rendering without modifying product modules."""
from pathlib import Path
import json,hashlib
from playwright.sync_api import sync_playwright
import validate_playback_continuity as continuity
import continuity_visual_probe

V=Path(__file__).resolve().parents[1]
OUT=V/'reports/v1_3a-musical-gesture-intelligence'
def captures(browser):
 page=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
 page.add_init_script('let seed=12345;window.__resetParticleSeed=()=>{seed=12345};Math.random=()=>((seed=(1664525*seed+1013904223)>>>0)/4294967296);window.requestAnimationFrame=()=>0;')
 def route(r):
  response=r.fetch();s=response.text().replace('const clock = new THREE.Clock();','const clock = {getElapsedTime:()=>2};').replace('const particleCount =','window.__resetParticleSeed();\nconst particleCount =')
  r.fulfill(response=response,body=s+continuity_visual_probe.EXPOSE)
 page.route('**/src/main.js*',route);page.goto('http://localhost:5173',wait_until='networkidle')
 page.wait_for_function('window.__motion');page.evaluate('window.__motion.ready')
 rows=[]
 for t in [0,46.5,200.5]:
  page.evaluate('t=>window.__motion.reset(t)',t);page.evaluate('t=>window.__motion.frame(t)',t)
  p=OUT/f'v13a-{t}.png';page.screenshot(path=str(p))
  old=V/f'reports/v1_2br3b_r1-playback-continuity/visual-after-{t}.png'
  a=hashlib.sha256(old.read_bytes()).hexdigest();b=hashlib.sha256(p.read_bytes()).hexdigest()
  rows.append({'time':t,'v12Sha256':a,'v13aSha256':b,'pixelIdentical':a==b});assert a==b,t
 (OUT/'pixel-regression.json').write_text(json.dumps(rows,indent=2));page.close()
if __name__=='__main__':
 OUT.mkdir(exist_ok=True)
 with sync_playwright() as p:
  browser=p.chromium.launch(channel='chrome',headless=True,args=['--mute-audio'])
  captures(browser)
  continuity.OUT=OUT
  continuity.run(browser,'v13a')
  browser.close()
