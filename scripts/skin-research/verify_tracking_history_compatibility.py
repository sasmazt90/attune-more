"""Open an actual old isolated v8 record on the v9 build; no reanalysis."""
import hashlib,json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'output/playwright/dry-sag-proposal-tracking-20261013'
bundle=(ROOT/'.runtime/periorbital-v5-browser-support/utilities.js').read_text('utf8')
records=[];proof={};skin_requests=[]
with sync_playwright() as pw:
 for version,profile in [('v8',ROOT/'output/playwright/dry-sag-source-census-20261013/40d781eb/automatic-front-profile'),('v9',OUT/'40d781eb/automatic-front-profile')]:
  assert profile.is_relative_to(ROOT/'output/playwright')
  context=pw.chromium.launch_persistent_context(str(profile),channel='chrome',headless=False,args=['--enable-unsafe-swiftshader'])
  context.add_init_script("window.__beforeHistory=localStorage.getItem('togg_health_skin_history');")
  page=context.new_page();page.on('request',lambda r:skin_requests.append(r.url) if r.url.endswith('/api/local-health/skin') else None)
  page.goto('http://127.0.0.1:3000/profile')
  record=page.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))');records.append(record)
  before=page.evaluate('window.__beforeHistory');assert before
  for region,rows in [('chin',record['indicators']['chin']),('overview',record['general']['indicators'])]:
   sag=next(v for v in rows if v['id']=='sag');assert sag['appearance']['normalizationVersion'].endswith(version)
  page.locator('[data-record-id="'+record['id']+'"]').get_by_role('button',name='Sonucu Aç',exact=True).click()
  dialog=page.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True);expect(dialog.locator('[data-skin-snapshot]')).to_be_visible()
  for _ in range(5):dialog.get_by_role('button',name='Sonraki Bölge',exact=True).click()
  card=dialog.locator('[data-skin-record-indicator="sag"]');expect(card).to_be_visible()
  text=card.inner_text();assert ('—' in text and '0%' not in text) if version=='v8' else '0%' in text
  page.screenshot(path=str(OUT/(version+'-actual-chin-history.png')),full_page=True)
  after=page.evaluate('localStorage.getItem("togg_health_skin_history")');assert before==after
  proof[version]=dict(recordId=record['id'],source='existing isolated actual camera record',historySHA256Before=hashlib.sha256(before.encode()).hexdigest(),historySHA256After=hashlib.sha256(after.encode()).hexdigest(),historyUnchanged=before==after,chinText=text)
  if version=='v9':
   page.add_script_tag(content=bundle)
   compared=page.evaluate('''records=>{const R=n=>__auditRequire('apps/vehicle-app/src/utils/'+n+'.ts'),I=R('skinIndicators'),H=R('healthHistorySeries');const r=[];
    for(const scope of ['overview','chin']){const get=x=>(scope==='overview'?x.general.indicators:x.indicators.chin).find(y=>y.id==='sag');const a=get(records[0]),b=get(records[1]);r.push({scope,canCompare:I.canCompareIndicator(a,b),series:H.buildHistorySeries('skin',records).filter(s=>s.region===scope&&s.criterion==='sag').length,oldNormalization:a.appearance.normalizationVersion,newNormalization:b.appearance.normalizationVersion});}return r;}''',records)
   assert all(not r['canCompare'] and r['series']==2 for r in compared);proof['comparison']=compared
  context.close()
assert not skin_requests
proof.update(reanalysisRequests=len(skin_requests),normalUserProfileTouched=False,buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text('utf8').strip())
(ROOT/'audit-results/dry-sag-proposal-tracking-20261013/history-compatibility.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(dict(buildId=proof['buildId'],oldHistoryUnchanged=proof['v8']['historyUnchanged'],newHistoryUnchanged=proof['v9']['historyUnchanged'],comparison=proof['comparison'],reanalysisRequests=len(skin_requests))))
