"""Production UI contract and durable deletion; controlled fixtures, NOT live acceptance.
No physical microphone or camera access. Native device/provider acceptance runs separately.
"""
import io, json, math, struct, wave, hashlib, traceback, subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

OUT=Path('audit-results/final-user-flow-20261003/after'); OUT.mkdir(parents=True,exist_ok=True)
BASE='http://localhost:3000'; API='http://localhost:8000'; results=[]
KEYS={'vision':('togg_health_vision_history','togg_health_latest_vision'),'skin':('togg_health_skin_history','togg_health_latest_skin'),'mental':('togg_health_mental_history','togg_health_latest_mental')}
DENIED="""window.captureAttempts=0;navigator.mediaDevices.getUserMedia=()=>{window.captureAttempts++;return Promise.reject(new DOMException('Controlled denial','NotAllowedError'));};const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(SR)SR.prototype.start=()=>{window.captureAttempts++;throw new DOMException('Controlled denial','NotAllowedError');};"""
CONTROLLED="""window.captureAttempts=0;window.audioProof=[];window.recognitionProof=[];
class VerifiedSyntheticRecognition {start(){window.controlledRecognition=this;window.recognitionProof.push('requested');}abort(){window.recognitionProof.push('aborted');}}
window.SpeechRecognition=window.webkitSpeechRecognition=VerifiedSyntheticRecognition;
navigator.mediaDevices.getUserMedia=()=>{window.captureAttempts++;throw new Error('Physical capture forbidden');};
const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(...args){for(const type of ['playing','ended','error'])this.addEventListener(type,()=>window.audioProof.push({type,time:performance.now()}));return play.apply(this,args);};"""
CONTROLLED_AUDIO=Path('tests/fixtures/synthetic-tone.mp3').read_bytes() # generated tone, controlled regression only; not provider acceptance

def record(name,fn):
 try: result={'name':name,'status':'PASS','detail':fn()}
 except Exception as error: result={'name':name,'status':'FAIL','error':str(error),'traceback':traceback.format_exc()}
 results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)

def snap(page,name,full=True):
 page.screenshot(path=str(OUT/(name+'.png')),full_page=full and not page.get_by_role('dialog').count(),animations='disabled')

def seed(page,category,extra=None):
 date='2026-10-03T10:00:00Z'
 common={'date':date,'timestamp':date}
 fields={'vision':{'testCompleted':True,'acuityRightSnellen':'20/20','acuityLeftSnellen':'20/30','contrastSensitivityLogCS':1.5},'skin':{'regions':{},'highestChangeRegion':'Alın','isBaseline':True,'usedMediaPipe':True,'comparisonScope':'single-front-v1'},'mental':{'summaryText':'Sentetik eski özet','themes':['kitap'],'schemaVersion':2,'completed':True,'consented':True}}
 old={**common,**fields[category]};new={**common,**fields[category],'id':'new-'+category,'isBaseline':False,'summaryText':'Sentetik yeni özet','baselineId':None,**(extra or {})}
 page.evaluate('([keys,records])=>{localStorage.setItem(keys[0],JSON.stringify(records));localStorage.setItem(keys[1],JSON.stringify(records[0]));}',[KEYS[category],[old,new]])

