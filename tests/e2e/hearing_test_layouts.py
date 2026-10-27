"""Actual Hearing presentation UI layout, with one real PCM press then explicit stop.
Partial engineering sessions do not replace the separate full14-round PCM proof.
"""
import json,os,math,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2];OUT=Path(os.environ.get('HEARING_LAYOUT_EVIDENCE','audit-results/hearing-test-layouts'));OUT.mkdir(parents=True,exist_ok=True)
M={v['tr']:v for v in json.loads((ROOT/'shared/localization/messages.json').read_text()).values()};BROWSER={'executable_path':os.environ['ATTUNE_BROWSER_EXECUTABLE']} if os.getenv('ATTUNE_BROWSER_EXECUTABLE') else {'channel':'chrome'}
INIT='''window.pcm=[];const start=AudioBufferSourceNode.prototype.start;AudioBufferSourceNode.prototype.start=function(...args){const row={ended:false};pcm.push(row);this.addEventListener('ended',()=>row.ended=true);return start.apply(this,args);};'''
checks=[];errors=[]
def scenario(c,language,label,native=False):
 t=lambda s:M.get(s,{}).get(language,s)
 c.add_init_script(INIT);p=c.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.goto('http://127.0.0.1:3000/hearing');p.locator('header select').select_option(language)
 p.get_by_label(t('Kulaklık sesleri ve yanıtlarımla yerel işitme testinin yapılmasına izin veriyorum.')).check();p.get_by_role('button',name=t('İzin ver ve devam et'),exact=True).click();p.get_by_role('button',name=t('Ses hazırlığını başlat'),exact=True).click();expect(p.get_by_role('button',name=t('Sol kanalı dinle'))).to_be_enabled(timeout=25000)
 for ear in ['sol','sağ']:
  p.get_by_role('button',name=t(ear.capitalize()+' kanalı dinle')).click();node=p.get_by_label(t('Yalnız '+ear+' kulağımda duydum.'));expect(node).to_be_enabled(timeout=10000);node.check()
 p.get_by_role('button',name=t('Saf ses testi'),exact=True).click();expect(p.get_by_role('button',name=t('Duydum'),exact=True)).to_be_visible(timeout=15000);p.wait_for_function('pcm.length>=3&&!pcm[pcm.length-1].ended',timeout=30000);p.get_by_role('button',name=t('Duydum'),exact=True).click();expect(p.locator('[data-hearing-previous-trial]')).to_have_count(1,timeout=10000)
 trial=p.locator('[data-hearing-previous-trial]').get_attribute('data-hearing-previous-trial');old=p.locator('[data-hearing-previous-panel] [role="meter"]').get_attribute('aria-valuenow');current=p.locator('[data-hearing-current-panel] [role="meter"][aria-valuemin="-90"]').get_attribute('aria-valuenow');assert old!=current,(old,current)
 for width in ([None] if native else [1440,768,375]):
  if width:p.set_viewport_size({'width':width,'height':1000})
  d=p.evaluate('({inner:innerWidth,outer:outerWidth,scroll:document.documentElement.scrollWidth,dpr:devicePixelRatio,cssZoom:getComputedStyle(document.documentElement).zoom})');assert d['scroll']<=d['inner'],d
  if native:assert d['dpr']>=2 and d['inner']<d['outer']*.65 and d['cssZoom']=='1',d
  p.screenshot(path=str(OUT/(label+'-'+str(width or 'native200')+'.png')),full_page=True);assert p.locator('[data-hearing-previous-trial]').get_attribute('data-hearing-previous-trial')==trial
  checks.append({'status':'PASS','language':language,'dimensions':d,'previousTrialId':trial,'previousLevel':old,'nextPlannedLevel':current,'previousDidNotBecomeCurrent':True})
 p.get_by_role('checkbox',name=t('Testi durdur'),exact=True).click();expect(p.get_by_role('button',name=t('Duydum'),exact=True)).to_have_count(0);assert p.evaluate('localStorage.getItem("attune_hearing_latest_v1")') is None;c.close()
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True,**BROWSER)
 for lang in ['tr','en','de']:scenario(b.new_context(viewport={'width':1440,'height':1000}),lang,lang)
 b.close()
 with tempfile.TemporaryDirectory(prefix='attune-hearing-active-zoom-') as profile:
  pref=Path(profile)/'Default';pref.mkdir();(pref/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(2)/math.log(1.2)}}}))
  scenario(pw.chromium.launch_persistent_context(profile,headless=False,no_viewport=True,args=['--window-size=1600,1000'],**BROWSER),'tr','tr',True)
 assert not errors,errors
 (OUT/'proof.json').write_text(json.dumps({'status':'PASS','buildId':(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'checks':checks,'pageErrors':errors,'partialSessionsExplicitlyStopped':True,'physicalListeningAcceptance':False},indent=2))
print('PASS actual TR/EN/DE test panels at1440/768/375 and native200%, immutable previous response, explicit cancellation')
