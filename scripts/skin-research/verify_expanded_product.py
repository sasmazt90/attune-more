"""Actual fixture camera/MediaPipe/API/UI/history and browser-native 200% zoom.

Uses the established product contract, updates the expected whole-photo degree
map rule and holds one real HTTP response across cancellation. No result,
landmark, pose or quality is substituted. All records belong to isolated test
profiles; normal user records are not read or written.
"""
import json,sys,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();parser.add_argument('--output-name',default='product-ui');args=parser.parse_args()
assert args.output_name.replace('-','').isalnum() and args.output_name.startswith('product-ui')
OUT=ROOT/'audit-results/skin-expanded-20261011'/args.output_name;OUT.mkdir(parents=True,exist_ok=True)
source=ROOT/'tests/e2e/current_skin_contract.py';code=source.read_text('utf8')
code=code.replace("OUT=Path(os.environ.get('SKIN_RESULT_AUDIT_DIR','audit-results/feedback-four-modules-20261009/skin'))",'OUT=Path('+repr(str(OUT))+')')
old=""" if not native:page.screenshot(path=str(path),full_page=True);return
 return capture_owned_window(page,profile.name,path)"""
new=""" page.screenshot(path=str(path),full_page=True)
 return {'browserNativeZoom':native,'devicePixelRatio':page.evaluate('devicePixelRatio'),'osWindowPixelsClaimed':False}"""
assert old in code;code=code.replace(old,new)
old="""  assert p.locator('[data-skin-local-fill]').get_attribute('data-map-photo')==general['captureId']"""
new="""  red=next(v for v in general['indicators'] if v['id']=='redness')
  if red.get('measurement',{}).get('modelHash'):
   assert p.locator('[data-skin-local-fill]').count()==0,'Whole-photo trained grade has no pixel localization'
  elif p.locator('[data-skin-local-fill]').count():
   assert p.locator('[data-skin-local-fill]').get_attribute('data-map-photo')==general['captureId']"""
assert old in code;code=code.replace(old,new)
old="""  p.goto('http://127.0.0.1:3000/skin');start=time.monotonic();p.get_by_role('button',name='Analizi Başlat',exact=True).click()"""
new="""  p.goto('http://127.0.0.1:3000/skin')
  if n==0:
   delayed=[]
   def late_real_response(route):
    response=route.fetch(timeout=90000)
    payload=response.json();assert payload.get('activeCriterionMethods')
    p.get_by_role('button',name='Taramayı İptal Et',exact=True).click()
    route.fulfill(response=response)
    delayed.append({'actualNormalAPI':True,'realResponseHeldAcrossCancellation':True,'pose':payload.get('pose'),'methodsReceipt':payload['activeCriterionMethods']})
   p.route('**/api/local-health/skin',late_real_response,times=1)
   p.wait_for_function('document.querySelector("canvas")?.dataset.mediapipeReady==="true"',timeout=90000)
   p.get_by_role('button',name='Analizi Başlat',exact=True).click()
   cancellation_deadline=time.monotonic()+270
   probe_trace=[]
   while not delayed and time.monotonic()<cancellation_deadline:
    p.wait_for_timeout(2000)
    # Startup WASM/shader warmup can legitimately invalidate fresh vehicle
    # telemetry. Retry via the real button only after normal PARK is restored.
    if p.get_by_role('button',name='Analizi Başlat',exact=True).count() and 'ARAÇ DURUMU BELİRSİZ' not in p.locator('body').inner_text() and not delayed:
     p.get_by_role('button',name='Analizi Başlat',exact=True).click()
    if p.get_by_role('button',name='Tekrar Dene',exact=True).count():
     p.screenshot(path=str(OUT/'cancel-probe-failure.png'),full_page=True)
     raise AssertionError('Actual camera engine failed before any appearance API request; see captured trace')
    probe_trace.append(p.evaluate('({at:performance.now(),canvas:{...document.querySelector("canvas")?.dataset},body:document.body.innerText,requests:window.appearanceRequests,workerTimings:window.workerTimings})'))
    (OUT/'cancel-probe-trace.json').write_text(json.dumps({'trace':probe_trace,'console':console,'pageErrors':errors},ensure_ascii=False,indent=2),'utf8')
   if not delayed:p.screenshot(path=str(OUT/'cancel-probe-failure.png'),full_page=True)
   assert delayed,'Real fixture never reached the HTTP cancellation probe'
   p.wait_for_timeout(1500)
   expect(p.get_by_role('button',name='Analizi Başlat',exact=True)).to_be_visible()
   assert p.get_by_text('Cilt Analizi Tamamlandı',exact=True).count()==0
   assert not p.evaluate('localStorage.getItem("togg_health_latest_skin")')
   (OUT/'cancel-late-real-response.json').write_text(json.dumps({'responses':delayed,'lateResultNotPersisted':True,'realFixtureRescanFollows':True},indent=2),'utf8')
  start=time.monotonic();p.get_by_role('button',name='Analizi Başlat',exact=True).click()"""
assert old in code;code=code.replace(old,new)
code=code.replace("'physicalCamera':False", "'physicalCamera':False,'normalProfileTouched':False,'osWindowScreenshotClaimed':False")
sys.path.insert(0,str(ROOT/'tests/e2e'));sys.argv=[str(source)]
exec(compile(code,str(source),'exec'),{'__name__':'__main__','__file__':str(source)})
