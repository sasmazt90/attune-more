"""Route exit/restart while a native follow-up is playing; controlled ASR/model only."""
import importlib.util,json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
spec=importlib.util.spec_from_file_location('vision_conversation',Path(__file__).with_name('vision_conversation.py'));M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=os.getenv('CHROME_PATH') or None,channel=None if os.getenv('CHROME_PATH') else 'chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required','--no-sandbox'])
 try:
  c=b.new_context(viewport={'width':1440,'height':1000});c.add_init_script(M.SEED+M.BOOT+M.OBSERVE);p=c.new_page();p.goto(M.BASE+'/vision');p.get_by_role('button',name='Başlat',exact=True).click();M.ready(p)
  v=M.target(p);p.evaluate('()=>{probe.oldResult=probe.current.onresult;probe.waitAfter=performance.now();}');M.emit(p,M.word(v,'tr'));M.next_prompt(p,'orientation');p.wait_for_function('()=>probe.audios.some(a=>!a.paused)')
  p.locator('a[href="/profile"]').first.click();p.wait_for_url('**/profile');p.wait_for_function("()=>probe.streams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))&&probe.audios.every(a=>a.paused)&&probe.recognitions.every(r=>r.aborted||!r.started)")
  p.evaluate('()=>{probe.oldResult({resultIndex:0,results:[Object.assign([{transcript:"E düz",confidence:.99}],{isFinal:true})]});}');assert p.evaluate("localStorage.getItem('togg_health_latest_vision')")==None
  p.goto(M.BASE+'/vision');p.get_by_role('button',name='Başlat',exact=True).click();p.wait_for_function('()=>probe.streams.length>0');p.evaluate("localStorage.setItem('attune_privacy_camera_allowed','false');window.dispatchEvent(new Event('attune-privacy'))");p.wait_for_function("()=>probe.streams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))");assert p.evaluate("localStorage.getItem('togg_health_latest_vision')")==None
  result={'status':'PASS','kind':'production UI/native audio with controlled camera/model/ASR','routeExitDuringFollowUp':True,'lateFinalAfterUnmountRejected':True,'restartThenCameraConsentWithdrawal':True,'incompleteHistorySaved':False}
  (M.OUT/'cleanup-browser.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 finally:b.close()
