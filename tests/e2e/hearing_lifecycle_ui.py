"""Real production PCM cancellation with synthetic engineering controls; no physical listening claim."""
import json,os,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path(os.getenv('HEARING_LIFECYCLE_EVIDENCE','audit-results/hearing-lifecycle'));OUT.mkdir(parents=True,exist_ok=True)
BROWSER={'executable_path':os.environ['ATTUNE_BROWSER_EXECUTABLE']} if os.getenv('ATTUNE_BROWSER_EXECUTABLE') else {'channel':'chrome'}
INIT='''window.pcm=[];const start=AudioBufferSourceNode.prototype.start,stop=AudioBufferSourceNode.prototype.stop;AudioBufferSourceNode.prototype.start=function(...args){const row={at:performance.now(),ended:false,stopped:false,duration:this.buffer?.duration};this.__hearingRow=row;pcm.push(row);this.addEventListener('ended',()=>row.ended=true);return start.apply(this,args);};AudioBufferSourceNode.prototype.stop=function(...args){if(this.__hearingRow)this.__hearingRow.stopped=true;return stop.apply(this,args);};'''
checks=[];errors=[]
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True,**BROWSER)
 for scenario in ['stop-checkbox','mute','locale-cancel','session-owner-change','consent-withdrawal','motion']:
  c=b.new_context(viewport={'width':1440,'height':1000});c.add_init_script(INIT);p=c.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.goto('http://127.0.0.1:3000/hearing');p.get_by_label('Kulaklık sesleri ve yanıtlarımla yerel işitme testinin yapılmasına izin veriyorum.').check();p.get_by_role('button',name='İzin ver ve devam et',exact=True).click();p.get_by_role('button',name='Ses hazırlığını başlat',exact=True).click();expect(p.get_by_role('button',name='Sol kanalı dinle')).to_be_enabled(timeout=25000)
  for ear in ['sol','sağ']:
   p.get_by_role('button',name=ear.capitalize()+' kanalı dinle').click();node=p.get_by_label('Yalnız '+ear+' kulağımda duydum.');expect(node).to_be_enabled(timeout=10000);node.check()
  p.get_by_role('button',name='Saf ses testi',exact=True).click();expect(p.get_by_role('button',name='Duydum',exact=True)).to_be_visible(timeout=15000)
  p.wait_for_function('pcm.length>=3&&!pcm[pcm.length-1].ended',timeout=30000)
  p.screenshot(path=str(OUT/(scenario+'-active.png')),full_page=True)
  assert p.locator('header select').is_disabled(),'language selector must lock during assessment'
  p.wait_for_function('pcm.length>=3&&!pcm[pcm.length-1].ended',timeout=30000)
  before=p.evaluate('({at:performance.now(),active:pcm.filter(x=>!x.ended&&!x.stopped).length})');assert before['active']>0
  if scenario=='stop-checkbox':p.get_by_role('checkbox',name='Testi durdur',exact=True).click()
  elif scenario=='mute':p.get_by_role('button',name='Seslendirmeyi kapat',exact=True).click()
  elif scenario=='locale-cancel':p.evaluate("window.dispatchEvent(new Event('attune-locale-media-cancel'))")
  elif scenario=='session-owner-change':p.evaluate("window.dispatchEvent(new StorageEvent('storage',{key:'attune_hearing_audio_owner',newValue:'synthetic-other-tab-owner'}))")
  elif scenario=='consent-withdrawal':p.evaluate("const doc=JSON.parse(localStorage.getItem('attune_health_processing_v1'));delete doc.services.hearing;localStorage.setItem('attune_health_processing_v1',JSON.stringify(doc));window.dispatchEvent(new Event('attune-service-consent'));window.dispatchEvent(new Event('attune-privacy'))")
  elif scenario=='motion':
   response=p.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':20});assert response.ok
  expect(p.get_by_role('button',name='Duydum',exact=True)).to_have_count(0,timeout=7000)
  p.wait_for_function('pcm.every(x=>x.ended||x.stopped)',timeout=5000);n=p.evaluate('pcm.length');p.wait_for_timeout(4000);assert p.evaluate('pcm.length')==n,'no stale PCM resumes after cancellation'
  assert p.evaluate('localStorage.getItem("attune_hearing_latest_v1")') is None,'aborted test is not persisted'
  p.screenshot(path=str(OUT/(scenario+'-cancelled.png')),full_page=True)
  checks.append({'scenario':scenario,'status':'PASS','actualPCM':p.evaluate('pcm'),'beforeCancellation':before,'languageSelectorLocked':True,'noAbortedRecord':True,'staleResume':False,'controlledInput':scenario in ['locale-cancel','session-owner-change','consent-withdrawal','motion']})
  if scenario=='motion':
   response=p.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0});assert response.ok;p.wait_for_timeout(2000);assert p.evaluate('pcm.length')==n
  c.close()
 assert not errors,errors
 b.close()
 (OUT/'proof.json').write_text(json.dumps({'status':'PASS','buildId':Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'checks':checks,'pageErrors':errors,'noPhysicalVehicleOrHeadphoneClaim':True},indent=2))
print('PASS active PCM stop/mute/language/session/consent/motion cancellation and no stale audio')
