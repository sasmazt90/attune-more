"""Rasterize the actual production SVG to verify scorer transformation symmetry.
Controlled rendering only, no physical/clinical acceptance or provider call.
"""
import ast, json, subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path.cwd();OUT=ROOT/'audit-results/vision-feedback-20261009'
tree=ast.parse((ROOT/'tests/e2e/vision_feedback.py').read_text('utf8'))
boot=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BOOT' for t in n.targets))
algorithm=subprocess.check_output(['node','-e',"const fs=require('fs'),ts=require('typescript');process.stdout.write(ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/spokenVision.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)"],text=True,encoding='utf8')
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True);c=b.new_context(viewport={'width':1600,'height':1000});c.add_init_script(boot);p=c.new_page();p.goto('http://127.0.0.1:3000/vision');p.get_by_role('button',name='Başlat',exact=True).click();p.wait_for_selector('[data-letter-optotype]');p.add_script_tag(content='var exports={};'+algorithm+';window.algorithm=exports')
 proof=p.evaluate("""async()=>{
 const V=algorithm,template=document.querySelector('[data-letter-optotype]'),out=[];
 const transforms=[0,90,180,270].flatMap(rotation=>[false,true].map(mirrored=>({rotation,mirrored,mirrorAxis:'x',order:'mirror-then-rotate'})));
 for(const [letter,path] of Object.entries(V.LETTER_PATHS)){
  const rasters=[];
  for(const t of transforms){const svg=template.cloneNode(true);svg.setAttribute('xmlns','http://www.w3.org/2000/svg');svg.style.width=svg.style.height='232px';svg.querySelector('path').setAttribute('d',path);svg.querySelector('g').setAttribute('transform',`translate(50 50) rotate(${t.rotation}) scale(${t.mirrored?-1:1} 1) translate(-50 -50)`);const image=new Image();image.src='data:image/svg+xml;base64,'+btoa(unescape(encodeURIComponent(svg.outerHTML)));await image.decode();const canvas=document.createElement('canvas');canvas.width=canvas.height=232;const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0,232,232);rasters.push([...ctx.getImageData(0,0,232,232).data].filter((_,i)=>i%4===3));}
  let equivalent=0,minDistinct=1,maxEquivalent=0;
  for(let i=0;i<8;i++)for(let j=i+1;j<8;j++){const a=rasters[i],z=rasters[j],diff=a.reduce((sum,v,k)=>sum+Math.abs(v-z[k]),0)/Math.max(1,a.reduce((s,v)=>s+v,0));const expected=V.equivalentTransform(letter,transforms[i],transforms[j]);if(expected){equivalent++;maxEquivalent=Math.max(maxEquivalent,diff);if(diff>.003)throw Error(letter+' equivalent raster mismatch '+diff);}else{minDistinct=Math.min(minDistinct,diff);if(diff<.02)throw Error(letter+' visually identical but scorer distinct '+diff);}}
  out.push({letter,transforms:8,equivalentPairs:equivalent,maxEquivalentDifference:maxEquivalent,minDistinctDifference:minDistinct});
 }return out;
}""")
 (OUT/'transform-pixels.json').write_text(json.dumps({'buildId':(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'actualProductionSvg':True,'physicalAcceptance':False,'proof':proof},indent=2),'utf8');print(json.dumps(proof));c.close();b.close()
