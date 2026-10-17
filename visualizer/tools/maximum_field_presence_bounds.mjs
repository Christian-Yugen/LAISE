import {readFileSync,writeFileSync,mkdirSync,copyFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
export const DIAGONAL=16*Math.SQRT2;
export function envelopeHeight(width,elevation){return width*(Math.sin(elevation)+5.625/DIAGONAL*Math.cos(elevation));}
export function maximumWidth(height,elevation){return height/(Math.sin(elevation)+5.625/DIAGONAL*Math.cos(elevation));}
// Generous upper bound: no top margin, no header/metadata, listener border only.
export function frontUpperBound(width,availableHeight){
  const a=5.625/DIAGONAL;
  const elevation=Math.asin(availableHeight/width/Math.sqrt(1+a*a))-Math.atan(a);
  return {elevationDegrees:elevation*180/Math.PI,front:availableHeight-2.8*width/DIAGONAL*Math.cos(elevation)};
}
if(process.argv[1]===fileURLToPath(import.meta.url)){
 const {probe}=await import('./explore_maximum_field_presence.mjs');
 const out=new URL('../reports/v1_2br3-maximum-field-presence/',import.meta.url);
 const snapshot=JSON.parse(readFileSync(new URL('snapshot.json',out))).path;
 const main=readFileSync(snapshot+'/src/main.js','utf8');
 const candidate=main.replace('widthTarget: 0.80','widthTarget: 1').replace('Math.min(width, height) * 0.035','8');
 const root=snapshot.replace('PRE_MAXIMUM_FIELD_PRESENCE','REVIEW_CANDIDATE');mkdirSync(root+'/src',{recursive:true});
 for(const file of ['style.css','audio-motion-recovery.js','audio-cue-timeline.js','ripple-field.js'])copyFileSync(snapshot+'/src/'+file,root+'/src/'+file);
 copyFileSync(snapshot+'/index.html',root+'/index.html');
 writeFileSync(root+'/src/main.js',candidate);
 const block=candidate.slice(candidate.indexOf('const TERRAIN ='),candidate.indexOf('frameTerrain();')+15);
 const result={status:'FAIL: visual target incompatible with full-envelope separation',activeRuntimeChanged:false,candidate:root,
   formula:'H = W * (sin(theta) + 5.625 / (16*sqrt(2)) * cos(theta))',
   generousBandHeight:878,zeroMarginWidthLimit:maximumWidth(878,16*Math.PI/180),
   targets:[.92,.94,.96].map(r=>({percent:r*100,width:r*1920,heightAt16:envelopeHeight(r*1920,16*Math.PI/180),bestFrontEvenIfElevationChanges:frontUpperBound(r*1920,878)})),
   candidateMeasurements:[[1920,1080],[1600,900],[1366,768],[2560,1440]].map(([w,h])=>({w,h,...probe(w,h,block)}))};
 writeFileSync(new URL('geometric-limits.json',out),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}
