import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tests/e2e'))
"""Focused production-page controller checks. Controlled camera/ASR/audio only.
Isolated profiles; never writes the normal user's history or sends provider calls.
"""
from pathlib import Path
import base64, json, math, subprocess
from playwright.sync_api import sync_playwright, expect

ROOT=Path.cwd(); OUT=ROOT/'audit-results/feedback-four-modules-20261009/vision-full'; OUT.mkdir(parents=True,exist_ok=True)
BOOT=r"""
localStorage.removeItem('togg_health_vision_history');localStorage.removeItem('togg_health_latest_vision');
window.probe={calls:[],recognitions:[],audios:[],fault:null,mouth:false};
localStorage.setItem('attune_privacy_vision_save_allowed','true');
const nativeFetch=window.fetch.bind(window);
window.fetch=async(url,options)=>{
 if(String(url).endsWith('/api/vision/speech')){const code=JSON.parse(options.body).text;probe.calls.push({code,at:performance.now()});probe.nextAudio=code;return new Response(new Uint8Array([1,2,3]),{headers:{'content-type':'audio/mpeg'}});}
 return nativeFetch(url,options);
};
class Buffer extends EventTarget{updating=false;appendBuffer(){setTimeout(()=>this.dispatchEvent(new Event('updateend')),0)}abort(){}}
class Source extends EventTarget{static isTypeSupported(){return true}readyState='closed';constructor(){super();setTimeout(()=>{this.readyState='open';this.dispatchEvent(new Event('sourceopen'))},0)}addSourceBuffer(){return new Buffer()}endOfStream(){}}
window.MediaSource=Source;
const create=URL.createObjectURL;URL.createObjectURL=x=>x instanceof Source?'blob:controlled-audio':create(x);
class Audio extends EventTarget{paused=true;constructor(){super();this.code=probe.nextAudio;probe.audios.push(this)}load(){}removeAttribute(){}pause(){this.paused=true;clearTimeout(this.timer)}async play(){this.paused=false;this.onplaying?.();this.dispatchEvent(new Event('playing'));this.timer=setTimeout(()=>{this.paused=true;this.onended?.();this.dispatchEvent(new Event('ended'))},['prepare','right','left'].includes(this.code)?120:6000)}}
window.Audio=Audio;
class SR{constructor(){this.results=[];probe.recognitions.push(this)}start(){probe.current=this;setTimeout(()=>this.onstart?.(),0)}abort(){this.aborted=true}emit(text,final=true,duplicate=false){const row=[{transcript:text,confidence:.99}];row.isFinal=final;if(!duplicate)this.results.push(row);this.onresult?.({resultIndex:this.results.length-1,results:this.results})}}
window.SpeechRecognition=SR;window.webkitSpeechRecognition=SR;
navigator.mediaDevices.getUserMedia=async()=>{const c=document.createElement('canvas');c.width=640;c.height=480;const x=c.getContext('2d');x.fillStyle='#102f3f';x.fillRect(0,0,640,480);x.fillStyle='#42d9ec';x.font='28px sans-serif';x.fillText('CONTROLLED CAMERA',125,220);x.font='20px sans-serif';x.fillText('Not physical acceptance',150,265);setInterval(()=>{x.fillStyle=Date.now()%2?'#123546':'#133647';x.fillRect(0,478,2,2)},60);return c.captureStream(10)};
class Worker{postMessage(m){setTimeout(()=>{if(this.closed)return;if(m.type==='initialize'){this.onmessage?.({data:{id:m.id}});return;}m.frame?.close();const open={state:'open',ear:.3,method:'controlled'},closed={...open,state:'closed'};const fault=probe.fault;const points=Array.from({length:478},()=>({x:.5,y:.5}));points[234]={x:.3,y:.5};points[454]={x:.7,y:.5};points[10]={x:.5,y:.2};points[1]={x:.5,y:.5};for(const i of [17,152,172,397])points[i].y=probe.mouth?.9:.65;
 const c={observedAt:m.frameTime,cameraLive:true,modelActive:true,faceCount:1,qualityValid:true,positionValid:true,relativeScaleChange:0,distancePolicy:'head-anchors-hysteresis-v1',distanceState:'stable',blocker:null,right:m.eye==='LEFT'?closed:open,left:m.eye==='RIGHT'?closed:open};
 if(fault==='both-open'){c.right=open;c.left=open;c.blocker='cover-other'}if(fault==='near'){c.positionValid=false;c.relativeScaleChange=.22;c.distanceState='near';c.blocker='recede'}if(fault==='uncertain'){c.left={...open,state:'uncertain'};c.blocker=null}
 this.onmessage?.({data:{id:m.id,evidence:{delegate:'controlled',alignment:{landmarks:points,isMediaPipeActive:true,faceCount:1,box:{x:.3,y:.2,w:.4,h:.5},yaw:0,pitch:.5,roll:0},quality:{status:'GOOD',avgLuminance:120,blurScore:20},conditions:c,inferenceMs:1,distanceRatios:[],distanceSamples:[]}}});},20)}terminate(){this.closed=true}}
window.Worker=Worker;
window.addEventListener('DOMContentLoaded',()=>{const label=document.createElement('div');label.textContent='KONTROLLÜ UI / ASR / KAMERA — fiziksel kabul değildir';Object.assign(label.style,{position:'fixed',bottom:'0',left:'0',zIndex:99999,font:'12px sans-serif',color:'#fff',background:'#753500',padding:'3px'});document.body.append(label)});
"""

