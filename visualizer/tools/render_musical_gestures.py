"""Standalone SVG audit plots in absolute signal units; no product UI changes."""
from pathlib import Path
import json,html,math
import numpy as np
from build_audio_cues import floor_position

V=Path(__file__).resolve().parents[1];OUT=V/'reports/v1_3a-musical-gesture-intelligence'
COLORS={'IMPULSE':'#e67e22','REPEATED_PULSE':'#248ac5','REPEATED_PULSE_SEQUENCE':'#2875d2',
 'SUSTAINED_TONE':'#29955b','SUSTAINED_TEXTURE':'#759a25','CRESCENDO':'#c73b91',
 'DECRESCENDO':'#7952b5','ACCELERATING_SEQUENCE':'#e54848','DECELERATING_SEQUENCE':'#986e35',
 'TREMOLO_OR_ROLL':'#b26c0d','PHRASE':'#778391','CONTINUOUS_MOTION':'#008d99','TRANSITION':'#333333'}
def esc(value):return html.escape(str(value),quote=True)
def svg_header(w,h,title):
 return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img"><title>{esc(title)}</title>',
 '<style>text{font-family:Arial,sans-serif;fill:#233344}.tick{font-size:11px}.label{font-size:13px;font-weight:bold}</style>',
 f'<rect width="{w}" height="{h}" fill="#fafcfe"/>']
