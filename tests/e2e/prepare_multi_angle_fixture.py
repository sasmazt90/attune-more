"""Three genuinely different camera poses from licensed public video, actual production MediaPipe.
Derived fixture is CC BY-SA 4.0, NMu11er, Head Shake (2022). Never use private user frames.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import shutil
import subprocess
import threading
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
compiler=r"""const fs=require('fs'),ts=require('typescript');for(const name of ['skinAnalyzer','skinMultiAngle','skinExpression']){let s=ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/'+name+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;s=s.replace("from '@mediapipe/tasks-vision'","from './tasks-vision.mjs'").replace('./skinAnalyzer','./skinAnalyzer.js').replace('./skinExpression','./skinExpression.js');fs.writeFileSync('audit-fixtures/'+name+'.js',s);}"""
subprocess.run(['node','-e',compiler],check=True)
for module in FIX.glob('skin*.js'):
    for dependency in re.findall(r"from\s+['\"](\./[^'\"]+)['\"]",module.read_text(encoding='utf-8')):
        target=Path('node_modules/@mediapipe/tasks-vision/vision_bundle.mjs') if dependency=='./tasks-vision.mjs' else FIX/dependency.removeprefix('./')
        assert target.is_file(),f'{module.name}: missing fixture dependency {dependency} at {target}'
selected={};measurements=[]
PUBLIC=Path('apps/vehicle-app/public').resolve()
served=set()
class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self,format,*args):pass
    def do_GET(self):
        path=self.path.split('?',1)[0]
        if path=='/fixture-probe':
            content_type='text/html';body=b'<canvas id="frame" width="640" height="480"></canvas>'
        elif path in ('/skinAnalyzer.js','/skinMultiAngle.js','/skinExpression.js'):
            name=path[1:];served.add(name);content_type='text/javascript';body=(FIX/name).read_bytes()
        elif path=='/tasks-vision.mjs':
            served.add('tasks-vision.mjs');content_type='text/javascript';body=Path('node_modules/@mediapipe/tasks-vision/vision_bundle.mjs').read_bytes()
        elif path.startswith('/mediapipe/'):
            asset=(PUBLIC/path.lstrip('/')).resolve();asset.relative_to(PUBLIC)
            content_type='application/wasm' if asset.suffix=='.wasm' else 'text/javascript' if asset.suffix=='.js' else 'application/octet-stream';body=asset.read_bytes()
        elif re.fullmatch(r'/probe-frame-\d{3}',path):
            content_type='image/jpeg';body=(frames/('frame-'+path.rsplit('-',1)[1]+'.jpg')).read_bytes()
        else:
            print('FIXTURE_404',path,flush=True);self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
server=ThreadingHTTPServer(('127.0.0.1',0),FixtureHandler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True,args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        p=b.new_page();p.on('console',lambda message:print('MODEL_DIAGNOSTIC',message.text) if message.type in ('error','warning') else None)
        base=f'http://127.0.0.1:{server.server_port}'
        p.goto(base+'/fixture-probe')
        p.evaluate("async()=>{window.A=(await import('./skinAnalyzer.js')).SkinAnalyzer;window.M=await import('./skinMultiAngle.js');if(!await A.getFaceLandmarker())throw Error('Actual model did not load');}")
        assert served=={'skinAnalyzer.js','skinMultiAngle.js','skinExpression.js','tasks-vision.mjs'},served
        for index,file in enumerate(sorted(frames.glob('frame-*.jpg')),1):
            result=p.evaluate('''async(index)=>{const image=new Image();image.src='./probe-frame-'+String(index).padStart(3,'0');await image.decode();const c=document.querySelector('canvas'),ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0,640,480);const a=A.assessAlignment(ctx,640,480),q=A.checkQuality(ctx,640,480,a.faceDetected,a.box);return {pose:{yaw:a.yaw,pitch:a.pitch,roll:a.roll,scaleRatio:a.scaleRatio},quality:q,usedMediaPipe:a.isMediaPipeActive,landmarkCount:a.landmarks?.length||0,matches:M.SKIN_ANGLES.filter(angle=>M.matchesSkinAngle(a,angle))};}''',index)
            result.update(frame=index,seconds=(index-1)/10);measurements.append(result)
            if result['quality']['isValid'] and result['usedMediaPipe']:
                for angle in result['matches']:
                    if angle not in selected:selected[angle]={**result,'file':str(file)}
        b.close()
finally:
    server.shutdown();server.server_close();thread.join()
provenance={'source':SOURCE,'page':PAGE,'license':'CC BY-SA 4.0','licenseUrl':'https://creativecommons.org/licenses/by-sa/4.0/','author':'NMu11er','sourceSha1':SHA1,'changes':['sample genuinely different frames at 10 fps','uniform crop 900x675 at 90,190 and scale 640x480','hold each admitted pose for fifteen seconds in virtual camera'],'poseMock':False,'rotation':False,'qualityThresholdChanged':False,'measurements':measurements,'selected':selected}
(OUT/'multi-angle-fixture-provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
assert set(selected)=={'FRONT','RIGHT','LEFT'},'Licensed video did not pass all real pose/quality checks; controlled user capture still needed'
assert len({r['frame'] for r in selected.values()})==3,'Same frame cannot stand for multiple angles'
concat=FIX/'three-angle-concat.txt';concat.write_text(''.join("file '"+str(Path(selected[a]['file']).resolve()).replace('\\','/')+"'\nduration 15\n" for a in ['FRONT','RIGHT','LEFT'])+"file '"+str(Path(selected['LEFT']['file']).resolve()).replace('\\','/')+"'\n",encoding='utf-8')
subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat),'-vf','fps=15,setsar=1','-t','45','-pix_fmt','yuv420p',str(FIX/'three-angle.y4m')],check=True)
print(json.dumps({'sourceSha1':SHA1,'selected':selected},ensure_ascii=False))
