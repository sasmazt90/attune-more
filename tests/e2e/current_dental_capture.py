"""Four photographed poses -> actual production camera/model/gates/capture/API.
Different participants: controller proof only, never a physical single-user test.
"""
from pathlib import Path
import json,time,subprocess,os,tempfile,math,sys
from playwright.sync_api import sync_playwright,expect
ROOT=Path.cwd();native=os.environ.get('DENTAL_AUDIT_NATIVE200')=='1';OUT=ROOT/'audit-results/followup-closure-20261010'/('dental-native200' if native else 'dental-camera');OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(Path(__file__).parent));from owned_window_capture import capture_owned_window
fixture=ROOT/'audit-results/followup-closure-20261010/dental-four-poses.y4m';assert fixture.exists()
js=subprocess.check_output(['node','-e',"const fs=require('fs'),ts=require('typescript');process.stdout.write(ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/dentalCapture.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText);"],text=True)
with sync_playwright() as pw:
 args=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(fixture),'--enable-unsafe-swiftshader'];b=None;profile=None
 if native:
  profile=tempfile.TemporaryDirectory(prefix='attune-dental-native200-');pref=Path(profile.name)/'Default';pref.mkdir();(pref/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(2)/math.log(1.2)}}}),'utf8');c=pw.chromium.launch_persistent_context(profile.name,channel='chrome',headless=False,no_viewport=True,permissions=['camera'],args=args+['--window-size=1600,1000'])
 else:
  b=pw.chromium.launch(channel='chrome',headless=True,args=args);c=b.new_context(permissions=['camera'],viewport={'width':1600,'height':1000})
 c.add_init_script('window.dentalProbe={};new Function("exports",'+json.dumps(js)+')(dentalProbe);')
 c.add_init_script('''window.dentalTrace=[];window.dentalRequests=[];window.dentalResponses=[];
 const original=Worker.prototype.postMessage;Worker.prototype.postMessage=function(m,...rest){if(!this.audit){this.audit=true;this.addEventListener('message',({data})=>{const v=document.querySelector('[data-dental-live-video]');if(!data.alignment||!v||v.readyState<2)return;const canvas=document.createElement('canvas');canvas.width=v.videoWidth;canvas.height=v.videoHeight;const ctx=canvas.getContext('2d');ctx.drawImage(v,0,0);dentalTrace.push({at:performance.now(),sourceTime:v.currentTime,sourceSize:[v.videoWidth,v.videoHeight],alignment:{faceDetected:data.alignment.faceDetected,faceTransform:data.alignment.faceTransform,legacyYaw:data.alignment.yaw,legacyPitch:data.alignment.pitch,scaleRatio:data.alignment.scaleRatio},gates:Object.fromEntries(['FRONT','RIGHT','LEFT','BITE'].map(pose=>[pose,dentalProbe.assessDentalCapture(ctx,data.alignment,pose)])),body:document.querySelector('[data-dental-page]').innerText});});}return original.call(this,m,...rest);};
 const fetchOriginal=window.fetch;window.fetch=async(...args)=>{if(String(args[0]).endsWith('/api/local-health/dental'))dentalRequests.push(JSON.parse(args[1].body));const r=await fetchOriginal(...args);if(String(args[0]).endsWith('/api/local-health/dental'))dentalResponses.push({status:r.status,body:await r.clone().json()});return r;};''')
 p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)));c.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0})
 p.goto('http://127.0.0.1:3000/dental');p.get_by_label('Fotoğraflarımı yalnız bu cihazda geçici işlemeyi kabul ediyorum.').check();p.get_by_role('button',name='Diş Taramasını Başlat',exact=True).click()
 start=time.monotonic();states=[]
 while not p.locator('[data-dental-result]').count() and time.monotonic()-start<130:
  p.wait_for_timeout(1000);states.append(dict(at=time.monotonic()-start,body=p.locator('[data-dental-page]').inner_text()));(OUT/'states.json').write_text(json.dumps(states,ensure_ascii=False,indent=2),'utf8')
  if p.locator('[data-dental-page] [role="alert"]').count():break
 trace=p.evaluate('dentalTrace');(OUT/'source-quality-trace.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2),'utf8');p.screenshot(path=str(OUT/'final-desktop.png'),full_page=True)
 (OUT/'capture-request-private.json').write_text(json.dumps(p.evaluate('dentalRequests')),'utf8');(OUT/'http-responses.json').write_text(json.dumps(p.evaluate('dentalResponses'),ensure_ascii=False,indent=2),'utf8')
 expect(p.locator('[data-dental-result]')).to_be_visible(timeout=1000)
 geometry=None
 if native:
  geometry=p.evaluate('({innerWidth,outerWidth,dpr:devicePixelRatio,zoom:getComputedStyle(document.documentElement).zoom,scroll:document.documentElement.scrollWidth})');assert geometry['dpr']>=2 and geometry['innerWidth']<geometry['outerWidth']*.65 and geometry['zoom']=='1' and geometry['scroll']<=geometry['innerWidth'];capture_owned_window(p,profile.name,OUT/'result-native200.png')
 requests=p.evaluate('dentalRequests');responses=p.evaluate('dentalResponses');assert len(requests)==1 and len(responses)==1
 capture=requests[0]['captures'];assert responses[0]['status']==200;response=responses[0]['body'];assert [v['pose'] for v in capture]==['FRONT','RIGHT','LEFT','BITE']
 assert len({v['photoId'] for v in capture})==4 and all(v['width']==1920 and v['height']==1080 and len(v['landmarks'])>=468 for v in capture)
 assert response['methodVersion']=='dental-visible-v2' and all(v['quality']['valid'] for v in response['views']),response['views']
 for expected,view in zip(capture,response['views']):assert view['pose']==expected['pose'] and view['photoId']==expected['photoId'] and view['caries']['quality']=='valid'
 for i in range(4):
  p.screenshot(path=str(OUT/f'view-{i}.png'),full_page=True);p.get_by_role('button',name='Sonraki',exact=True).click()
 p.set_viewport_size({'width':720,'height':900});p.screenshot(path=str(OUT/'result-narrow.png'),full_page=True);assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
 assert not errors,errors
 (OUT/'capture-request-private.json').write_text(json.dumps(requests[0]),'utf8');(OUT/'response.json').write_text(json.dumps(response,ensure_ascii=False,indent=2),'utf8')
 (OUT/'proof.json').write_text(json.dumps(dict(status='PASS',buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),seconds=time.monotonic()-start,controlledPhotographicFixture=True,independentPeople=True,physicalUserAcceptance=False,poseOverride=False,qualityOverride=False,capturePoses=[v['pose'] for v in capture],photoIds=[v['photoId'] for v in capture],allBackendQualityValid=True,native200=geometry,pageErrors=errors),indent=2),'utf8');c.close()
 if b:b.close()
 if profile:profile.cleanup()
print('PASS: actual model and source-quality gates, four camera captures and local backend')