def text(out,x,y,label,size=12,extra=''):out.append(f'<text x="{x}" y="{y}" font-size="{size}" {extra}>{esc(label)}</text>')
def main():
 d=json.loads((V/'public/audio/tukana-musical-gestures-v1.json').read_text(encoding='utf-8'))
 sources=[s['source'] for s in d['stemStatistics']];frames={s:np.array(json.loads((OUT/f'features/{s}.json').read_text())['rows']) for s in sources}
 rmsmax=max(float(np.max(f[:,1])) for f in frames.values());ampmax=max(a['amplitude'] for a in d['attacks'])
 plots=OUT/'timelines';plots.mkdir(exist_ok=True)
 def timeline(start,end,name):
  w=1900;left=180;right=1850;top=168;lane=114;h=top+lane*12+45
  out=svg_header(w,h,f'Tukana II musical gesture evidence {start}-{end} seconds')
  text(out,28,30,f'LAISE V1.3A | Musical Gesture Intelligence | {start:g}-{end:g} s',22)
  text(out,28,52,f'Absolute stereo RMS: common 0..{rmsmax:.5f} FS axis for every stem. No per-stem gain normalization.',13)
  text(out,28,72,'Each lane: envelope; original attacks; impulse / pulse / sustain / trend / spatial / phrase tracks. Hover gestures for evidence.',12)
  for i,(kind,color) in enumerate(COLORS.items()):
   x=28+(i%4)*460;y=94+(i//4)*17;out.append(f'<rect x="{x}" y="{y-9}" width="10" height="10" fill="{color}"/>');text(out,x+16,y,kind,10)
  def x(t):return left+(t-start)/(end-start)*(right-left)
  step=30 if end-start>60 else 5
  for tick in np.arange(math.ceil(start/step)*step,end+.001,step):
   out.append(f'<path d="M{x(tick):.3f} {top-8}V{h-30}" stroke="#d8e1e8" stroke-width="1"/>');text(out,x(tick),top-14,f'{tick:g} s',11)
  for row,source in enumerate(sources):
   y=top+row*lane;out.append(f'<rect x="10" y="{y}" width="1870" height="{lane-3}" fill="{"#edf3f8" if row%2==0 else "#ffffff"}" fill-opacity=".7"/>')
   text(out,20,y+20,source,14);stats=next(s for s in d['stemStatistics'] if s['source']==source)
   text(out,20,y+39,f'{stats["attackCount"]} attacks',11);text(out,20,y+55,f'{stats["gestureCount"]} gestures',11)
   text(out,20,y+74,f'RMS P95 {stats["rmsDistribution"]["P95"]:.5f}',10)
   f=frames[source];f=f[(f[:,0]>=start)&(f[:,0]<=end)];stride=max(1,len(f)//1600)
   # Peak-preserving downsampling only for plotting, never for classification.
   points=[]
   for i in range(0,len(f),stride):
    block=f[i:i+stride];points.append((float(np.mean(block[:,0])),float(np.max(block[:,1]))))
   path=' '.join(f'{"M" if i==0 else "L"}{x(t):.3f},{y+30-a/rmsmax*25:.3f}' for i,(t,a) in enumerate(points))
   out.append(f'<path d="{path}" fill="none" stroke="#304758" stroke-width=".8"/>')
   for a in d['attacks']:
    if a['source']==source and start<=a['time']<=end:
     out.append(f'<path d="M{x(a["time"]):.3f},{y+43}v{-max(1,9*math.sqrt(a["amplitude"]/ampmax)):.3f}" stroke="#182e44" stroke-width=".7"><title>attack {a["index"]}; {source}; {a["time"]:.4f}s; absolute RMS {a["amplitude"]}</title></path>')
   for g in d['gestures']:
    if g['source']!=source or g['endTime']<start or g['startTime']>end:continue
    kind=g['gestureType'];track=0 if kind=='IMPULSE' else 1 if kind in ['REPEATED_PULSE','REPEATED_PULSE_SEQUENCE','ACCELERATING_SEQUENCE','DECELERATING_SEQUENCE','TREMOLO_OR_ROLL'] else 2 if kind.startswith('SUSTAINED') else 3 if kind in ['CRESCENDO','DECRESCENDO'] else 4 if kind=='CONTINUOUS_MOTION' else 5
    xx=x(max(start,g['startTime']));width=max(.8,x(min(end,g['endTime']))-xx);opacity=.25+.75*math.sqrt(min(1,g['intensity']/rmsmax))
    title=f'{g["gestureId"]} | {kind} | {g["startTime"]:.3f}-{g["endTime"]:.3f}s | RMS {g["intensity"]:.6f} | confidence {g["confidence"]:.3f} | {len(g["attackRefs"])} attacks'
    out.append(f'<rect x="{xx:.3f}" y="{y+49+track*9}" width="{width:.3f}" height="7" fill="{COLORS[kind]}" opacity="{opacity:.4f}"><title>{esc(title)}</title></rect>')
   out.append(f'<path d="M{left},{y+105}H{right}" stroke="#c6d3dd" stroke-width=".5"/>')
  text(out,left,h-10,'Time in seconds. Simultaneous evidence layers may overlap; PHRASE is a temporal grouping proxy, not musicological ground truth.',11)
  out.append('</svg>');(plots/name).write_text('\n'.join(out),encoding='utf-8')
 timeline(0,330,'overview-0-330.svg')
 for start in range(0,330,30):timeline(start,start+30,f'zoom-{start:03d}-{start+30:03d}.svg')
 # Independent spatial audit: the original floor projection, never new mesh logic.
 automation=json.loads((V.parent/d['spatialTrajectoryReference']['manifest']).read_text())
 roles={r['source_id']:r for r in automation['roles']}
 spatial=svg_header(1640,1190,'T007 known spatial trajectories and measured source activity')
 text(spatial,25,30,'T007 spatial evidence | original normalized X/Z projection',23)
 text(spatial,25,55,'Gray: automation at all times. Colored dots: measured energy above the recorded activity floor. Blue = start, orange = end.',13)
 text(spatial,25,77,'Front is negative Z (up in these analysis plots); X increases right. Not a visualization/camera change.',12)
 for i,source in enumerate(sources):
  col=i%4;row=i//4;cx=210+col*405;cy=265+row*355;scale=130
  text(spatial,cx-175,cy-145,source,17)
  spatial.append(f'<rect x="{cx-scale}" y="{cy-scale}" width="{2*scale}" height="{2*scale}" fill="none" stroke="#bfccd8"/>')
  spatial.append(f'<path d="M{cx-scale} {cy}H{cx+scale}M{cx} {cy-scale}V{cy+scale}" stroke="#d3dde6" stroke-width=".8"/>')
  text(spatial,cx-22,cy-scale-8,'-Z front',10);text(spatial,cx+scale+5,cy+4,'+X',10)
  times=np.arange(0,330.001,.25);points=[floor_position(roles[source],float(t)) for t in times]
  path=' '.join(f'{"M" if j==0 else "L"}{cx+p[0]*scale:.3f},{cy+p[1]*scale:.3f}' for j,p in enumerate(points))
  spatial.append(f'<path d="{path}" fill="none" stroke="#aebbc6" stroke-width="1"/>')
  floor=next(s['activityFloor'] for s in d['stemStatistics'] if s['source']==source);f=frames[source]
  for t,p in zip(times,points):
   index=min(len(f)-1,int(round(t/.02)))
   if f[index,3]>=floor:
    r=round(25+210*t/330);g=round(110+20*t/330);b=round(220-195*t/330)
    spatial.append(f'<circle cx="{cx+p[0]*scale:.3f}" cy="{cy+p[1]*scale:.3f}" r="1.3" fill="rgb({r},{g},{b})" opacity=".5"><title>{source}; {t:.2f}s; az {p[2]:.3f}; el {p[3]:.3f}; distance {p[4]:.4f}m</title></circle>')
  text(spatial,cx-150,cy+150,f'azimuth {min(p[2] for p in points):.1f}..{max(p[2] for p in points):.1f} deg (unwrapped)',10)
 spatial.append('</svg>');(plots/'spatial-trajectories.svg').write_text('\n'.join(spatial),encoding='utf-8')
 cases=[]
 for kind in ['IMPULSE','REPEATED_PULSE_SEQUENCE','SUSTAINED_TONE','CRESCENDO','DECRESCENDO','TREMOLO_OR_ROLL']:
  candidates=[g for g in d['gestures'] if g['gestureType']==kind and g['confidence']>=.72]
  if not candidates:
   cases.append({'gestureType':kind,'found':False,'reason':'no candidate meeting confidence >=0.72'})
   (plots/f'case-{kind.lower()}.svg').unlink(missing_ok=True)
   continue
  g=sorted(candidates,key=lambda g:(-g['confidence'],-g['intensity'],-len(g['attackRefs']),g['startTime'],g['source']))[0]
  cases.append({'found':True,**g})
  start=max(0,g['startTime']-.75);end=min(330,g['endTime']+.75);f=frames[g['source']];f=f[(f[:,0]>=start)&(f[:,0]<=end)]
  w=1500;h=420;out=svg_header(w,h,g['gestureId']);text(out,30,30,f'{kind} | {g["source"]} | confidence {g["confidence"]:.3f}',21)
  text(out,30,55,f'{g["startTime"]:.3f}-{g["endTime"]:.3f} s | RMS {g["intensity"]:.6f} | {len(g["attackRefs"])} original attacks',14)
  xmax=1300;x0=90;yy=310;ymax=max(1e-8,float(np.max(f[:,1])))*1.1
  xp=lambda t:x0+(t-start)/(end-start)*(xmax-x0)
  out.append(f'<rect x="{xp(g["startTime"]):.3f}" y="90" width="{xp(g["endTime"])-xp(g["startTime"]):.3f}" height="220" fill="{COLORS[kind]}" opacity=".12"/>')
  path=' '.join(f'{"M" if i==0 else "L"}{xp(row[0]):.3f},{yy-row[1]/ymax*200:.3f}' for i,row in enumerate(f))
  out.append(f'<path d="{path}" fill="none" stroke="#203c50" stroke-width="1.5"/>')
  for frac in [0,.25,.5,.75,1]:
   text(out,12,yy-frac*200,f'{frac*ymax:.5f}',11)
   t=start+(end-start)*frac;text(out,xp(t),335,f'{t:.3f}s',11)
  for i in g['attackRefs']:
   a=d['attacks'][i];out.append(f'<path d="M{xp(a["time"]):.3f},95V310" stroke="#e67e22" opacity=".45"><title>original attack {i} at {a["time"]}s</title></path>')
  text(out,30,365,'Vertical axis: absolute stereo RMS FS (case-specific numeric axis, no signal normalization). Orange lines: original attacks.',12)
  text(out,30,389,'Classification is a feature-supported hypothesis. Full numeric and T007 trajectory evidence: cases.json.',12)
  out.append('</svg>');(plots/f'case-{kind.lower()}.svg').write_text('\n'.join(out),encoding='utf-8')
 (OUT/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
 links=''.join(f'<li><a href="timelines/zoom-{i:03d}-{i+30:03d}.svg">{i}-{i+30} s</a></li>' for i in range(0,330,30))
 case_links=''.join(f'<li><a href="timelines/case-{g["gestureType"].lower()}.svg">{g["gestureType"]}: {g["source"]} {g["startTime"]:.3f}-{g["endTime"]:.3f}s</a></li>' if g['found'] else f'<li>{g["gestureType"]}: insufficient evidence</li>' for g in cases)
 (OUT/'index.html').write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>LAISE V1.3A evidence</title><style>body{{font:16px Arial;max-width:1500px;margin:30px auto;color:#233344;background:#fafcfe}}object{{width:100%;height:1150px;border:1px solid #ddd}}ul{{display:flex;flex-wrap:wrap;gap:18px;list-style:none;padding:0}}a{{color:#176ba0}}p{{line-height:1.5}}</style><h1>LAISE V1.3A - Musical Gesture Intelligence</h1><p>Offline audit, 12 real T007 stems, 330 seconds. This is an evidence viewer, not a visualizer UI change. RMS is in absolute full-scale units. Source intensity relationships remain intact. Gesture labels and confidence are heuristic evidence, not ground truth.</p><p><a href="timelines/overview-0-330.svg">Open full 330 s SVG</a> | <a href="timelines/spatial-trajectories.svg">T007 spatial audit</a> | <a href="analysis-summary.json">Numeric results</a> | <a href="cases.json">Case evidence and trajectories</a></p><object data="timelines/overview-0-330.svg" type="image/svg+xml"></object><h2>30-second zooms</h2><ul>{links}</ul><h2>Automatically selected real cases (confidence >=0.72)</h2><ul>{case_links}</ul><p>Each source has six gesture tracks: impulse, repetition, sustain, energy trend, spatial motion, phrase. Hover SVG rectangles for time/intensity/confidence/attack identity. Classification overlaps are explicit evidence layers; the future behavior engine must resolve salience. No mesh behavior is produced here.</p></html>''',encoding='utf-8')
 print(f'Plots: overview + 11 zooms + {sum(g["found"] for g in cases)} real case plots -> {OUT}',flush=True)
if __name__=='__main__':main()
