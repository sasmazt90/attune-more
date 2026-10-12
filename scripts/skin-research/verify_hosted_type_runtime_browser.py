"""Complete only pending runtime controls; reuse hash-identical passed stages.
Actual fixture/MediaPipe/UI/API, recorded provider, no live hosted photo calls.
"""
from pathlib import Path
source=Path(__file__).with_name('verify_hosted_type_browser.py')
# Shared audited fixture/crop observation functions, without its full campaign.
exec(compile(source.read_text('utf8').split('with sync_playwright() as pw, ExitStack() as cleanup:')[0],str(source),'exec'),globals())
stages=json.loads((OUT/'completed-stages.json').read_text('utf8'))
assert stages['buildId']==(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip()
for name,digest in stages['backendSourceHashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
assert hashlib.sha256(source.read_bytes()).hexdigest()==stages['executedScriptSHA256']
assert hashlib.sha256((ROOT/'audit-fixtures/three-angle.y4m').read_bytes()).hexdigest()==stages['fixtureSHA256']
errors=[];console=[];retries=[]
def wait_actual(page,condition,label):
 end=time.monotonic()+150;count=0
 while not condition() and time.monotonic()<end:
  page.wait_for_timeout(500)
  button=page.get_by_role('button',name='Tekrar Dene',exact=True)
  body=page.locator('body').inner_text()
  if button.count() and 'Cilt analiz motoru' in body and count<2:
   retries.append(dict(control=label,action='Actual UI Tekrar Dene',reason=body,qualityOverride=False));count+=1
   button.click();page.wait_for_function('document.querySelector("canvas")?.dataset.mediapipeReady==="true"',timeout=90000);start(page)
  elif page.get_by_role('button',name='Analizi Başlat',exact=True).count() and page.get_by_text('PARK',exact=True).count() and count<2:
   retries.append(dict(control=label,action='Actual UI start after PARK restored',qualityOverride=False));count+=1;start(page)
 assert condition(),dict(control=label,body=page.locator('body').inner_text())
def finish(page):
 wait_actual(page,lambda:page.get_by_text('Cilt Analizi Tamamlandı',exact=True).count()>0,'complete')
 return page.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))')
with sync_playwright() as pw, ExitStack() as cleanup:
 browser=pw.chromium.launch(channel='chrome',headless=True,args=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(ROOT/'audit-fixtures/three-angle.y4m'),'--enable-unsafe-swiftshader']);cleanup.callback(browser.close)
 context=browser.new_context(permissions=['camera'],viewport={'width':1600,'height':1000});context.add_init_script(INIT)
 def route(r):
  target='http://127.0.0.1:8103/'+r.request.url.split(':8000/',1)[1];response=r.fetch(url=target,timeout=60000);r.fulfill(response=response)
 context.route('http://localhost:8000/**',route);context.route('http://127.0.0.1:8000/**',route)
 context.request.post('http://127.0.0.1:8103/api/vehicle/speed',data={'speedKmH':0})
 page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)));page.on('console',lambda message:console.append(dict(type=message.type,text=message.text[:1000])))
 page.goto('http://127.0.0.1:3000/privacy');page.get_by_label(PERMISSION,exact=True).check();page.get_by_label('Cilt ölçümlerini ve kişisel sayısal referansı bu tarayıcıda sakla',exact=True).check()
 baseline=len(provider_state()['calls']);mode('normal');configure_front(page);start(page);record=finish(page);assert record['general']['skinType']['value']=='normal';seed=summary(page,record)
 history(page,record,'Normal')
 # Load the revocation UI before the bounded request starts. Under paging,
 # opening a new tab can outlast the 15s request and test completed history.
 privacy=context.new_page();privacy.goto('http://127.0.0.1:3000/privacy');expect(privacy.get_by_label(PERMISSION,exact=True)).to_be_checked()
 mode('timeout');before=len(provider_state()['calls']);previous=record['id'];configure_front(page);start(page)
 wait_actual(page,lambda:len(provider_state()['calls'])>before,'revoke-in-flight')
 expect(page.get_by_role('button',name='Taramayı İptal Et',exact=True)).to_be_visible()
 privacy.get_by_label(PERMISSION,exact=True).uncheck()
 expect(page.get_by_role('button',name='Analizi Başlat',exact=True)).to_be_visible(timeout=3000)
 page.wait_for_timeout(17000);assert page.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin")).id')==previous
 expect(page.get_by_role('button',name='Analizi Başlat',exact=True)).to_be_visible();privacy.close()
 mode('normal');before=len(provider_state()['calls']);start(page);record=finish(page);assert record['general']['skinType']['limitationCode']=='HOSTED_INFERENCE_PERMISSION_DENIED' and len(provider_state()['calls'])==before
 revoked=summary(page,record)
 page.goto('http://127.0.0.1:3000/privacy');page.get_by_label(PERMISSION,exact=True).check()
 mode('timeout');before=len(provider_state()['calls']);previous=record['id'];configure_front(page);start(page)
 wait_actual(page,lambda:len(provider_state()['calls'])>before,'cancel-in-flight')
 page.get_by_role('button',name='Taramayı İptal Et',exact=True).click();page.wait_for_timeout(17000)
 assert page.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin")).id')==previous
 mode('normal');start(page);record=finish(page);assert record['id']!=previous and record['general']['skinType']['value']=='normal';replacement=summary(page,record)
 assert not errors,errors
 assert len(provider_state()['calls'])==baseline+4
 proof=dict(status='PASS',buildId=stages['buildId'],reusedStages=stages,actualMediaPipe=True,qualityOverride=False,poseMock=False,recordedProviderReplay=True,newLiveHostedRequests=0,fixtureSubjectClassificationAccuracyNotMeasured=True,normalUserHistoryTouched=False,seed=seed,revocation=revoked,replacement=replacement,cancelAndReplaceProtected=True,providerRequests=provider_state()['calls'][baseline:],pageErrors=errors,cameraUIRetries=retries)
 (OUT/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf8');context.close();browser.close()
 print(json.dumps(dict(status='PASS',buildId=proof['buildId'],newLiveHostedRequests=0,cancelAndReplaceProtected=True,cameraUIRetries=len(retries))))
