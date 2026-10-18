"""Same accepted public pixels, real model, controlled local alternatives.
This diagnostic is separate from production UI and personal user acceptance.
"""
import base64, json, subprocess, time
from pathlib import Path
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT=Path.cwd(); OLD=ROOT/'audit-results/user-followup-20261005'; OUT=ROOT/'audit-results/remediation-20261005/comparison'
OUT.mkdir(parents=True,exist_ok=True)
UTIL=ROOT/'apps/vehicle-app/src/utils'
for name in ['skinAnalyzer','skinMultiAngle','skinMesh','skinSnapshot','skinMatte']:
    source=(UTIL/(name+'.ts')).read_text(encoding='utf-8')
    (OUT/(name+'.ts')).write_text(source,encoding='utf-8')
(OUT/'oldSkinSnapshot.ts').write_bytes(subprocess.check_output(['git','show','d1e19fa:apps/vehicle-app/src/utils/skinSnapshot.ts']))
compiler=r"""const fs=require('fs'),ts=require('typescript');const dir=process.argv[1];for(const file of fs.readdirSync(dir).filter(f=>f.endsWith('.ts'))){let s=ts.transpileModule(fs.readFileSync(dir+'/'+file,'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;s=s.replaceAll("from '@mediapipe/tasks-vision'","from 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/+esm'");s=s.replace(/from '(\.\/[^']+)'/g,"from '$1.js'");fs.writeFileSync(dir+'/'+file.replace('.ts','.js'),s);}"""
subprocess.run(['node','-e',compiler,str(OUT)],check=True)
samples=[('digital-front','digital-detail',0),('film-front','high-detail',0),('video-front','low-detail',0),('video-left','low-detail',2),('video-right','low-detail',1)]
proof=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--enable-precise-memory-info'])
    page=browser.new_page(viewport={'width':1800,'height':900})
    page.route('**/matte-probe',lambda r:r.fulfill(body='<html><canvas id="source"></canvas><main></main></html>',content_type='text/html'))
    page.route('**/*.js',lambda r:r.fulfill(path=str(OUT/r.request.url.rsplit('/',1)[1]),content_type='text/javascript') if (OUT/r.request.url.rsplit('/',1)[1]).exists() else r.continue_())
    page.route('**/models/selfie_multiclass_256x256.tflite',lambda r:r.fulfill(path=str(ROOT/'apps/vehicle-app/public/models/selfie_multiclass_256x256.tflite')))
    page.route('**/models/hair_segmenter.tflite',lambda r:r.fulfill(path=str(ROOT/'audit-fixtures/hair_segmenter.tflite')))
    page.route('**/source.png*',lambda r:r.fulfill(path=str(current_source),content_type='image/png'))
    page.goto('http://localhost:3000/matte-probe')
    load=page.evaluate('''async()=>{const t=performance.now();window.V=await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/+esm');window.S=await import('./skinSnapshot.js');window.O=await import('./oldSkinSnapshot.js');window.R=await import('./skinMatte.js');window.model=await V.ImageSegmenter.createFromOptions(await V.FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm'),{baseOptions:{modelAssetPath:'/models/selfie_multiclass_256x256.tflite',delegate:'CPU'},runningMode:'IMAGE',outputCategoryMask:true,outputConfidenceMasks:true});return performance.now()-t;}''')
    hair_load=page.evaluate('''async()=>{const t=performance.now();window.hairModel=await V.ImageSegmenter.createFromOptions(await V.FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm'),{baseOptions:{modelAssetPath:'/models/hair_segmenter.tflite',delegate:'CPU'},runningMode:'IMAGE',outputCategoryMask:true,outputConfidenceMasks:true});return performance.now()-t;}''')
    for label,kind,index in samples:
        current_source=OLD/kind/f'accepted-original-1-{index}.png'
        alignment=json.loads((OLD/kind/f'accepted-landmarks-1-{index}.json').read_text())
        result=page.evaluate('''async({alignment,label})=>{
          const im=new Image();im.src='/source.png?'+label;await im.decode();const c=document.querySelector('canvas');c.width=im.width;c.height=im.height;const ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(im,0,0);const rgb=ctx.getImageData(0,0,c.width,c.height),start=performance.now(),res=model.segment(c),elapsedMs=performance.now()-start;
          const categories=new Uint8Array(res.categoryMask.getAsUint8Array()),conf=res.confidenceMasks,confidence=new Float32Array(categories.length),faceConfidence=new Float32Array(conf[3].getAsFloat32Array()),neckConfidence=new Float32Array(conf[2].getAsFloat32Array());const hair=new Float32Array(conf[1].getAsFloat32Array());for(let i=0;i<confidence.length;i++)confidence[i]=Math.min(1,hair[i]+faceConfidence[i]);const mask={width:res.categoryMask.width,height:res.categoryMask.height,categories,confidence,faceConfidence,neckConfidence,elapsedMs};res.close();
          const oldStart=performance.now(),baseline=O.headAlpha(mask,alignment,c.width,c.height),oldMs=performance.now()-oldStart,newStart=performance.now(),compact=S.compactSkinMask(mask.width,mask.height,categories,hair,faceConfidence,neckConfidence),coarse=S.headAlpha(compact,alignment,c.width,c.height),newMs=performance.now()-newStart,methods={baseline:{...baseline,elapsedMs:oldMs},taper:{...coarse,elapsedMs:newMs}};
          for(const method of ['guided','color']){const refined=R.refineSkinMatte(rgb.data,coarse.alpha,c.width,c.height,256,method);for(let y=Math.ceil(alignment.landmarks[152].y*c.height);y<c.height;y++)for(let x=0;x<c.width;x++)refined.alpha[y*c.width+x]=coarse.alpha[y*c.width+x];methods[method]=refined;}
          const hairStart=performance.now(),hairRes=hairModel.segment(c),hairMs=performance.now()-hairStart,hair512=hairRes.confidenceMasks[1].getAsFloat32Array(),combinedCategories=new Uint8Array(categories),combinedConfidence=new Float32Array(confidence);
          for(let i=0;i<categories.length;i++){if(categories[i]===1)combinedCategories[i]=0;if(hair512[i]>.5)combinedCategories[i]=1;combinedConfidence[i]=Math.min(1,faceConfidence[i]+hair512[i]);}
          const higher=S.headAlpha({...mask,categories:combinedCategories,confidence:combinedConfidence},alignment,c.width,c.height),hairRefined=R.refineSkinMatte(rgb.data,higher.alpha,c.width,c.height,512);
          for(let y=Math.ceil(alignment.landmarks[152].y*c.height);y<c.height;y++)for(let x=0;x<c.width;x++){const i=y*c.width+x;hairRefined.alpha[i]=higher.alpha[i];}
          methods.hair512={...hairRefined,hairInferenceMs:hairMs};hairRes.close();
          const tensorCanvas=document.createElement('canvas');tensorCanvas.width=256;tensorCanvas.height=256;const tensorCtx=tensorCanvas.getContext('2d');const tensorStart=performance.now();tensorCtx.drawImage(c,0,0,256,256);const tensorResult=model.segment(tensorCanvas),tensorInferenceMs=performance.now()-tensorStart;
          const tensorMask=tensorResult.categoryMask,tensorConf=tensorResult.confidenceMasks,tensorCompact=S.compactSkinMask(tensorMask.width,tensorMask.height,tensorMask.getAsUint8Array(),tensorConf[1].getAsFloat32Array(),tensorConf[3].getAsFloat32Array(),tensorConf[2].getAsFloat32Array());tensorResult.close();
          let agreeing=0,confidenceError=0;for(let i=0;i<compact.categories.length;i++){if(compact.categories[i]===tensorCompact.categories[i])agreeing++;confidenceError+=Math.abs(compact.confidence[i]-tensorCompact.confidence[i]);}
          const tensorCoarse=S.headAlpha(tensorCompact,alignment,c.width,c.height),tensorRefined=R.refineSkinMatte(rgb.data,tensorCoarse.alpha,c.width,c.height,256);
          for(let y=Math.ceil(alignment.landmarks[152].y*c.height);y<c.height;y++)for(let x=0;x<c.width;x++)tensorRefined.alpha[y*c.width+x]=tensorCoarse.alpha[y*c.width+x];
          methods.tensor256={...tensorRefined,inferenceMs:tensorInferenceMs,categoryAgreement:agreeing/compact.categories.length,confidenceMAE:confidenceError/compact.categories.length,maskWidth:tensorCompact.width,maskHeight:tensorCompact.height};
          const results={};for(const [name,m] of Object.entries(methods)){const output=document.createElement('canvas');output.width=c.width;output.height=c.height;const pixels=new ImageData(new Uint8ClampedArray(rgb.data),c.width,c.height);for(let i=0;i<m.alpha.length;i++)pixels.data[i*4+3]=m.alpha[i];output.getContext('2d').putImageData(pixels,0,0);results[name]={png:output.toDataURL(),elapsedMs:m.elapsedMs,hairInferenceMs:m.hairInferenceMs,inferenceMs:m.inferenceMs,categoryAgreement:m.categoryAgreement,confidenceMAE:m.confidenceMAE,maskWidth:m.maskWidth,maskHeight:m.maskHeight,changedPixels:m.changedPixels,unknownPixels:m.unknownPixels,workingBytes:m.workingBytes};}
          const angle=label==='video-left'?'LEFT':label==='video-right'?'RIGHT':'FRONT';window.snapshot=S.snapshotSkinFrame(c,alignment,angle,{...tensorCompact,alpha:methods.tensor256.alpha});return {width:c.width,height:c.height,maskWidth:mask.width,maskHeight:mask.height,inferenceMs:elapsedMs,heap:performance.memory?.usedJSHeapSize,results,snapshot};
        }''',{'alignment':alignment,'label':label})
        for method,data in result['results'].items():
            path=OUT/f'{label}-{method}.png';path.write_bytes(base64.b64decode(data.pop('png').split(',')[1]));orig=Image.open(current_source).convert('RGB');masked=Image.open(path).convert('RGBA')
            opaque=masked.getchannel('A').point(lambda a:255 if a==255 else 0)
            assert ImageChops.multiply(ImageChops.difference(orig,masked.convert('RGB')),Image.merge('RGB',[opaque]*3)).getbbox() is None,'Opaque source RGB must be unchanged'
        snapshot=result.pop('snapshot');(OUT/f'{label}-snapshot.json').write_text(json.dumps({k:v for k,v in snapshot.items() if k!='dataUrl'}),encoding='utf-8')
        assert not snapshot.get('visualError'),snapshot.get('visualError')
        (OUT/f'{label}-landmarks.json').write_text(json.dumps(alignment),encoding='utf-8')
        # Original-size alpha PNGs plus a browser-rendered anatomy gallery.
        for region,mesh in snapshot['meshes'].items():
            x,y,w,h=[snapshot['crop'][k] for k in ['x','y','width','height']]
            paths=''.join(f'<path d="M{mesh["points"][a]["x"]} {mesh["points"][a]["y"]}L{mesh["points"][b]["x"]} {mesh["points"][b]["y"]}"/>' for a,b in mesh['edges'])
            circles=''.join(f'<circle cx="{p["x"]}" cy="{p["y"]}" r="{w/300}" fill="#7af2fc"/>' for p in mesh['points'])
            svg=f'<svg viewBox="{x} {y} {w} {h}"><image href="{snapshot["dataUrl"]}" width="{snapshot["width"]}" height="{snapshot["height"]}"/><g stroke="#36e4f1" stroke-width="{w/330}" stroke-opacity=".68" fill="none">{paths}{circles}</g></svg>'
            (OUT/f'{label}-{region}.svg').write_text(svg,encoding='utf-8')
        result.update(label=label,modelLoadMs=load,hairModelLoadMs=hair_load,controlledFixture=True,userAcceptance=False,source=str(current_source.relative_to(ROOT)));proof.append(result)
    browser.close()
(OUT/'measurements.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
print(json.dumps([{k:r[k] for k in ['label','inferenceMs','heap']}|{'methods':r['results']} for r in proof],indent=2))
