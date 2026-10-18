"""Real control endpoint/UI, keyless summary fixture; no physical mic or paid calls."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path('audit-results/user-followup-20261005/mental');OUT.mkdir(parents=True,exist_ok=True)
proof=[]
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True)
 for width in (390,1600):
  c=b.new_context(viewport={'width':width,'height':1000});c.add_init_script("navigator.mediaDevices.getUserMedia=()=>{throw Error('Physical capture forbidden')};const S=window.SpeechRecognition||window.webkitSpeechRecognition;if(S)S.prototype.start=()=>{throw Error('Physical STT forbidden')};")
  p=c.new_page();c.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0});p.goto('http://localhost:3000/mental');expect(p.get_by_role('main').get_by_text('Ruhsal İyi Oluş',exact=True)).to_be_visible()
  p.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();p.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click();p.get_by_role('button',name='Sesli yanıtı kapat',exact=True).click()
  box=p.get_by_role('textbox',name='Görüşme mesajı');box.fill('Sonra gelirim');p.get_by_role('button',name='Gönder',exact=True).click();expect(p.locator('[data-chat-author=AI]')).to_contain_text('ara vermek mi')
  expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','ready');p.screenshot(path=str(OUT/f'active-{width}.png'),full_page=True)
  box.fill('Görüşmeyi duraklat');p.get_by_role('button',name='Gönder',exact=True).click();expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','paused');expect(box).to_be_disabled()
  assert p.evaluate('localStorage.getItem("togg_health_mental_history")') is None;p.screenshot(path=str(OUT/f'paused-{width}.png'),full_page=True)
  p.get_by_role('button',name='Devam et',exact=True).click();expect(box).to_be_enabled();p.get_by_role('button',name='Duraklat',exact=True).click();expect(box).to_be_disabled();p.get_by_role('button',name='Devam et',exact=True).click()
  p.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();expect(p.get_by_role('dialog',name='Görüşme tamamlandı')).to_be_visible();p.get_by_role('button',name='Tamam',exact=True).click()
  expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed');expect(p.locator('[data-session-rows] [data-record-id]')).to_have_count(1);p.screenshot(path=str(OUT/f'finished-{width}.png'),full_page=True)
  proof.append({'width':width,'clarificationNotEmotion':True,'explicitActionMatchesPausedUI':True,'resumeThenFinish':True,'oneSummary':True,'physicalCapture':0,'paidCalls':0,'liveGenerationAcceptance':False});c.close()
 b.close()
(OUT/'proof.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))
