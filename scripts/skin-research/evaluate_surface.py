"""Engineering evaluation on actual licensed scan captures, not clinical truth.
Compares pinned MIT oiliness baseline on the same valid sampled skin mask.
Exposure perturbations are software sensitivity tests, never sweat/cream tests.
"""
import argparse, base64, hashlib, importlib.util, io, json, subprocess
from pathlib import Path
import cv2, numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
NODE=r'''
const fs=require('fs'),ts=require('typescript'),Module=require('module');
const m=new Module('surface',module);m.paths=module.paths;
m._compile(ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/skinSurfaceAnalysis.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,'surface');
const input=JSON.parse(fs.readFileSync(process.argv[1],'utf8')),S=m.exports;
const rows=input.map(v=>{v.pixels=new Uint8ClampedArray(Buffer.from(v.pixels,'base64'));v.mesh=v.meshes[v.region];const before=Buffer.from(v.pixels);const t=performance.now(),g=S.analyzeSurface(v,true),v1ms=performance.now()-t;const t2=performance.now(),v2=S.analyzeRelativeShine(v);if(!before.equals(Buffer.from(v.pixels)))throw Error('SOURCE_MUTATED');return {...g,valid:Array.from(g.valid),redness:Array.from(g.redness),shine:Array.from(g.shine),ms:v1ms,relative:{...v2,valid:Array.from(v2.valid),redness:undefined,shine:Array.from(v2.shine),ms:performance.now()-t2}};});
process.stdout.write(JSON.stringify(rows));
'''

