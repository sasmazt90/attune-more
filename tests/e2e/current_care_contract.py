"""Real provider read (no booking), plus five real route/filter/payload mappings.
Mapping pages abort transport deliberately; they cannot assert provider availability.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path('audit-results/current-health-20261009/care');OUT.mkdir(parents=True,exist_ok=True)
modules=json.loads(Path('shared/healthModules.json').read_text('utf8'))
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required']);c=b.new_context();p=c.new_page()
 payload={'specialty':modules['hearing']['specialties'][0],'preferredCity':'İstanbul','useBrowserAgent':True,'availableWindows':[{'start':'2026-10-11T09:00','end':'2026-10-11T11:00'}],'durationMin':45,'timeZone':'Europe/Berlin'}
 response=c.request.post('http://127.0.0.1:8000/api/care/match',data=payload,timeout=60000);assert response.status==200;actual=response.json()
 assert actual['providerType']!='DemoCareSearchProvider'
 for row in actual['matchedSlots']:
  assert row['sourceType']!='DEMO' and row['matchScore'] is None
  if not row.get('dateTime'):assert row['calendarFits'] is None
  if row['calendarFits'] is True:assert row['dateTime']
 (OUT/'actual-source-response.json').write_text(json.dumps({'request':payload,'response':actual,'realReadOnlyProvider':True,'declaredEngineeringAvailabilityInput':True,'bookingCalls':0},ensure_ascii=False,indent=2),'utf8')
 observed=[]
 def capture(route):
  observed.append(route.request.post_data_json);route.abort()
 p.route('**/api/care/match',capture)
 routes=[]
 for id,module in modules.items():
  from urllib.parse import urlencode
  url='http://127.0.0.1:3000/care?'+urlencode({'from':id,'specialty':module['specialties'][0],'recordId':'declared-history-fixture'})
  p.goto(url);button=p.get_by_role('button',name=module['specialties'][0],exact=True);expect(button).to_be_visible();assert 'bg-togg-turquoise text-togg-darkBlue' in button.get_attribute('class')
  p.get_by_label('Uygun zaman başlangıcı',exact=True).fill('2026-10-11T09:00');p.get_by_label('Uygun zaman bitişi',exact=True).fill('2026-10-11T11:00');p.get_by_label('Görüşme süresi').select_option('60')
  p.wait_for_timeout(100);assert observed[-1]['specialty']==module['specialties'][0] and observed[-1]['durationMin']==60 and observed[-1]['availableWindows'][0]['start']=='2026-10-11T09:00'
  routes.append({'module':id,'url':url,'payload':observed[-1]})
  p.go_back() if id!='vision' else None
 p.screenshot(path=str(OUT/'current-filters.png'),full_page=True)
 (OUT/'proof.json').write_text(json.dumps({'status':'PASS','buildId':Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'realProviderRead':True,'providerStatus':actual['status'],'verifiedActualSlots':sum(bool(r.get('dateTime')) for r in actual['matchedSlots']),'fiveRouteFilters':routes,'mappingTransportAborted':True,'noManufacturedProviders':True,'noBookingCalls':True,'humanAppointmentAvailabilityAccepted':False},ensure_ascii=False,indent=2),'utf8');b.close()
print('PASS real read-only source behavior, five filters and user window/timezone/duration payloads')
