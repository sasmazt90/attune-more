"""Keyless real UI/backend: deliver verified response before admitting next TTS.
No real OpenAI/TTS acceptance claimed; keyless speech fixture deliberately makes speech 503; old paid admission harness is historical.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from live_provider_admission import LiveAdmission,TEXTS,forward_admitted_response
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chromium',headless=True);c=b.new_context();page=c.new_page();gate=LiveAdmission(True);records=[]
 def guard(route):
  if route.request.method=='GET':route.continue_();return
  d=route.request.post_data_json;path=route.request.url.rsplit('/',1)[-1]
  if path=='converse':kind=gate.admit('/v1/chat/completions',{'messages':[{'role':'system','content':'Sen Togg araç içi Ruhsal İyi Oluş Asistanısın.'}]+d['history']+[{'role':'user','content':d['userMessage']}]})
  elif path=='speech':kind=gate.admit('/v1/audio/speech',{'input':d['text'],'voice':'coral','response_format':'mp3'})
  else:route.abort();return
  forward_admitted_response(route,gate,kind,lambda kind,data,res:records.append({'kind':kind,'httpStatus':res.status,'providerType':data.get('providerType') if data else None}),expected_provider='LIVE_OPENAI')
 page.route('**/api/mental/**',guard)
 try:
  page.goto('http://localhost:3000/mental');page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click()
  page.get_by_role('textbox',name='Görüşme mesajı').fill(TEXTS[0]);page.get_by_role('button',name='Gönder',exact=True).click()
  expect(page.get_by_text('Microsoft tr-TR-EmelNeural seslendirmesine ulaşılamadı. Sesli yanıt başarısız. Yanıtı metin olarak okuyabilirsiniz.',exact=True)).to_be_visible()
  assert gate.counts=={'conversation':1,'tts':1,'summary':0}
  assert gate.blocked==['PROVIDER_FAILED_NO_RETRY'] and records==[{'kind':'conversation','httpStatus':200,'providerType':'LIVE_OPENAI'},{'kind':'tts','httpStatus':503,'providerType':None}]
  assert page.evaluate('localStorage.getItem("togg_health_mental_history")') is None
  proof={'status':'PASS','mode':'keyless real backend/UI ordering check','realOpenAIRequests':0,'realOpenAITTSRequests':0,'records':records,'gate':gate.proof(),'liveAcceptanceClaim':False}
  Path('audit-results/live-harness-order.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))
 finally:c.close();b.close()
