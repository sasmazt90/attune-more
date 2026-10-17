"""Finite CARE contract tests: actual route AST, no app/model import or external I/O."""
import ast
import asyncio
from pathlib import Path
import sys
from typing import List, Optional
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
import care_provider as cp

WINDOW=[{'start':'2026-10-20T09:00','end':'2026-10-20T10:00'}]

def live_row(**changes):
    return dict(id='fixture-source-time',providerName='Declared contract fixture',
        bookingUrl='https://www.doktortakvimi.com/dermatoloji/istanbul',
        sourceId='doktortakvimi',sourceType='LIVE_AVAILABILITY',dateTime='2026-10-20T10:00',**changes)

def test_public_links_keep_source_specialty_city_without_claiming_slot():
    for specialty in cp.SPECIALTY_PATHS:
        rows=cp.public_handoff_result(specialty,'İstanbul')['slots']
        assert len(rows)==2
        assert all(('/istanbul' in row['bookingUrl'] or 'loc=%C4%B0stanbul' in row['bookingUrl']) and row['sourceId']!='doctolib' for row in rows)
        result=cp.normalize_care_slots({'slots':rows},WINDOW,45,'Europe/Berlin')
        assert all(row['calendarFits'] is None and row['dateTime'] is None and row['travelTimeMin'] is None for row in result)
    rows=cp.public_handoff_result('Dermatoloji','Berlin')['slots']
    assert len(rows)==1 and rows[0]['bookingUrl']=='https://www.doctolib.de/hautarzt/berlin'
    assert cp.public_handoff_result('Unknown','İstanbul')['status']=='EMPTY_RESULT'
    assert cp.public_handoff_result('Dermatoloji','Unknown city')['slots']==[]

@pytest.mark.parametrize('url',[
    'https://www.doktortakvimi.com/dermatoloji/istanbul',
    'https://www.doktorsitesi.com/uzmanlik-alanlari/dermatoloji/istanbul',
    'https://www.doctolib.de/hautarzt/berlin',
    'https://www.doktortakvimi.com/arama?q=G%C3%B6z%20Hastal%C4%B1klar%C4%B1&loc=%C4%B0stanbul',
])
def test_safe_public_links(url): assert cp.safe_care_url(url)

@pytest.mark.parametrize('url',[
    'http://www.doktortakvimi.com/dermatoloji/istanbul',
    'https://www.doktortakvimi.com.evil.test/profile',
    'https://www.doktortakvimi.com@evil.test/profile',
    'https://www.doktortakvimi.com/redirect?url=https://evil.test',
    'https://www.doktortakvimi.com/profile?next=https://evil.test',
    'https://www.doktortakvimi.com/%2f%2fevil',
    'https://www.doktortakvimi.com/a/../out',
    'https://www.doktortakvimi.com:8000/profile',
    'javascript:alert(1)', '//evil.test/path', None,
])
def test_unsafe_or_redirect_links_rejected(url): assert not cp.safe_care_url(url)

def test_url_source_identity_cannot_be_substituted():
    assert not cp.safe_care_url('https://www.doctolib.de/hautarzt/berlin','doktortakvimi')
    assert not cp.safe_care_url('https://www.doctolib.de/hautarzt/berlin',{})

def test_naive_provider_time_uses_source_not_user_timezone():
    # 10:00 Istanbul = 09:00 Berlin on this date; whole 45 minutes fits.
    assert cp.available_window_match('2026-10-20T10:00',WINDOW,45,'Europe/Berlin') is True
    assert cp.available_window_match('2026-10-20T09:00',WINDOW,45,'Europe/Berlin') is False
    rows=cp.normalize_care_slots({'slots':[live_row()]},WINDOW,45,'Europe/Berlin')
    assert rows[0]['dateTime']=='2026-10-20T10:00:00+03:00' and rows[0]['calendarFits'] is True
    assert rows[0]['calendarConflict'] is None and rows[0]['matchScore'] is None

@pytest.mark.parametrize('windows',[
    [{'start':'bad','end':'bad'}], [{'start':'2026-10-20','end':'2026-10-21'}],
    [{'start':'2026-10-20T10:00','end':'2026-10-20T09:00'}], [{}],
    [{'start':'2026-10-25T02:15','end':'2026-10-25T04:00'}],
    [{'start':'2026-03-29T02:15','end':'2026-03-29T04:00'}], None,
])
def test_invalid_or_ambiguous_user_windows_never_match(windows):
    with pytest.raises(ValueError): cp.available_window_match(None,windows,45,'Europe/Berlin')

@pytest.mark.parametrize('value',['09:00','2026-10-20','2026-02-30T09:00',None])
def test_bad_source_timestamp_downgrades_to_profile_not_fitting_slot(value):
    row=live_row();row['dateTime']=value
    out=cp.normalize_care_slots({'slots':[row]},WINDOW,45,'Europe/Berlin')[0]
    assert out['dateTime'] is None and out['calendarFits'] is None and out['sourceType']=='LIVE_PROVIDER_ONLY'

def test_profile_cannot_claim_a_date_and_missing_window_remains_unknown():
    row=live_row();row['sourceType']='LIVE_PROVIDER_ONLY'
    assert cp.normalize_care_slots({'slots':[row]},WINDOW,45,'Europe/Berlin')[0]['dateTime'] is None
    assert cp.available_window_match('2026-10-20T10:00',[],45,'Europe/Berlin') is None

