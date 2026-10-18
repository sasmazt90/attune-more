"""Actual production UI/audio cancellation; disposable profiles, no human acceptance."""
import json,math,tempfile,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,str(Path.cwd()/'tests/e2e'))
from owned_window_capture import capture_owned_window
OUT=Path('audit-results/feedback-four-modules-20261009/ui-cancel');OUT.mkdir(exist_ok=True)
INIT="window.audioStarts=[];const start=AudioBufferSourceNode.prototype.start;AudioBufferSourceNode.prototype.start=function(...a){audioStarts.push(performance.now());return start.apply(this,a);};window.guidance=[];window.addEventListener('attune-guidance-event',e=>guidance.push({...e.detail,at:performance.now()}));"
proof=[]
with sync_playwright() as pw:
 for mode in ('desktop','narrow','native200'):
  profile=tempfile.TemporaryDirectory(prefix='attune-feedback-ui-')
  if mode=='native200':
   pref=Path(profile.name)/'Default';pref.mkdir();(pref/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(2)/math.log(1.2)}}}),'utf8')
  c=pw.chromium.launch_persistent_context(profile.name,channel='chrome',headless=mode!='native200',no_viewport=mode=='native200',viewport=None if mode=='native200' else {'width':720 if mode=='narrow' else 1920,'height':900 if mode=='narrow' else 1080},args=['--window-size=1600,1000','--autoplay-policy=no-user-gesture-required'])
  c.add_init_script(INIT);p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
  p.goto('http://127.0.0.1:3000/hearing');p.get_by_label('Yerel ses testi işlemini başlatmayı kabul ediyorum.').check()
  def prepare():
   p.get_by_role('button',name='Ses hazırlığını başlat').click();expect(p.get_by_role('button',name='Sol kanalı dinle')).to_be_enabled(timeout=20000)
   for ear in ('sol','sağ'):
    p.get_by_role('button',name=ear.capitalize()+' kanalı dinle').click();check=p.get_by_label('Yalnız '+ear+' kulağımda duydum.');expect(check).to_be_enabled(timeout=10000);check.check()
   p.get_by_role('button',name='Gürültüde Türkçe sayılar',exact=True).click()
  prepare();expect(p.locator('[data-din-countdown]')).to_have_text('5',timeout=20000)
  stop=p.get_by_role('button',name='Durdur',exact=True);stop.scroll_into_view_if_needed()
  geometry=p.evaluate('({innerWidth,outerWidth,dpr:devicePixelRatio,cssZoom:getComputedStyle(document.documentElement).zoom,scroll:document.documentElement.scrollWidth})')
  assert geometry['scroll']<=geometry['innerWidth'],geometry
  if mode=='native200':assert geometry['dpr']>=2 and geometry['innerWidth']<geometry['outerWidth']*.65 and geometry['cssZoom']=='1'
  keypad=p.locator('[data-din-keypad]');boxes=keypad.locator('button').evaluate_all('(a)=>a.map(e=>({text:e.innerText,...e.getBoundingClientRect().toJSON()}))')
  assert [v['text'] for v in boxes]==['1','2','3','4','5','6','7','8','9','Durdur','0','Son Sayıyı Sil','Yanıtı Gönder']
  for row in range(4):assert max(v['y'] for v in boxes[row*3:row*3+3])-min(v['y'] for v in boxes[row*3:row*3+3])<1
  assert abs(boxes[-1]['width']-keypad.bounding_box()['width'])<1
  if mode=='native200':capture_owned_window(p,profile.name,OUT/f'{mode}-keypad.png')
  else:p.screenshot(path=str(OUT/f'{mode}-keypad.png'),full_page=True)
  before=p.evaluate('audioStarts.length');stop.click();p.wait_for_timeout(6500)
  assert p.evaluate('audioStarts.length')==before and p.locator('[data-din-countdown]').count()==0
  assert p.evaluate('localStorage.getItem("attune_hearing_history_v1")') is None
  prepare();expect(p.get_by_role('textbox',name='Üç sayı yanıtı')).to_be_enabled(timeout=25000)
  for number in ('1','2','3'):p.get_by_role('button',name=number,exact=True).click()
  p.get_by_role('button',name='Son Sayıyı Sil').click();expect(p.get_by_role('textbox',name='Üç sayı yanıtı')).to_have_value('12')
  expect(p.get_by_role('button',name='Yanıtı Gönder')).to_be_disabled();before=p.evaluate('audioStarts.length');p.get_by_role('button',name='Durdur',exact=True).click();p.wait_for_timeout(1500)
  assert p.evaluate('audioStarts.length')==before and p.evaluate('localStorage.getItem("attune_hearing_history_v1")') is None
  p.goto('http://127.0.0.1:3000/profile');p.locator('[data-health-module]').first.click()
  headings=[]
  for module in ('vision','skin','dental','hearing','mental'):
   p.locator('[data-health-history] select').first.select_option(module);h=p.locator('#health-history-analysis h2');expect(h).to_be_visible()
   info=h.locator('xpath=..').locator('summary');box=h.bounding_box();ib=info.bounding_box();assert 0<=ib['x']-box['x']-box['width']<=20
   info.click();expect(h.locator('xpath=..').locator('details')).to_have_attribute('open','')
   assert p.evaluate('document.documentElement.scrollWidth<=innerWidth');headings.append(h.inner_text())
  p.screenshot(path=str(OUT/f'{mode}-history-heading.png'),full_page=True)
  assert not errors,errors
  proof.append({'mode':mode,'geometry':geometry,'keypad':boxes,'countdownCancelNoStimulus':True,'answerCancelNoRecord':True,'deleteLastOnly':True,'historyHeadings':headings,'pageErrors':errors})
  c.close();profile.cleanup()
 (OUT/'proof.json').write_text(json.dumps({'status':'PASS','buildId':Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'physicalAcceptance':False,'runs':proof},indent=2),'utf8')
print('PASS desktop/narrow/native200 keypad, real countdown cancellation, five history heading anchors')
