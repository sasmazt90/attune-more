#!/usr/bin/env python3
"""Reports why each dental photo passes or fails each capture gate. Measures only.

Runs the production frontend gate (assessDentalCapture) and the backend gate
(dental_quality) on real MediaPipe landmarks. No threshold, photo or result changes.
Run on a host from the deployed tree: python dental_gate_probe.py --root /opt/attune FILE...
"""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys

from playwright.sync_api import sync_playwright

POSES = ['FRONT', 'RIGHT', 'LEFT', 'BITE']
BASE = 'http://127.0.0.1:6932/'
# Text rather than numbers keeps the result readable; each maps to one gate rule.
SETUP = """async()=>{
 const V=await import('./vision_bundle.mjs');
 window.m=await V.FaceLandmarker.createFromOptions(await V.FilesetResolver.forVisionTasks('%swasm'),
  {baseOptions:{modelAssetPath:'%sface.task'},runningMode:'IMAGE',numFaces:1,outputFacialTransformationMatrixes:true});
}""" % (BASE, BASE)
ASSESS = """async({data,poses})=>{
 const im=new Image();im.src=data;await im.decode();
 const c=document.createElement('canvas');c.width=im.width;c.height=im.height;
 const ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(im,0,0);
 const small=document.createElement('canvas');small.width=640;small.height=Math.round(im.height*640/im.width);
 small.getContext('2d').drawImage(c,0,0,small.width,small.height);
 const result=m.detect(small),points=result.faceLandmarks[0];
 if(!points)return {size:[im.width,im.height],face:false};
 const a={landmarks:points,faceDetected:true,isMediaPipeActive:true,faceTransform:result.facialTransformationMatrixes[0]?.data};
 const rows={};
 for(const pose of poses){
  const r=dental.assessDentalCapture(ctx,a,pose);
  rows[pose]={valid:r.valid,reasons:r.reasons,contact:r.contact&&{enamel:+r.contact.enamelColumnFraction.toFixed(3),touching:+r.contact.contactColumnFraction.toFixed(3),confirmed:r.contact.confirmed},
   opening:r.opening&&+r.opening.toFixed(3),mouthWidth:r.mouthWidth&&Math.round(r.mouthWidth),visibleFraction:r.visibleFraction&&+r.visibleFraction.toFixed(3),enamelArea:r.enamelAreaFraction&&+r.enamelAreaFraction.toFixed(3),
   light:r.light&&Math.round(r.light),sharp:r.sharp&&Math.round(r.sharp),glare:r.glareFraction&&+r.glareFraction.toFixed(3),tongue:r.tongueFraction&&+r.tongueFraction.toFixed(3),rotation:r.rotation&&{yaw:+(r.rotation.yaw||0).toFixed(1),pitch:+(r.rotation.pitch||0).toFixed(1),roll:+(r.rotation.roll||0).toFixed(1)}};
 }
 return {size:[im.width,im.height],face:true,points:Array.from(points,p=>({x:p.x,y:p.y})),rows};
}"""


def transpile(root):
    script = ("const fs=require('fs'),ts=require('typescript');process.stdout.write(ts.transpileModule("
              "fs.readFileSync('apps/vehicle-app/src/utils/dentalCapture.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText);")
    return subprocess.check_output([str(root.parent / 'node/bin/node') if (root.parent / 'node/bin/node').exists() else 'node', '-e', script], cwd=root, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--chrome', default='/usr/bin/google-chrome')
    parser.add_argument('photos', nargs='+', type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.root / 'services/core-api'))
    from dental_analysis import decode_photo, dental_quality
    public = args.root / 'apps/vehicle-app/public/mediapipe'
    tasks = args.root / 'node_modules/@mediapipe/tasks-vision'
    source = transpile(args.root)
    report = {'scope': 'Gate measurement only. Thresholds unchanged. Not a dental or clinical assessment.', 'photos': []}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=args.chrome, args=['--no-sandbox'])
        page = browser.new_page()

        def route(request):
            name = request.request.url.rsplit('/', 1)[-1]
            if name == 'index':
                request.fulfill(body='<html></html>', content_type='text/html')
            elif name == 'face.task':
                request.fulfill(path=str(public / 'models/face_landmarker.task'), content_type='application/octet-stream')
            elif name == 'vision_bundle.mjs':
                request.fulfill(path=str(tasks / name), content_type='text/javascript')
            elif name.startswith('vision_wasm'):
                request.fulfill(path=str(tasks / 'wasm' / name), content_type='application/wasm' if name.endswith('wasm') else 'text/javascript')
            else:
                request.abort()

        page.route('**/*', route)
        page.goto(BASE + 'index')
        page.evaluate(SETUP)
        page.evaluate('(js)=>{window.dental={};new Function("exports","require",js)(dental,()=>({}));}', source)
        for path in args.photos:
            data = 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode()
            result = page.evaluate(ASSESS, {'data': data, 'poses': POSES})
            row = {'photo': path.name, 'size': result['size'], 'faceFound': result['face']}
            if result['face']:
                image, _ = decode_photo(data)
                row['frontend'] = result['rows']
                row['backend'] = {pose: {'valid': q['valid'], 'reasons': q['reasons']} for pose, q in
                                  ((pose, dental_quality(image, result['points'], bite=pose == 'BITE')) for pose in POSES)}
            report['photos'].append(row)
        browser.close()
    print(json.dumps(report))


if __name__ == '__main__':
    main()
