"""Three genuinely different camera poses from licensed public video, actual production MediaPipe.
Derived fixture is CC BY-SA 4.0, NMu11er, Head Shake (2022). Never use private user frames.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request
from playwright.sync_api import sync_playwright

SOURCE='https://upload.wikimedia.org/wikipedia/commons/9/92/Head_Shake.webm'
PAGE='https://commons.wikimedia.org/wiki/File:Head_Shake.webm'
SHA1='fb35a2ecbf0771ab818c2ca336142c30b515a414'
FIX=Path('audit-fixtures');FIX.mkdir(exist_ok=True)
OUT=Path('audit-results');OUT.mkdir(exist_ok=True)
(OUT/'FIXTURE-LICENSE.md').write_text(Path('docs/test-fixture-provenance.md').read_text(encoding='utf-8-sig'),encoding='utf-8')
video=FIX/'head-shake.webm'
if not video.exists():
    request=urllib.request.Request(SOURCE,headers={'User-Agent':'AttuneFixtureVerification/1.0 (https://github.com/sasmazt90/togg-health-mvp)'})
    with urllib.request.urlopen(request,timeout=30) as response:video.write_bytes(response.read())
assert hashlib.sha1(video.read_bytes()).hexdigest()==SHA1,'Public fixture changed'
ffmpeg=shutil.which('ffmpeg')
if not ffmpeg:
    import imageio_ffmpeg
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
frames=FIX/'head-shake-frames';frames.mkdir(exist_ok=True)
subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(video),'-vf','fps=10,crop=900:675:90:190,scale=640:480',str(frames/'frame-%03d.jpg')],check=True)
compiler=r"""const fs=require('fs'),ts=require('typescript');for(const name of ['skinAnalyzer','skinMultiAngle']){let s=ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/'+name+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;s=s.replace("from '@mediapipe/tasks-vision'","from 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/+esm'").replace('./skinAnalyzer','./skinAnalyzer.js');fs.writeFileSync('audit-fixtures/'+name+'.js',s);}"""
subprocess.run(['node','-e',compiler],check=True)
selected={};measurements=[]
with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True,args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
    p=b.new_page()
    p.on('console',lambda message:print('MODEL_DIAGNOSTIC',message.text) if message.type in ('error','warning') else None)
    p.route('**/fixture-probe',lambda r:r.fulfill(content_type='text/html',body='<canvas id="frame" width="640" height="480"></canvas>'))
    p.route('**/skinAnalyzer.js',lambda r:r.fulfill(path=str(FIX/'skinAnalyzer.js'),content_type='text/javascript'))
    p.route('**/skinMultiAngle.js',lambda r:r.fulfill(path=str(FIX/'skinMultiAngle.js'),content_type='text/javascript'))
    p.route('**/probe-frame-*',lambda r:r.fulfill(path=str(frames/('frame-'+r.request.url.rsplit('-',1)[1]+'.jpg')),content_type='image/jpeg'))
    p.goto('http://localhost:3000/fixture-probe')
    p.evaluate("async()=>{window.A=(await import('./skinAnalyzer.js')).SkinAnalyzer;window.M=await import('./skinMultiAngle.js');if(!await A.getFaceLandmarker())throw Error('Actual model did not load');}")
    for index,file in enumerate(sorted(frames.glob('frame-*.jpg')),1):
        result=p.evaluate('''async(index)=>{const image=new Image();image.src='./probe-frame-'+String(index).padStart(3,'0');await image.decode();const c=document.querySelector('canvas'),ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0,640,480);const a=A.assessAlignment(ctx,640,480),q=A.checkQuality(ctx,640,480,a.faceDetected,a.box);return {pose:{yaw:a.yaw,pitch:a.pitch,roll:a.roll,scaleRatio:a.scaleRatio},quality:q,usedMediaPipe:a.isMediaPipeActive,landmarkCount:a.landmarks?.length||0,matches:M.SKIN_ANGLES.filter(angle=>M.matchesSkinAngle(a,angle))};}''',index)
        result.update(frame=index,seconds=(index-1)/10);measurements.append(result)
        if result['quality']['isValid'] and result['usedMediaPipe']:
            for angle in result['matches']:
                if angle not in selected:selected[angle]={**result,'file':str(file)}
    b.close()
provenance={'source':SOURCE,'page':PAGE,'license':'CC BY-SA 4.0','licenseUrl':'https://creativecommons.org/licenses/by-sa/4.0/','author':'NMu11er','sourceSha1':SHA1,'changes':['sample genuinely different frames at 10 fps','uniform crop 900x675 at 90,190 and scale 640x480','hold each admitted pose for fifteen seconds in virtual camera'],'poseMock':False,'rotation':False,'qualityThresholdChanged':False,'measurements':measurements,'selected':selected}
(OUT/'multi-angle-fixture-provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
assert set(selected)=={'FRONT','RIGHT','LEFT'},'Licensed video did not pass all real pose/quality checks; controlled user capture still needed'
assert len({r['frame'] for r in selected.values()})==3,'Same frame cannot stand for multiple angles'
concat=FIX/'three-angle-concat.txt';concat.write_text(''.join("file '"+str(Path(selected[a]['file']).resolve()).replace('\\','/')+"'\nduration 15\n" for a in ['FRONT','RIGHT','LEFT'])+"file '"+str(Path(selected['LEFT']['file']).resolve()).replace('\\','/')+"'\n",encoding='utf-8')
subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat),'-vf','fps=15,setsar=1','-t','45','-pix_fmt','yuv420p',str(FIX/'three-angle.y4m')],check=True)
print(json.dumps({'sourceSha1':SHA1,'selected':selected},ensure_ascii=False))
