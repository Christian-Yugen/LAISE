"""Reuse frozen V1.3A capture/playback harness in a separate V1.3B audit output."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
import validate_gesture_v12_regression as approved
OUT=Path(__file__).resolve().parents[1]/'reports/v1_3b-musical-salience-arbitration'
if __name__=='__main__':
 OUT.mkdir(exist_ok=True);approved.OUT=OUT;approved.continuity.OUT=OUT
 with sync_playwright() as p:
  browser=p.chromium.launch(channel='chrome',headless=True,args=['--mute-audio'])
  approved.captures(browser)
  rows=json.loads((OUT/'pixel-regression.json').read_text())
  for row in rows:row['v13bSha256']=row.pop('v13aSha256')
  (OUT/'pixel-regression.json').write_text(json.dumps(rows,indent=2))
  for t in [0,46.5,200.5]:(OUT/f'v13a-{t}.png').rename(OUT/f'v13b-{t}.png')
  approved.continuity.run(browser,'v13b');browser.close()