with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,args=['--autoplay-policy=no-user-gesture-required'])
 def fresh(width=1280,height=900,controlled=False):
  c=browser.new_context(viewport={'width':width,'height':height},locale='tr-TR');c.add_init_script(CONTROLLED if controlled else DENIED);c.request.post(API+'/api/vehicle/speed',data={'speedKmH':0});p=c.new_page();p.goto(BASE+'/profile');return c,p

 def information():
  evidence=[]
  for width,height in [(390,500),(820,900),(1280,900)]:
   c,p=fresh(width,height)
   try:
    for route in ['','vision','skin','mental','care','profile','privacy']:
     if route=='care':p.route('**/api/care/match',lambda r:r.abort())
     p.goto(BASE+'/'+route);p.wait_for_timeout(300)
     assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
     snap(p,f'{route or "cockpit"}-initial-{width}')
     buttons=p.get_by_role('button',name='hakkında bilgi').all()
     assert buttons,route
     for i,caller in enumerate(buttons):
      assert caller.bounding_box()['width']>=44 and caller.bounding_box()['height']>=44
      caller.click();dialog=p.get_by_role('dialog');expect(dialog).to_be_visible()
      p.wait_for_function('document.querySelector("[role=dialog]").contains(document.activeElement)')
      bounds=dialog.bounding_box();assert bounds['y']>=15 and bounds['y']+bounds['height']<=height-15,(route,width,caller.get_attribute('aria-label'),bounds)
      assert dialog.evaluate('(e)=>{const r=e.firstElementChild.getBoundingClientRect();return e.contains(document.elementFromPoint(r.left+10,r.top+10))}'),'Dialog title covered by page navigation'
      for _ in range(15):p.keyboard.press('Tab');assert dialog.evaluate('e=>e.contains(document.activeElement)')
      p.keyboard.press('Shift+Tab');assert dialog.evaluate('e=>e.contains(document.activeElement)')
      snap(p,f'{route or "cockpit"}-information-{i}-{width}',False)
      p.keyboard.press('Escape');expect(dialog).to_have_count(0);assert caller.evaluate('e=>e===document.activeElement')
     evidence.append({'route':route or 'cockpit','width':width,'dialogs':len(buttons),'captureAttempts':p.evaluate('window.captureAttempts')})
    for category in KEYS:
     p.goto(BASE+'/profile');seed(p,category);p.reload();panel=p.locator(f'[data-record-history={category}]');expect(panel.locator('[data-record-id]')).to_have_count(2)
     panel.get_by_role('button',name='kaydını sil:').first.click();snap(p,f'{category}-delete-dialog-{width}',False);p.keyboard.press('Escape');expect(panel.locator('[data-record-id]')).to_have_count(2)
   finally:c.close()
  return evidence
 record('All seven tabs: information dialogs, touch targets, short viewport, trap and return',information)

 def deletion(category):
  c,p=fresh(390,844)
  try:
   seed(p,category);p.reload();panel=p.locator(f'[data-record-history={category}]');expect(panel.locator('[data-record-id]')).to_have_count(2)
   migrated=p.evaluate('(k)=>JSON.parse(localStorage.getItem(k))',KEYS[category][0]);assert len({r['id'] for r in migrated})==2 and migrated[0]['id']!='new-'+category
   before=p.evaluate('()=>JSON.stringify({...localStorage})')
   for action in ['cancel','escape','close']:
    caller=panel.get_by_role('button',name='kaydını sil:').first
    caller.click();dialog=p.get_by_role('dialog',name='Bu kaydı silmek istiyor musunuz?',exact=True);expect(dialog).to_contain_text('Bu işlem geri alınamaz.');snap(p,f'{category}-delete-{action}-390',False)
    if action=='cancel':dialog.get_by_role('button',name='Hayır, vazgeç',exact=True).click()
    elif action=='escape':p.keyboard.press('Escape')
    else:dialog.get_by_role('button',name='Silme penceresini kapat',exact=True).click()
    assert p.evaluate('()=>JSON.stringify({...localStorage})')==before
    assert caller.evaluate('e=>e===document.activeElement')
   old_id=migrated[0]['id'];panel.get_by_role('button',name='kaydını sil:').first.click();p.get_by_role('button',name='Evet, sil',exact=True).click();expect(panel.locator('[data-record-id]')).to_have_count(1)
   assert p.evaluate('(k)=>JSON.parse(localStorage.getItem(k))[0].id',KEYS[category][0])=='new-'+category
   assert p.evaluate('(k)=>JSON.parse(localStorage.getItem(k)).id',KEYS[category][1])=='new-'+category
   p.reload();expect(panel.locator('[data-record-id]')).to_have_count(1)
   p.close();p=c.new_page();p.goto(BASE+'/profile');panel=p.locator(f'[data-record-history={category}]');expect(panel.locator('[data-record-id]')).to_have_count(1)
   assert panel.locator(f'[data-record-id="{old_id}"]').count()==0
   # Another isolated browser user never receives or removes this profile's record.
   other=browser.new_context();op=other.new_page();op.goto(BASE+'/profile');expect(op.locator(f'[data-record-history={category}] [data-record-id]')).to_have_count(0);other.close()
   panel.get_by_role('button',name='kaydını sil:').click();p.get_by_role('button',name='Evet, sil',exact=True).click();expect(panel.locator('[data-record-id]')).to_have_count(0);p.reload();expect(panel.locator('[data-record-id]')).to_have_count(0)
   assert p.evaluate('(k)=>localStorage.getItem(k)',KEYS[category][1]) is None
   p.get_by_role('button',name='Hekimle Paylaşılabilir Özet',exact=True).click();expect(p.get_by_role('button',name='Yazdır / PDF olarak kaydet',exact=True)).to_be_disabled()
   return {'oldAndNew':True,'cancelEscapeCloseNoMutation':True,'onlySelectedIdDeleted':True,'refreshReopenSurvives':True,'otherProfileIsolated':True,'lastRecordEmpty':True,'pdfEmpty':True}
  finally:c.close()
 for category in KEYS:record(f'{category}: legacy migration, cancellation, exact durable deletion, isolation and empty export',lambda category=category:deletion(category))

 def linked_backend():
  c,p=fresh();a=c.request.post(API+'/api/mental/sessions',data={'summaryText':'Synthetic owned deletion','recurringThemes':[],'saveMentalSummaries':True}).json()
  b=c.request.post(API+'/api/mental/sessions',data={'summaryText':'Other owner synthetic record','recurringThemes':[],'saveMentalSummaries':True}).json()
  try:
   assert a['sessionId']!=b['sessionId'] and a['deletionToken']!=b['deletionToken']
   forbidden=c.request.delete(API+'/api/mental/sessions/'+b['sessionId'],data={'deletionToken':a['deletionToken']});assert forbidden.status==404
   assert all('deletionToken' not in r for r in c.request.get(API+'/api/mental/sessions').json())
   seed(p,'mental',{'backendSessionId':a['sessionId'],'backendDeletionToken':a['deletionToken']});p.reload();panel=p.locator('[data-record-history=mental]');expect(panel.locator('[data-record-id]')).to_have_count(2)
   p.route('**/api/mental/sessions/**',lambda r:r.fulfill(status=503,json={'detail':'controlled backend unavailable'}))
   panel.locator('[data-record-id=new-mental]').get_by_role('button',name='kaydını sil:').click();p.get_by_role('button',name='Evet, sil',exact=True).click();expect(p.get_by_role('dialog')).to_contain_text('Yerel kayıt korundu');assert len(p.evaluate('(k)=>JSON.parse(localStorage.getItem(k))',KEYS['mental'][0]))==2
   p.unroute('**/api/mental/sessions/**');p.get_by_role('button',name='Evet, sil',exact=True).click();expect(panel.locator('[data-record-id]')).to_have_count(1)
   remaining=c.request.get(API+'/api/mental/sessions').json();assert a['sessionId'] not in [r['sessionId'] for r in remaining] and b['sessionId'] in [r['sessionId'] for r in remaining]
   assert c.request.delete(API+'/api/mental/sessions/'+a['sessionId'],data={'deletionToken':a['deletionToken']}).json()=={'deleted':True}
   return {'failurePreservesLocal':True,'retryDeletesBoth':True,'otherOwnerPreserved':True,'capabilityNotExposed':True,'idempotentRetry':True}
  finally:c.close()
 record('Linked backend deletion: truthful failure, safe retry, capability isolation and persistent removal',linked_backend)

 def reference():
  c,p=fresh()
  try:
   seed(p,'skin');p.reload();expect(p.locator('[data-record-history=skin] [data-record-id]')).to_have_count(2);records=p.evaluate('(k)=>JSON.parse(localStorage.getItem(k))',KEYS['skin'][0]);rid=records[0]['id'];records[1]['baselineId']=rid
   p.evaluate('([records,id])=>{localStorage.setItem("togg_health_skin_history",JSON.stringify(records));localStorage.setItem("togg_health_skin_baseline","{}");localStorage.setItem("togg_health_skin_baseline_meta",JSON.stringify({id}));}',[records,rid]);p.reload()
   panel=p.locator('[data-record-history=skin]');panel.locator('[data-record-id]').first.get_by_role('button').click();p.get_by_role('button',name='Evet, sil',exact=True).click();expect(panel).to_contain_text('Yeni bir cilt referansı gerekiyor')
   surviving=p.evaluate('(k)=>JSON.parse(localStorage.getItem(k))',KEYS['skin'][0]);assert len(surviving)==1 and surviving[0]['referenceDeleted'] and surviving[0]['comparisonUnavailable']
   assert p.evaluate('localStorage.getItem("togg_health_skin_baseline")') is None;p.reload();expect(panel).to_contain_text('referansı silindi')
   return {'otherAnalysisPreserved':True,'referenceRemoved':True,'dependentComparisonInvalidated':True}
  finally:c.close()
 record('Deleting a skin reference invalidates comparisons and preserves other analyses',reference)

 def conversation():
  c,p=fresh(controlled=True);posts=[]
  try:
   p.goto(BASE+'/mental');p.on('request',lambda r:posts.append(r.url) if r.method=='POST' and '/mental/' in r.url else None)
   expect(p.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True)).not_to_be_checked();expect(p.get_by_role('button',name='Görüşmeyi Başlat',exact=True)).to_be_disabled()
   assert p.get_by_role('combobox').count()==0 and p.get_by_role('checkbox').count()==1
   assert p.evaluate('window.recognitionProof')==[] and posts==[]
   p.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();p.get_by_role('button',name='Görüşmeyi Başlat',exact=True).click();expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','permission')
   p.evaluate('window.controlledRecognition.onstart()');expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','listening')
   p.route('**/api/mental/speech',lambda r:r.fulfill(status=200,content_type='audio/mpeg',body=CONTROLLED_AUDIO))
   p.evaluate('window.controlledRecognition.onresult({resultIndex:0,results:[Object.assign([{transcript:"Bugün yeni bir kitap okudum."}],{isFinal:true})]})')
   expect(p.locator('[data-chat-author=USER]')).to_have_count(1);expect(p.locator('[data-chat-author=AI]')).to_have_count(1)
   p.wait_for_function('window.audioProof.some(e=>e.type==="playing")');assert p.evaluate('window.recognitionProof.filter(e=>e==="requested").length')==1
   p.wait_for_function('window.audioProof.some(e=>e.type==="ended")');expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','permission')
   p.evaluate('window.controlledRecognition.onstart()');expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','listening')
   pending=[];p.route('**/api/mental/converse',lambda r:pending.append(r));p.evaluate('window.controlledRecognition.onresult({resultIndex:0,results:[[{transcript:"Sentetik gecikmiş tur"}]]})');p.wait_for_timeout(150);assert len(pending)==1
   p.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).uncheck();pending[0].fulfill(json={'reply':'late prohibited response','providerType':'LIVE_OPENAI'});p.wait_for_timeout(500)
   assert p.locator('[data-live-transcript]').count()==0 and len(p.evaluate('window.audioProof.filter(e=>e.type==="playing")'))==1
   assert p.evaluate('localStorage.getItem("togg_health_mental_history")') is None and p.evaluate('window.captureAttempts')==0
   expect(p.get_by_role('button',name='Görüşmeyi Başlat',exact=True)).to_be_disabled();snap(p,'mental-service-revoked')
   p.unroute('**/api/mental/converse');p.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();p.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click();p.get_by_role('button',name='Sesli yanıtı kapat',exact=True).click()
   p.get_by_role('textbox',name='Görüşme mesajı').fill('Bugün yeni bir kitap okudum.');p.get_by_role('button',name='Gönder',exact=True).click();expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','ready');p.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed');expect(p.locator('[data-session-rows]')).to_be_visible();assert p.locator('[data-current-summary]').count()==0
   p.get_by_role('dialog',name='Görüşme tamamlandı',exact=True).get_by_role('button',name='Tamam',exact=True).click()
   other=c.new_page();other.goto(BASE+'/profile');other.locator('[data-record-history=mental]').get_by_role('button',name='kaydını sil:').click();other.get_by_role('button',name='Evet, sil',exact=True).click()
   expect(p.locator('[data-current-summary]')).to_have_count(0);expect(p.locator('[data-mental-record-panel]')).to_contain_text('0 kayıtlı görüşme');expect(p.get_by_role('img',name='Görüşme tema payları')).to_have_count(0);other.close()
   return {'singleConsentDefaultOff':True,'automaticSpeech':True,'permissionPendingTruthful':True,'noCaptureDuringAudio':True,'resumeAfterEnded':True,'lateOutputAfterRevokeBlocked':True,'currentSummaryAndChartRemovedAfterDeletion':True,'physicalCapture':0,'fixtureAudioSha256':hashlib.sha256(CONTROLLED_AUDIO).hexdigest(),'liveAcceptance':False}
  finally:c.close()
 record('Single service consent, direct start, automatic audio, echo guard, resume and revocation',conversation)

 browser.close()
proof={'results':results,'sourceHead':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'buildId':Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'generation':'controlled synthetic UI fixture; not live OpenAI','physicalCapture':False,'actualImageReviewPending':True}
(OUT/'results.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
raise SystemExit(any(r['status']!='PASS' for r in results))
