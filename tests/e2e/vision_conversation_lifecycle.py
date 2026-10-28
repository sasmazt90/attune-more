"""Additional production sequential-turn retry/interruption checks, explicit ASR/model fixtures."""
import importlib.util,json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
spec=importlib.util.spec_from_file_location('vision_conversation',Path(__file__).with_name('vision_conversation.py'));M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=os.getenv('CHROME_PATH') or None,channel=None if os.getenv('CHROME_PATH') else 'chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required','--no-sandbox'])
 try:
  for lang in ['tr','en','de']:
   c=b.new_context(viewport={'width':1440,'height':1000});c.add_init_script(M.SEED+M.BOOT+M.OBSERVE+f"localStorage.setItem('attune.language.v1','{lang}');")
   p=c.new_page();p.goto(M.BASE+'/vision');p.get_by_role('button',name=M.label('Başlat',lang),exact=True).click();M.ready(p)
   M.exercise_lifecycle(p,lang);assert p.evaluate('probe.overlaps')==[]
   # Existing service cancellation must tear down all tracks and leave no incomplete history.
   p.evaluate("localStorage.setItem('attune_privacy_camera_allowed','false');window.dispatchEvent(new Event('attune-privacy'))")
   p.wait_for_function("()=>probe.streams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))");assert p.evaluate("localStorage.getItem('togg_health_latest_vision')")==None
   print('PASS',lang,'bounded retries, follow-up interruption, spoken resume, retained letter, camera consent cleanup',flush=True);c.close()
  (M.OUT/'lifecycle-browser.json').write_text(json.dumps({'kind':'actual production browser/native audio; simulated camera/model/ASR','checks':M.checks},indent=2)+'\n')
 finally:b.close()