def capture(p,name):
 s=p.context.new_cdp_session(p);r=s.send('Page.captureScreenshot',{'format':'png','fromSurface':True,'captureBeyondViewport':False});s.detach();(OUT/name).write_bytes(base64.b64decode(r['data']))
def active(p):
 try:p.wait_for_function("document.querySelector('[data-vision-stage]')?.dataset.visionStage==='listening'&&probe.current&&!probe.current.aborted&&document.querySelector('[data-letter-optotype]')",timeout=15000)
 except Exception:
  capture(p,'failure.png');print(p.locator('body').inner_text());print(p.evaluate('({calls:probe.calls,evidence:document.querySelector("canvas")?.dataset,recognitions:probe.recognitions.length})'));raise
def target(p):
 return p.locator('[data-letter-optotype]').evaluate("e=>({path:e.querySelector('path').getAttribute('d'),transform:e.querySelector('g').getAttribute('transform'),geometry:e.getBoundingClientRect().toJSON(),id:document.querySelector('[data-vision-trial]').dataset.visionTrial})")
PATHS={'M15 90L50 10L85 90M29 60H71':'A','M20 90V10H55C85 10 85 50 55 50H20M55 50C90 50 90 90 55 90H20':'B','M80 10H20V90H80M20 50H70':'E','M80 10H20V90M20 50H70':'F','M20 90V10H55C90 10 90 50 55 50H20':'P','M20 90V10H55C90 10 90 50 55 50H20M55 50L85 90':'R'}
def words(t):
 import re
 rotation=int(re.search(r'rotate\((\d+)\)',t['transform'])[1]);return PATHS[t['path']],{0:'düz',90:'sağa yatmış',180:'baş aşağı',270:'sola yatmış'}[rotation]+(' ve aynalı' if 'scale(-1' in t['transform'] else '')
def emit(p,text):p.evaluate('(text)=>probe.current.emit(text)',text)
def next_target(p,old):p.wait_for_function('(id)=>document.querySelector("[data-vision-trial]")?.dataset.visionTrial!==id',arg=old);active(p)
def dims(p):return p.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,doc:document.documentElement.scrollWidth,cssZoom:getComputedStyle(document.body).zoom})')

