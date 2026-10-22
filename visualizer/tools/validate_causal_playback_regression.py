"""Isolated R1 evidence; product capture/playback harness remains unchanged."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
import validate_gesture_v12_regression as approved
OUT=Path(__file__).resolve().parents[1]/'reports/v1_3br1-causal-eligibility'
if __name__=='__main__':
 OUT.mkdir(exist_ok=True);approved.OUT=OUT;approved.continuity.OUT=OUT
 with sync_playwright() as p:
  browser=p.chromium.launch(channel='chrome',headless=True,args=['--mute-audio'])
  approved.captures(browser)
  rows=json.loads((OUT/'pixel-regression.json').read_text())
  for row in rows:row['v13br1Sha256']=row.pop('v13aSha256')
  (OUT/'pixel-regression.json').write_text(json.dumps(rows,indent=2))
  for t in [0,46.5,200.5]:(OUT/f'v13a-{t}.png').rename(OUT/f'v13br1-{t}.png')
  approved.continuity.run(browser,'v13br1');browser.close()
