"""Standalone V1.3B audit: SVGs plus a local, embedded-data window inspector."""
from pathlib import Path
import json,html,math
import numpy as np
from render_musical_gestures import svg_header,text,esc

V=Path(__file__).resolve().parents[1];OUT=V/'reports/v1_3b-musical-salience-arbitration'
ROLE_COLORS=['#e1e7ec','#80b4d3','#efac45','#c93c45']
def render():
 d=json.loads((V/'public/audio/tukana-musical-visual-intents-v1.json').read_text(encoding='utf-8'))
 a=json.loads((V/'public/audio/tukana-musical-gestures-v1.json').read_text(encoding='utf-8'))
 frames=d['frames'];values=np.array([f['values'] for f in frames]);times=np.array([f['startTime'] for f in frames]);sources=d['sourceOrder']
 order=[s['source'] for s in a['stemStatistics']];plots=OUT/'timelines';plots.mkdir(exist_ok=True)
 maxrms=max(1e-12,float(np.max(values[:,:,0])));maxscore=max(1e-12,float(np.max(values[:,:,5])));maxrel=max(1e-12,float(np.max(values[:,:,1:3])))
 def timeline(start,end,name,title):
  width=1900;left=180;right=1850;top=160;lane=126;height=top+12*lane+145
  out=svg_header(width,height,title);text(out,25,30,f'LAISE V1.3B | {title} | {start:.2f}-{end:.2f} s',22)
  text(out,25,54,f'Absolute RMS (gray), common 0..{maxrms:.6f} FS. Salience (purple), common 0..{maxscore:.3f}. No per-source gain.',13)
  text(out,25,74,'Orange: source-relative; dashed slate: track-relative (shared log1p axis, diagnostic only). These curves DO NOT set priority.',12)
  text(out,25,94,'Roles: red dominant / gold secondary / blue supporting / gray background. Blue bars: V1.3A descriptions. Green: fused intents.',12)
  text(out,25,114,'50 ms analysis windows are evidence, not a playback schedule. Exact cue and gesture timestamps remain in the JSON.',12)
  x=lambda t:left+(t-start)/(end-start)*(right-left)
  selected=np.flatnonzero((times>=start)&(times<end));step=30 if end-start>60 else 5 if end-start>=20 else 1
  for tick in np.arange(math.ceil(start/step)*step,end+.0001,step):
   xx=x(tick);out.append(f'<path d="M{xx:.3f} {top-15}V{height-38}" stroke="#dce5ed" stroke-width=".7"/>');text(out,xx,top-20,f'{tick:g}s',10)
  for row,source in enumerate(order):
   j=sources.index(source);y=top+row*lane
   out.append(f'<rect x="8" y="{y}" width="1875" height="{lane-3}" fill="{"#eaf1f7" if row%2==0 else "#ffffff"}" fill-opacity=".7"/>')
   count=sum(i['source']==source for i in d['intents']);gcount=sum(g['source']==source for g in a['gestures']);text(out,20,y+18,source,14)
   text(out,20,y+39,f'{gcount} gestures',11);text(out,20,y+56,f'{count} intents',11)
   text(out,20,y+76,'RMS / salience / relative',9);text(out,20,y+94,'roles / gestures / intents',9)
   stride=max(1,len(selected)//1500)
   for col,offset,scale,color,transform,dashed in [(0,29,maxrms,'#536675',False,False),(5,55,maxscore,'#8552ad',False,False),(1,78,math.log1p(maxrel),'#cf831c',True,False),(2,78,math.log1p(maxrel),'#536675',True,True)]:
    points=[]
    for pos in range(0,len(selected),stride):
     indices=selected[pos:pos+stride];value=float(np.max(values[indices,j,col]));value=math.log1p(value) if transform else value
     points.append((float(np.mean(times[indices])),y+offset-value/scale*21))
    path=' '.join(f'{"M" if k==0 else "L"}{x(t):.3f},{yy:.3f}' for k,(t,yy) in enumerate(points))
    dash=' stroke-dasharray="3,2"' if dashed else '';out.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1"{dash}/>')
   # Run-length encode roles instead of emitting 79,200 nearly identical boxes.
   if len(selected):
    first=int(selected[0]);last=first;role=int(values[first,j,9])
    for i in list(selected[1:])+[int(selected[-1])+1]:
     current=int(values[i,j,9]) if i<len(times) and i in selected else -1
     if current!=role:
      l=max(start,times[first]);r=min(end,times[last]+.05)
      out.append(f'<rect x="{x(l):.3f}" y="{y+83}" width="{max(.5,x(r)-x(l)):.3f}" height="7" fill="{ROLE_COLORS[role]}"><title>{source}: {d["roleCodes"][role]} {l:.3f}-{r:.3f}s</title></rect>');first=i;role=current
     last=i
   for g in a['gestures']:
    if g['source']==source and g['endTime']>=start and g['startTime']<=end:
     l=max(start,g['startTime']);r=min(end,g['endTime']);out.append(f'<rect x="{x(l):.3f}" y="{y+95}" width="{max(.6,x(r)-x(l)):.3f}" height="5" fill="#3d8fb6" opacity=".3"><title>{esc(g["gestureId"])} {g["gestureType"]}</title></rect>')
   for intent in d['intents']:
    if intent['source']==source and intent['endTime']>=start and intent['startTime']<=end:
     l=max(start,intent['startTime']);r=min(end,intent['endTime']);out.append(f'<rect x="{x(l):.3f}" y="{y+106}" width="{max(.8,x(r)-x(l)):.3f}" height="7" fill="#238968"><title>{esc(intent["intentId"])} {intent["temporalBehavior"]}; {len(intent["gestureRefs"])} gestures; {len(intent["attackRefs"])} attacks</title></rect>')
  y=top+12*lane+30;text(out,20,y,'Concurrency',13);scale=max(f['activeGestures'] for f in frames)
  for key,color in [('activeGestures','#438ab5'),('activeVisualIntents','#238968'),('dominantCount','#c93c45')]:
   points=[(times[i],y+65-frames[i][key]/scale*60) for i in selected[::max(1,len(selected)//1600)]]
   path=' '.join(f'{"M" if k==0 else "L"}{x(t):.3f},{yy:.3f}' for k,(t,yy) in enumerate(points));out.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.1"/>')
  text(out,left,height-12,'Blue: gesture descriptions; green: causal intent drivers; red: dominant sources. No music/attack is removed.',11);out.append('</svg>')
  (plots/name).write_text('\n'.join(out),encoding='utf-8')
 timeline(0,330,'overview-0-330.svg','Full-track salience and semantic arbitration')
 for start in range(0,330,30):timeline(start,start+30,f'zoom-{start:03d}-{start+30:03d}.svg','30-second audit zoom')
 energy=np.sum(values[:,:,0]**2,axis=1);eligible=np.array([len(f['activeSources'])>0 for f in frames]);quiet=int(np.flatnonzero(eligible)[np.argmin(energy[eligible])])
 dense=max(range(len(frames)),key=lambda i:(frames[i]['activeGestures'],len(frames[i]['activeSources'])))
 selections={'dense':dense,'quiet':quiet,'percussion':int(np.argmax(values[:,sources.index('percussion'),0])),
 'bass-dense':max(range(len(frames)),key=lambda i:sum(a0['source']=='bass' and times[i]-.25<=a0['time']<times[i]+.05 for a0 in a['attacks'])),
 'strings':int(np.argmax(values[:,sources.index('strings'),0])),'synth':int(np.argmax(values[:,sources.index('synth'),0]))}
 for label,kind,source in [('vocal-sustain','SUSTAINED_TONE','lead_vocal'),('crescendo','CRESCENDO',None),('decrescendo','DECRESCENDO',None),('roll','TREMOLO_OR_ROLL',None)]:
  candidates=[g for g in a['gestures'] if g['gestureType']==kind and (source is None or g['source']==source)]
  if candidates:
   g=max(candidates,key=lambda g:(g['confidence'],g['intensity']));selections[label]=min(len(frames)-1,int(g['peakTime']/.05))
 cases=[]
 for label,index in selections.items():
  center=min(325,max(5,times[index]));start=max(0,center-5);end=min(330,center+5);name=f'case-{label}.svg';timeline(start,end,name,label)
  f=frames[index];cases.append({'case':label,'frameIndex':index,'time':f['startTime'],'startTime':float(start),'endTime':float(end),
   'activeSources':f['activeSources'],'activeGestures':f['activeGestures'],'activeVisualIntents':f['activeVisualIntents'],'dominantCount':f['dominantCount'],
   'ranking':sorted([{'source':s,'absoluteIntensity':f['values'][j][0],'sourceRelativeIntensity':f['values'][j][1],
       'trackRelativeIntensity':f['values'][j][2],'localContextIntensity':f['values'][j][3],'musicalSalience':f['values'][j][5],
       'role':d['roleCodes'][f['values'][j][9]]} for j,s in enumerate(sources)],key=lambda r:(-r['musicalSalience'],r['source'])),
   'intentIds':f['activeIntentIds'],'figure':'timelines/'+name})
 (OUT/'cases-real.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
 # Self-contained data allows the inspector to work via file:// as well as Vite.
 embedded={'sources':sources,'roles':d['roleCodes'],'frames':[{'v':[[row[k] for k in [0,1,2,3,5,9]] for row in f['values']],
  'g':f['activeGestures'],'i':f['activeVisualIntents'],'d':f['dominantCount'],'ids':f['activeIntentIds']} for f in frames],
  'intents':[{k:e[k] for k in ['intentId','source','startTime','endTime','primaryGesture','gestureRefs','attackRefs','classificationConfidence','reason']} for e in d['intents']]}
 links=''.join(f'<a href="timelines/zoom-{s:03d}-{s+30:03d}.svg">{s}-{s+30}s</a> ' for s in range(0,330,30))
 cases_links=''.join(f'<li><a href="{c["figure"]}">{esc(c["case"])}: {c["time"]:.2f}s</a></li>' for c in cases)
 page='''<!doctype html><html lang="en"><meta charset="utf-8"><title>LAISE V1.3B offline salience audit</title><style>body{font:15px Arial;max-width:1600px;margin:25px auto;color:#243747;background:#fafcfe}a{color:#176a99}p{line-height:1.5}table{border-collapse:collapse;width:100%}td,th{text-align:right;border-bottom:1px solid #dbe3ea;padding:7px}td:first-child,th:first-child{text-align:left}input{width:80%}object{width:100%;height:1250px}pre{max-height:330px;overflow:auto;background:#eaf1f6;padding:15px;white-space:pre-wrap}li{display:inline-block;margin-right:20px}.dominant{background:#fbe0e0}.secondary{background:#fff1d8}</style><h1>LAISE V1.3B - Musical Salience & Arbitration</h1><p>Standalone analytical evidence. No product renderer, physics or headroom changes. Confidence describes a heuristic classification; it is not intensity. Source-relative values are diagnostic, never gain. Exact attacks and all V1.3A descriptions remain traceable.</p><p><a href="timelines/overview-0-330.svg">Full 330-second SVG</a> | <a href="analysis-summary.json">Metrics</a> | <a href="sensitivity.json">Weight sensitivity</a> | <a href="intensity-distributions.json">Absolute distributions</a></p><h2>Window inspector (50 ms)</h2><input id="time" type="range" min="0" max="329.95" step="0.05" value="124.75"><output id="timeLabel"></output><p id="counts"></p><table><thead><tr><th>Source</th><th>Absolute RMS FS</th><th>Source-relative</th><th>Track-relative</th><th>Local context</th><th>Salience</th><th>Role</th></tr></thead><tbody id="rows"></tbody></table><p>Click a source to inspect active intent → V1.3A gestures → original attack indices → source/T007. A window is a coarse analysis interval, not a new playback clock.</p><pre id="trace"></pre><h2>Full-track evidence</h2><object data="timelines/overview-0-330.svg" type="image/svg+xml"></object><h2>30-second zooms</h2><p>LINKS</p><h2>Automatically selected review regions</h2><ul>CASES</ul><script>const DATA=EMBED;
const ids=new Map(DATA.intents.map(i=>[i.intentId,i]));let selected=null;
function show(){const idx=Math.min(DATA.frames.length-1,Math.floor(Number(document.querySelector('#time').value)/.05+1e-6));const f=DATA.frames[idx];document.querySelector('#timeLabel').textContent=(idx*.05).toFixed(2)+' - '+((idx+1)*.05).toFixed(2)+' s';document.querySelector('#counts').textContent=f.g+' gesture descriptions; '+f.i+' intent drivers; '+f.d+' dominant sources';const rows=DATA.sources.map((s,j)=>({s,v:f.v[j]})).sort((a,b)=>b.v[4]-a.v[4]||a.s.localeCompare(b.s));document.querySelector('#rows').innerHTML=rows.map(r=>'<tr class="'+DATA.roles[r.v[5]]+'" data-source="'+r.s+'"><td>'+r.s+'</td><td>'+r.v[0].toExponential(5)+'</td><td>'+r.v[1].toFixed(4)+'</td><td>'+r.v[2].toFixed(4)+'</td><td>'+r.v[3].toFixed(4)+'</td><td>'+r.v[4].toFixed(6)+'</td><td>'+DATA.roles[r.v[5]]+'</td></tr>').join('');document.querySelectorAll('[data-source]').forEach(row=>row.onclick=()=>{selected=row.dataset.source;show()});const active=f.ids.map(id=>ids.get(id)).filter(i=>!selected||i.source===selected);document.querySelector('#trace').textContent=JSON.stringify(active,null,2)}document.querySelector('#time').oninput=show;show();</script></html>'''
 page=page.replace('LINKS',links).replace('CASES',cases_links).replace('EMBED',json.dumps(embedded,separators=(',',':'),allow_nan=False))
 (OUT/'index.html').write_text(page,encoding='utf-8');print('V1.3B offline viewer, overview, 11 zooms and 10 targeted cases rendered',flush=True)
if __name__=='__main__':render()
