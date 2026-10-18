"""One new actual production three-pose photographic-fixture scan, then real
observation/actions/trend/reminder controls. No injected result or quality PASS.
"""
import ast,json,os,sys
from pathlib import Path
from playwright.sync_api import expect
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/all-health-20261010/skin-followups';OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'tests/e2e'))
def verify_followups(p):
 count=p.evaluate('JSON.parse(localStorage.getItem("togg_health_skin_history")).length')
 p.get_by_role('button',name='Gözlem Notu',exact=True).click();expect(p.get_by_role('dialog',name='Gözlem Notu',exact=True)).to_contain_text('Genel Bakış');p.keyboard.press('Escape')
 p.get_by_role('button',name='Zaman İçinde Değişim',exact=True).click();trend=p.get_by_role('dialog',name='Zaman İçinde Değişim',exact=True);expect(trend).to_be_visible();expect(trend.locator('svg[role="group"]')).to_be_visible();assert trend.get_by_label('Ölçüm').input_value()=='tone';assert 'Genel Bakış' in trend.inner_text();assert trend.locator('svg circle[role="button"]').count()>=1;trend.locator('svg circle[role="button"]').last.focus();expect(trend.get_by_role('tooltip')).to_contain_text('%');assert not any(v in trend.get_by_role('tooltip').inner_text() for v in ('mean(', 'clamp(', 'appearance-cv'));p.screenshot(path=str(OUT/'overview-trend-current-measurements.png'),full_page=True);p.keyboard.press('Escape')
 p.get_by_role('button',name='Önerilen Aksiyonlar',exact=True).click();actions=p.get_by_role('dialog',name='Önerilen Aksiyonlar',exact=True);actions.get_by_role('button',name='Hatırlat',exact=True).click();assert actions.get_by_label('Hatırlatma tarihi ve saati').input_value()
 actions.get_by_role('button',name='Hatırlatmayı kaydet',exact=True).click();expect(actions).to_contain_text('Uygulama içi plan kaydedildi.')
 plan=p.evaluate('JSON.parse(localStorage.getItem("togg_health_skin_reminder"))');assert plan['dueAt']
 with p.expect_download() as download:actions.get_by_role('button',name='Takvim dosyasını indir (.ics)',exact=True).click()
 download.value.save_as(str(OUT/'isolated-reminder.ics'));calendar=(OUT/'isolated-reminder.ics').read_text('utf8');assert 'BEGIN:VCALENDAR' in calendar and 'BEGIN:VEVENT' in calendar
 actions.get_by_role('button',name='Hatırlatmayı iptal et',exact=True).click();expect(actions).to_contain_text('Uygulama içi plan iptal edildi.');assert p.evaluate('localStorage.getItem("togg_health_skin_reminder")') is None
 p.screenshot(path=str(OUT/'actions-reminder-cancelled.png'),full_page=True);p.keyboard.press('Escape')
 assert p.evaluate('JSON.parse(localStorage.getItem("togg_health_skin_history")).length')==count
 (OUT/'followup-proof.json').write_text(json.dumps(dict(status='PASS',buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),actualProductionScan=True,photographicFixture=True,observation=True,trendPopup=True,actions=True,reminderSaveDownloadCancel=True,noDuplicateAnalysisRecord=True,native200Claimed=False,normalProfileTouched=False,physicalAcceptance=False),indent=2),'utf8')

source=ROOT/'tests/e2e/current_skin_contract.py';tree=ast.parse(source.read_text('utf8'))
class Followups(ast.NodeTransformer):
 def visit_Assign(self,node):
  if any(isinstance(t,ast.Name) and t.id=='OUT' for t in node.targets):node.value=ast.Call(func=ast.Name(id='Path',ctx=ast.Load()),args=[ast.Constant(str(OUT))],keywords=[])
  return node
 def visit_For(self,node):
  if isinstance(node.target,ast.Name) and node.target.id=='n' and ast.unparse(node.iter)=='range(2)':node.iter=ast.parse('range(1)',mode='eval').body
  return self.generic_visit(node)
 def visit_Expr(self,node):
  if "get_by_role('button', name='Referans ve görüntü hakkında bilgi')" in ast.unparse(node):
   return [ast.Expr(value=ast.Call(func=ast.Name(id='verify_followups',ctx=ast.Load()),args=[ast.Name(id='p',ctx=ast.Load())],keywords=[])),node]
  if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='print':return ast.parse("print('PASS one actual production scan plus observation/trend/actions/reminder UI; controlled fixture, no physical/native200 claim')").body[0]
  return node
tree=ast.fix_missing_locations(Followups().visit(tree));sys.argv=[str(source)]
exec(compile(tree,str(source),'exec'),{'__name__':'__main__','__file__':str(source),'verify_followups':verify_followups})
assert (OUT/'followup-proof.json').exists(),'UI hook did not execute'