errors=[];proof=[]
with sync_playwright() as pw:
 for name,zoom,width in [('desktop',1,1920),('narrow',1,750),('native200',2,1600)]:
  profile=OUT/(name+'-controlled-profile');prefs=profile/'Default';prefs.mkdir(parents=True,exist_ok=True);(prefs/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(zoom)/math.log(1.2)}}}),'utf8')
  c=pw.chromium.launch_persistent_context(str(profile),channel='chrome',headless=False,no_viewport=True,args=[f'--window-size={width},1080','--window-position=0,0']);c.add_init_script(BOOT);p=c.pages[0];p.on('pageerror',lambda e:errors.append(str(e)))
  p.goto('http://127.0.0.1:3000/vision');expect(p.get_by_role('button',name='Başlat',exact=True)).to_be_enabled();capture(p,name+'-start.png');p.get_by_role('button',name='Başlat',exact=True).click();active(p)
  observations=[]
  if name=='desktop':
   first=target(p);p.evaluate("probe.current.emit('Harf alanına bakın. Harfi ve yönünü istediğiniz sırada söyleyin.')");p.wait_for_timeout(80);assert target(p)['id']==first['id'];assert not p.get_by_text('Duyulan:',exact=False).count()
   # Retain partial through a short unknown sensor frame. Mouth-only crop stable.
   before=p.locator('[data-camera-preview]').bounding_box();p.evaluate('probe.mouth=true');p.wait_for_timeout(150);assert p.locator('[data-camera-preview]').bounding_box()==before
   letter,direction=words(first);assert p.evaluate('probe.audios.at(-1).paused===false');p.evaluate('(text)=>probe.current.emit(text,false)',direction);assert target(p)['id']==first['id'];emit(p,direction);p.evaluate('(text)=>probe.current.emit(text,true,true)',direction);expect(p.locator('[data-vision-answer-notice]')).to_contain_text('Yalnız harf');p.evaluate("probe.fault='uncertain'");p.wait_for_timeout(90);p.evaluate('probe.fault=null');p.wait_for_timeout(100);emit(p,letter);next_target(p,first['id']);assert not p.get_by_text('Duyulan:',exact=False).count()
   second=target(p);assert abs(second['geometry']['width']-first['geometry']['width'])<.1;letter,direction=words(second);p.evaluate('(x)=>{probe.old=probe.current;probe.oldCallback=probe.current.onresult;probe.oldAudio=probe.audios.at(-1);probe.oldEnded=probe.oldAudio.onended;probe.current.emit(x)}',letter+' '+direction);next_target(p,second['id']);third=target(p);assert third['geometry']['width']<second['geometry']['width'];p.evaluate("probe.oldCallback({resultIndex:0,results:Object.assign([[{transcript:'düz P',confidence:1}]],{})});probe.oldEnded?.()");p.wait_for_timeout(100);assert target(p)['id']==third['id'];assert not p.get_by_text('Duyulan:',exact=False).count()
   # One wrong doesn't grow. Then not-visible supplies the second error.
   letter,direction=words(third);emit(p,('F' if letter!='F' else 'P')+' '+direction);next_target(p,third['id']);fourth=target(p);assert abs(fourth['geometry']['width']-third['geometry']['width'])<.1;emit(p,'göremiyorum');next_target(p,fourth['id']);fifth=target(p);assert fifth['geometry']['width']>fourth['geometry']['width']
   # A known invalid answer is not queued for subsequent recovery.
   p.evaluate("probe.fault='near'");p.wait_for_timeout(180);emit(p,'düz P');assert target(p)['id']==fifth['id'];p.evaluate('probe.fault=null');p.wait_for_timeout(180);assert target(p)['id']==fifth['id']
   # Popup once, dismissing does not make the wrong-eye state scoreable.
   p.evaluate("probe.fault='both-open'");p.wait_for_timeout(1050);expect(p.get_by_role('dialog',name='Görme bildirimi')).to_be_visible();p.get_by_role('button',name='Tamam',exact=True).click();p.wait_for_timeout(1000);assert not p.get_by_role('dialog').count();assert not p.locator('[data-letter-optotype]').count();p.evaluate('probe.fault=null');active(p)
   # Complete the recovered target explicitly; its retained invalid-condition
   # fragments must not make this pause test a complete answer by accident.
   recovered=target(p);letter,direction=words(recovered);emit(p,letter+' '+direction);next_target(p,recovered['id'])
   resumed=target(p);letter,direction=words(resumed);emit(p,direction);p.wait_for_timeout(100)
   assert target(p)['id']==resumed['id']
   p.get_by_role('button',name='Duraklat',exact=True).click();assert p.get_by_text('Duyulan:',exact=False).count()
   p.get_by_role('button',name='Devam et',exact=True).click();active(p);now=target(p)
   assert now['path']==resumed['path'] and now['transform']==resumed['transform']
   assert p.get_by_text('Duyulan:',exact=False).count()
   observations=[first,second,third,fourth,fifth]
  if name=='desktop':p.locator('[data-vision-stage]').evaluate("e=>e.scrollIntoView({block:'start'})");p.wait_for_timeout(150)
  capture(p,name+'-active.png');layout=dims(p)
  if name=='desktop':
   camera=p.locator('[data-camera-preview]').bounding_box();area=p.locator('[data-letter-area]').bounding_box();assert all(abs(camera[k]-area[k])<.1 for k in ['y','width','height']),(camera,area)
   # Enlarged matching frames use normal page scroll for the readable controls.
   for control in [p.locator('[data-camera-preparation]'),p.get_by_role('button',name='Bitir',exact=True)]:control.scroll_into_view_if_needed();expect(control).to_be_visible()
   p.locator('[data-letter-optotype]').scroll_into_view_if_needed()
  assert layout['doc']<=layout['width']+1,layout
  # Complete exactly 12 per eye on the actual page, free ordering and early finals.
  while p.locator('[data-vision-stage]').get_attribute('data-vision-stage')!='result':
   active(p);t=target(p);letter,direction=words(t);index=p.locator('[data-vision-stage]').inner_text().split(' göz · ')[-1].split('/12')[0]
   if len(observations)%2:emit(p,letter);p.wait_for_timeout(60);emit(p,direction)
   else:emit(p,direction+' '+letter)
   observations.append(t)
   try:p.wait_for_function('(id)=>document.querySelector("[data-vision-trial]").dataset.visionTrial!==id',arg=t['id'],timeout=10000)
   except Exception:
    capture(p,name+'-response-failure.png');print(name,t,letter,direction,p.locator('body').inner_text());print(p.evaluate('({calls:probe.calls,answer:document.querySelector("canvas")?.dataset,voice:probe.current?.aborted,results:probe.current?.results})'));raise
  expect(p.get_by_role('dialog',name='Görme bildirimi')).to_be_visible();p.get_by_role('button',name='Tamam',exact=True).click();p.evaluate('window.scrollTo(0,0)');capture(p,name+'-result.png')
  record=p.evaluate("JSON.parse(localStorage.getItem('togg_health_vision_history'))[0]");valid=[t for t in record['trials'] if t['valid']];assert len(valid)==24;assert all(sum(t['eye']==eye for t in valid)==12 for eye in ['RIGHT','LEFT']);assert record['protocolVersion']=='spoken-letter-v2'
  calls=p.evaluate('probe.calls');assert sum(x['code']=='first' for x in calls)==1;assert sum(x['code']=='right' for x in calls)==1;assert sum(x['code']=='left' for x in calls)==1
  continued=[x['code'] for x in calls if x['code'].startswith('next')];assert all(a!=b for a,b in zip(continued,continued[1:])),continued
  assert not p.locator('[data-letter-result]').get_by_text('CONDITIONS_INVALID_AT_RESPONSE').count();expect(p.get_by_role('button',name='Yeni görev',exact=True)).to_be_visible()
  if name!='desktop':
   p.locator('[data-letter-result]').get_by_role('button',name='Sonraki kartlar').click();p.wait_for_timeout(450);expect(p.locator('[data-letter-result]').get_by_role('button',name='Önceki kartlar')).to_be_enabled();capture(p,name+'-result-left.png')
  summaries=p.locator('[data-eye-summary]').all_text_contents();p.get_by_role('button',name='Sonucu Aç',exact=True).click();d=p.get_by_role('dialog',name='Göz Sağlığı sonucu');expect(d.locator('[data-eye-result]')).to_have_count(2);assert d.locator('[data-eye-summary]').all_text_contents()==summaries;capture(p,name+'-record-popup.png');d.get_by_role('button',name='Sonuç penceresini kapat').click()
  p.get_by_role('button',name='Göz Sağlığı kaydını sil:',exact=False).click();p.get_by_role('button',name='Hayır, vazgeç').click();assert len(p.evaluate("JSON.parse(localStorage.getItem('togg_health_vision_history'))"))==1;p.get_by_role('button',name='Göz Sağlığı kaydını sil:',exact=False).click();p.get_by_role('button',name='Evet, sil').click();expect(p.locator('[data-record-id]')).to_have_count(0)
  p.goto('http://127.0.0.1:3000/profile');p.evaluate('(r)=>{localStorage.setItem("togg_health_vision_history",JSON.stringify([r]));window.dispatchEvent(new Event("attune-records"))}',record);p.get_by_role('button',name='Sonucu Aç',exact=True).click();d=p.get_by_role('dialog',name='Göz Sağlığı sonucu');assert d.locator('[data-eye-summary]').all_text_contents()==summaries;capture(p,name+'-history-popup.png');d.get_by_role('button',name='Sonuç penceresini kapat').click()
  proof.append({'surface':name,'dimensions':layout,'validTrials':len(valid),'calls':calls,'geometry':observations,'protocol':record['protocolVersion'],'normalProfileWritten':False,'physicalCamera':False,'physicalMicrophone':False,'nativePlayback':False,'summary':summaries});c.close()
(OUT/'controller-proof.json').write_text(json.dumps({'build':(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'proof':proof,'pageErrors':errors},ensure_ascii=False,indent=2),'utf8');assert not errors,errors;print(json.dumps({'surfaces':[x['surface'] for x in proof],'validTrials':[x['validTrials'] for x in proof],'errors':errors}))
