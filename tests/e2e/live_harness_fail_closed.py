"""Real production UI and browser permission, zero cloud/network dispatch."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from live_provider_admission import LiveAdmission,TEXTS
out=Path('audit-results/live-harness-fail-closed.json');results=[]
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome' if __import__('os').name=='nt' else 'chromium',headless=True)
 for case in ['source-not-verified','unexpected-user','unexpected-history']:
  c=b.new_context();page=c.new_page();cdp=c.new_cdp_session(page)
  cdp.send('Browser.setPermission',{'permission':{'name':'microphone'},'setting':'denied','origin':'http://localhost:3000','browserContextId':cdp.send('Target.getTargetInfo')['targetInfo']['browserContextId']})
  gate=LiveAdmission(case!='source-not-verified');intercepted=[];forwarded=[]
  def intercept(route):
   if route.request.method!='POST':route.continue_();return
   data=route.request.post_data_json;intercepted.append(route.request.url)
   if case=='unexpected-history':data['history']=[{'role':'user','content':'Sentetik izin dışı geçmiş'}]
   try:
    gate.admit('/v1/chat/completions',{'messages':[{'role':'system','content':'Sen Togg araç içi Ruhsal İyi Oluş Asistanısın.'}]+data.get('history',[])+[{'role':'user','content':data.get('userMessage')}]})
    forwarded.append(True);route.continue_()
   except Exception:route.abort()
  page.route('**/api/mental/**',intercept)
  try:
   c.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0})
   page.goto('http://localhost:3000/mental');assert page.evaluate('navigator.permissions.query({name:"microphone"}).then(p=>p.state)')=='denied'
   expect(page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True)).not_to_be_checked()
   page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check()
   page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click()
   page.get_by_role('textbox',name='Görüşme mesajı').fill('Sentetik izin dışı kitap cümlesi.' if case=='unexpected-user' else TEXTS[0]);page.get_by_role('button',name='Gönder',exact=True).click()
   expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','error')
   assert len(intercepted)==1 and not forwarded and sum(gate.counts.values())==0
   assert page.evaluate('localStorage.getItem("togg_health_mental_history")') is None
   results.append({'case':case,'status':'PASS','physicalMicrophone':'denied','forwardedBackendRequests':0,'providerRequests':0,'records':0,'gate':gate.proof()})
  finally:c.close()
 b.close()
out.write_text(json.dumps(results,indent=2),encoding='utf-8');print(json.dumps(results))
