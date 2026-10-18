"""Isolated real browser expression observation using the existing local task."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/material-runtime-followup-20261013';CENSUS=ROOT/'audit-results/dry-sag-source-census-20261013'
selection=json.loads((CENSUS/'contour-selection.json').read_text('utf8'))
prefixes=['99f82af5','fc3a6b13','05619d0a','f90e68f8','64b02ede','40c7edda'];rows=[]
with sync_playwright() as pw:
    context=pw.chromium.launch_persistent_context(str(ROOT/'output/playwright/material-runtime-expression-profile'),channel='chrome',headless=False,viewport=dict(width=1300,height=900),args=['--enable-unsafe-swiftshader'])
    context.route('**/__audit/vision_bundle.mjs',lambda r:r.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision/vision_bundle.mjs'),content_type='text/javascript'))
    page=context.new_page();page.goto('http://127.0.0.1:3000/privacy');assert not page.get_by_label('Cilt tipi için yüz fotoğrafımın Roboflow tarafından işlenmesine izin ver',exact=True).is_checked()
    page.add_script_tag(content=(ROOT/'.runtime/periorbital-v5-browser-support/utilities.js').read_text('utf8'))
    page.evaluate("async()=>{window.__auditMediaPipe=await import('/__audit/vision_bundle.mjs');const m=await __auditRequire('apps/vehicle-app/src/utils/skinAnalyzer.ts').SkinAnalyzer.getFaceLandmarker();await m.setOptions({outputFaceBlendshapes:true});return true}")
    for prefix in prefixes:
        path=CENSUS/'product'/prefix/(prefix+'-automatic-payload.json')
        if prefix=='05619d0a':path=ROOT/'audit-results/dry-sag-native-followup-20261013/05619d0a-payload.json'
        if prefix=='40c7edda':path=ROOT/'audit-results/native-dry-scale-20261013/sag-targeted/40c7edda-payload.json'
        if path.exists():payload=json.loads(path.read_text('utf8'))
        else:
            probe=json.loads((CENSUS/(prefix+'-probe.json')).read_text('utf8'));s=probe['snapshot'];payload=dict(photo=s['dataUrl'],photoId=s['photoId'],landmarks=s['landmarks'])
        result=page.evaluate('''async photo=>{const im=new Image();im.src=photo;await im.decode();const m=await __auditRequire('apps/vehicle-app/src/utils/skinAnalyzer.ts').SkinAnalyzer.getFaceLandmarker();const r=m.detect(im);return {landmarks:r.faceLandmarks[0],blendshapes:Object.fromEntries((r.faceBlendshapes[0]?.categories||[]).map(c=>[c.categoryName,c.score])),faceCount:r.faceLandmarks.length}}''',payload['photo'])
        # Same actual source bitmap and same local MediaPipe model; coefficients
        # are recorded, not substituted for quality or a clinical sag label.
        result.update(source=prefix,photoId=payload['photoId']);rows.append(result)
        print(json.dumps({k:v for k,v in result.items() if k!='landmarks'}),flush=True)
    context.close()
(OUT/'browser-expression.json').write_text(json.dumps(dict(rows=rows,hostedCalls=0,existingLocalMediaPipe=True,normalCaptureCodeChanged=False,predeclaredSmileSupportThreshold=.5),indent=2),'utf8')