def test_dom_time_requires_complete_timestamp_and_explicit_source_timezone():
    class Node:
        def __init__(self,value): self.value=value
        def get_attribute(self,key): return self.value if key=='datetime' else None
        def query_selector(self,key): return None
    assert cp.verified_source_slot_time(Node('2026-10-20T09:00'),'Europe/Berlin')=='2026-10-20T09:00:00+02:00'
    assert cp.verified_source_slot_time(Node('2026-10-20T09:00'))=='2026-10-20T09:00:00+03:00'
    assert cp.verified_source_slot_time(Node('09:00')) is None
    assert cp.verified_source_slot_time(Node('2026-02-30T09:00')) is None

def test_missing_partner_configuration_preserves_public_handoff_no_demo():
    result=cp.get_care_provider(config={'ATTUNE_CARE_PROVIDER':'partner'}).search_slots('Dermatoloji')
    assert result['status']=='CONFIGURATION_REQUIRED' and result['slots']
    assert all(row['sourceType']=='PUBLIC_SEARCH_ONLY' for row in result['slots'])
    assert isinstance(cp.get_care_provider(False,config={}),cp.PublicCareSearchProvider)
    assert not isinstance(cp.get_care_provider(False,config={'ATTUNE_CARE_PROVIDER':'demo'}),cp.DemoCareSearchProvider)
    assert isinstance(cp.get_care_provider(False,config={'ATTUNE_CARE_PROVIDER':'demo','ATTUNE_CARE_ALLOW_DEMO':'1'}),cp.DemoCareSearchProvider)

@pytest.mark.parametrize('error,status',[(TimeoutError,'TIMEOUT'),(ConnectionError,'NETWORK_ERROR'),(PermissionError,'ACCESS_BLOCKED')])
def test_partner_failure_never_invents_demo_or_time(error,status):
    class Client:
        calls=0
        def search_slots(self,**kwargs):
            self.calls+=1;assert kwargs['timeout_seconds']==8;raise error()
    client=Client();result=cp.PartnerCareSearchProvider(client).search_slots('Dermatoloji')
    assert result['status']==status and client.calls==1
    assert all(row['dateTime'] is None and row['sourceType']=='PUBLIC_SEARCH_ONLY' for row in result['slots'])

def test_partner_empty_not_conflated_with_network_or_demo():
    class Client:
        def search_slots(self,**kwargs): return dict(status='SUCCESS',slots=[])
    out=cp.PartnerCareSearchProvider(Client()).search_slots('Dermatoloji')
    assert out['status']=='EMPTY_RESULT' and out['slots']==[]

def route_scope():
    tree=ast.parse((ROOT/'services/core-api/main.py').read_text('utf-8-sig'))
    nodes=[node for node in tree.body if isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in ('AppointmentMatchPayload','match_appointments')]
    assert len(nodes)==2
    app=FastAPI()
    scope=dict(app=app,BaseModel=BaseModel,Field=Field,Optional=Optional,List=List,
        Request=Request,HTTPException=HTTPException,vehicle_state={'vehicleParked':True,'vehicleMoving':False})
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(ROOT/'services/core-api/main.py'),'exec'),scope)
    return scope

@pytest.fixture
def route(monkeypatch):
    monkeypatch.delenv('ATTUNE_CARE_PROVIDER',raising=False)
    return route_scope()

def test_actual_selected_route_public_response_no_models_records_or_network(route):
    with TestClient(route['app']) as client:
        result=client.post('/api/care/match',json=dict(specialty='Dermatoloji',preferredCity='İstanbul',availableWindows=WINDOW,timeZone='Europe/Berlin'))
    assert result.status_code==200
    value=result.json();assert value['status']=='PUBLIC_HANDOFF' and len(value['matchedSlots'])==2
    assert value['currentTravelBufferMin'] is None
    assert all(row['calendarFits'] is None and row['sourceType']=='PUBLIC_SEARCH_ONLY' for row in value['matchedSlots'])

@pytest.mark.parametrize('change,code',[
    ({'availableWindows':[{'start':'bad','end':'bad'}]},422),
    ({'timeZone':'Bad/Zone'},422), ({'durationMin':0},422),
])
def test_route_rejects_invalid_inputs_before_provider(route,monkeypatch,change,code):
    def forbidden(*args,**kwargs): pytest.fail('provider called before validation')
    monkeypatch.setattr(cp,'get_care_provider',forbidden)
    with TestClient(route['app']) as client:
        assert client.post('/api/care/match',json={'specialty':'Dermatoloji',**change}).status_code==code

def test_actual_route_driving_blocks_before_provider(route,monkeypatch):
    route['vehicle_state']['vehicleMoving']=True
    monkeypatch.setattr(cp,'get_care_provider',lambda *args:pytest.fail('driving provider request'))
    with TestClient(route['app']) as client:
        assert client.post('/api/care/match',json={'specialty':'Dermatoloji'}).status_code==409

def test_route_discards_result_after_disconnect_or_vehicle_change(route,monkeypatch):
    class RequestState:
        calls=0
        async def is_disconnected(self): self.calls+=1;return self.calls>1
    payload=route['AppointmentMatchPayload'](specialty='Dermatoloji')
    with pytest.raises(HTTPException,match='CANCELLED'):
        asyncio.run(route['match_appointments'](payload,RequestState()))
    class Provider:
        def search_slots(self,**kwargs):
            route['vehicle_state']['vehicleMoving']=True
            return cp.public_handoff_result('Dermatoloji','İstanbul')
    class Connected:
        async def is_disconnected(self): return False
    monkeypatch.setattr(cp,'get_care_provider',lambda *args:Provider())
    with pytest.raises(HTTPException,match='PARK_REQUIRED'):
        asyncio.run(route['match_appointments'](payload,Connected()))
