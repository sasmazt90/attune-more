"""Render the actual production SVG component, separately from eye admission.
No camera conditions, session, TTS, STT or score is fabricated by this probe.
It establishes painted path geometry only, not a successful production trial.
"""
import hashlib,json,subprocess
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

OUT=Path('audit-results/vision-usable');OUT.mkdir(parents=True,exist_ok=True)
SOURCE=Path('apps/vehicle-app/src/components/LetterStimulus.tsx')
node=r"""
const fs=require('fs'),ts=require('typescript'),React=require('react'),server=require('react-dom/server');
function source(path){const output=ts.transpileModule(fs.readFileSync(path,'utf8'),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const m={exports:{}};new Function('require','module','exports',output)(require,m,m.exports);return m.exports;}
const {LetterStimulus}=source('apps/vehicle-app/src/components/LetterStimulus.tsx'),{LETTER_PATHS}=source('apps/vehicle-app/src/utils/spokenVision.ts');
const elements=Object.entries(LETTER_PATHS).flatMap(([letter,path])=>['upright','right','down','left','mirror'].map(orientation=>React.createElement('figure',{key:letter+orientation,'data-case':letter+'-'+orientation},React.createElement(LetterStimulus,{path,orientation,sizePx:160}),React.createElement('figcaption',null,letter+' / '+orientation))));
fs.writeFileSync('audit-results/vision-usable/stimulus-render.html','<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{background:#101820;color:white;margin:16px;font:14px sans-serif}main{display:grid;grid-template-columns:repeat(auto-fit,196px);gap:8px}figure{margin:0;background:#000;padding:12px;width:172px;text-align:center}svg{display:block;margin:auto}figcaption{margin-top:8px}</style><h1>Actual source SVG — geometry only / no eye admission</h1><main>'+server.renderToStaticMarkup(React.createElement(React.Fragment,null,elements))+'</main>');
"""
subprocess.run(['node','-e',node],check=True)
rows=[]
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True)
 for tag,width,height,dpr,zoom in [('desktop',1300,1100,1,1),('narrow',440,900,2,1),('css200',1300,1100,1,2)]:
  c=b.new_context(viewport={'width':width,'height':height},device_scale_factor=dpr);p=c.new_page()
  p.route('**/stimulus-geometry',lambda route:route.fulfill(path=str(OUT/'stimulus-render.html'),content_type='text/html'))
  p.goto('http://127.0.0.1:3000/stimulus-geometry');p.evaluate('(z)=>document.documentElement.style.zoom=String(z)',zoom)
  measurements=[]
  for index in range(p.locator('[data-case]').count()):
   case=p.locator('[data-case]').nth(index);svg=case.locator('svg');svg.scroll_into_view_if_needed();name=case.get_attribute('data-case')
   image_path=OUT/('geometry-'+tag+'-'+name+'.png');svg.screenshot(path=str(image_path))
   image=Image.open(image_path).convert('RGB');white=[(x,y) for y in range(image.height) for x in range(image.width) if min(image.getpixel((x,y)))>220]
   assert white,(tag,name,'No actual painted letter pixels')
   x0,x1=min(x for x,y in white),max(x for x,y in white);y0,y1=min(y for x,y in white),max(y for x,y in white)
   assert x0>0 and y0>0 and x1<image.width-1 and y1<image.height-1,(tag,name,'Paint intersects SVG clipping edge')
   geometry=svg.evaluate("s=>{const b=s.getBoundingClientRect(),p=s.querySelector('path').getBoundingClientRect();return {viewportWidthCssPx:b.width,viewportHeightCssPx:b.height,pathWidthCssPx:p.width,pathHeightCssPx:p.height,dpr:devicePixelRatio,viewBox:s.getAttribute('viewBox')}}")
   measurements.append({'case':name,'geometry':geometry,'paintBoundsPixels':[x0,y0,x1,y1],'imageSizePixels':[image.width,image.height]})
  p.evaluate('window.scrollTo(0,0)');p.screenshot(path=str(OUT/('stimulus-'+tag+'.png')),full_page=True)
  rows.append({'tag':tag,'cssZoom':zoom,'actualBrowserZoomAcceptance':False,'cases':measurements});c.close()
 b.close()
proof={'sourceComponentSHA256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'productionEyeGateAcceptance':False,'cameraOrScoringSubstituted':False,'casesPerLayout':30,'layouts':rows}
(OUT/'stimulus-geometry.json').write_text(json.dumps(proof,indent=2),'utf8')
print('PASS: actual source SVG, 30 paths/orientations × desktop/narrow/CSS200; painted pixels clear of clipping. Production eye admission remains OPEN.')