def color(value):
 t=np.clip(value,0,1);return np.stack((np.round(54-40*t),np.round(228-100*t),np.round(241-95*t),np.round(255*.32*t)),axis=-1).astype('uint8')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--captures',default='audit-results/skin-capabilities-20261008/product');ap.add_argument('--out',default='audit-results/skin-capabilities-20261008/surface');args=ap.parse_args()
 capture=(ROOT/args.captures).resolve();out=(ROOT/args.out).resolve();assert capture.is_relative_to(ROOT/'audit-results') and out.is_relative_to(ROOT/'audit-results');out.mkdir(parents=True,exist_ok=True)
 baseline=ROOT/'audit-results/skin-capabilities-20261008/sources/skin-scan/src/pipeline/maps/oiliness.py'
 assert hashlib.sha256(baseline.read_bytes()).hexdigest()=='b80d78c6e0701a70052b3e5a6a5866c4427e9a70a868cf4aa7031dbb8597e814'
 spec=importlib.util.spec_from_file_location('licensed_oiliness',baseline);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 inputs=[];sources=[]
 for file in sorted(capture.glob('source-*.json')):
  meta=json.loads(file.read_text());region=meta['region'];source=np.array(Image.open(file.with_suffix('.png')).convert('RGBA'))
  assert hashlib.sha256(source.tobytes()).hexdigest()==meta['photoId']
  for name,gains in [('original',(1,1,1)),('exposure-0.8',(.8,.8,.8)),('exposure-1.2',(1.2,1.2,1.2)),('warm-cast',(1.08,1,.92))]:
   pixels=source.copy();pixels[:,:,:3]=np.clip(source[:,:,:3]*np.array(gains),0,255).astype('uint8')
   inputs.append({**meta,'pixels':base64.b64encode(pixels.tobytes()).decode()});sources.append((file.stem,name,pixels))
 private_input=out/'evaluation-input-private.json';private_input.write_text(json.dumps(inputs),'utf8')
 try:
  result=subprocess.run(['node','-e',NODE,str(private_input)],cwd=ROOT,text=True,capture_output=True,encoding='utf8')
  if result.returncode:raise RuntimeError('Local surface evaluator failed: '+result.stderr[:1500])
 finally:private_input.unlink(missing_ok=True)
 grids=json.loads(result.stdout);reports=[];checks=0;compared_maps=0
 for meta,grid,(name,challenge,source) in zip(inputs,grids,sources):
  h,w=grid['height'],grid['width'];valid=np.array(grid['valid'],dtype='uint8').reshape(h,w)>0
  value=np.array(grid['shine']).reshape(h,w);red=np.array(grid['redness']).reshape(h,w);ys=np.minimum(source.shape[0]-1,grid['y']+np.arange(h)*grid['step']+grid['step']//2);xs=np.minimum(source.shape[1]-1,grid['x']+np.arange(w)*grid['step']+grid['step']//2)
  # Baseline is computed on its original image domain; sample the same skin denominator.
  bgr=cv2.cvtColor(source,cv2.COLOR_RGBA2BGR);base=mod.oiliness_map(bgr,{'evaluation-domain':np.ones(source.shape[:2],dtype='uint8')});sample=base[np.ix_(ys,xs)]>0
  assert not np.any(value[~valid]) and not np.any(red[~valid]);assert int(valid.sum())==grid['validSamples'];assert int(((value>=.15)&valid).sum())==grid['shineSamples']
  checks+=1
  relative=grid['relative'];v2=np.array(relative['shine']).reshape(h,w)
  assert np.array_equal(np.array(relative['valid']).reshape(h,w)>0,valid)
  assert not np.any(v2[~valid]) and int(((v2>=.15)&valid).sum())==relative['shineSamples']
  reports.append({'capture':name,'region':meta['region'],'pose':meta['pose'],'photoId':meta['photoId'],'challenge':challenge,'validSampleDenominator':grid['validSamples'],'candidateSampleNumerator':grid['shineSamples'],'candidateAreaPercent':grid['shineAreaPercent'],'unavailableReason':grid['shineUnavailable'],'baselineCandidateAreaPercent':100*int((sample&valid).sum())/max(1,int(valid.sum())),'clippedFraction':grid['clippedFraction'],'analysisMs':grid['ms'],'grid':{'width':w,'height':h,'step':grid['step']},'knownTypedArrayBytes':grid['allocatedBytes']})
  reports[-1]['relativeV2']={'areaPercent':relative['shineAreaPercent'],'numerator':relative['shineSamples'],'denominator':relative['validSamples'],'unavailable':relative['shineUnavailable'],'ms':relative['ms'],'knownArrayBytes':relative['allocatedBytes']}
  if challenge=='original' and meta['region']!='periorbital':
   rgba=color(value);rgba[~valid]=0;Image.fromarray(rgba).save(out/(name+'-shine-map.png'))
   rgba=color(v2);rgba[~valid]=0;Image.fromarray(rgba).save(out/(name+'-relative-v2-map.png'))
  mapping_file=capture/('map-'+name.removeprefix('source-')+'.json')
  if challenge=='original' and meta['region']!='periorbital' and mapping_file.exists():
   actual=json.loads(mapping_file.read_text());assert actual['width']==w and actual['height']==h and actual['step']==grid['step']
   actual_values=np.array(actual['values']);actual_mask=np.array(actual['valid']);assert np.allclose(actual_values,red.ravel(),atol=1e-5) and np.array_equal(actual_mask,valid.ravel()*255)
   png=np.array(Image.open(io.BytesIO(base64.b64decode(actual['rgba'].split(',')[1]))).convert('RGBA'));maskpng=np.array(Image.open(io.BytesIO(base64.b64decode(actual['mask'].split(',')[1]))).convert('RGBA'))
   expected=color(red/100);expected[~valid|(red<=0)]=0
   # Canvas premultiplied-alpha encoding can round RGB; alpha is exact.
   assert np.array_equal(png[:,:,3],expected[:,:,3]);assert np.all(png[:,:,3][~valid]==0);assert np.array_equal(maskpng[:,:,3],actual_mask.reshape(h,w))
   points=source[np.ix_(ys,xs)][:,:,:3].astype(float);raw=np.clip((2*points[:,:,0]-points[:,:,1]-points[:,:,2])/255*100,0,100)
   assert np.allclose(red[valid],raw[valid],atol=1e-5);checks+=1;compared_maps+=1
 summary={'engineeringChecksPassed':checks,'clinicalAcceptance':False,'method':'surface-specular-candidate-v1','denominator':'valid grid sample count; area approximation on fixed equal-area source grid, not sebum amount','baseline':'MIT skin-scan pinned HSV/Sobel morphological candidate union','sourcePixelsUnchanged':True,'actualProductRednessMapsVerified':compared_maps,'noPerImageMinMax':True,'physicalSweatCreamMakeupTrials':False,'independentSkinToneExpertLabels':False,'repeatedFixture':'repeated licensed stored frames are not independent physical repeat captures','missing':['expert-labelled reflection vs diffuse light/sweat/cream/makeup','independent physical repeats across skin tones and camera/exposure conditions','beard/makeup segmentation validation'],'rows':reports}
 (out/'report.json').write_text(json.dumps(summary,indent=2),'utf8');print(json.dumps({k:v for k,v in summary.items() if k!='rows'}))

if __name__=='__main__':main()
