import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/aws'))
from capture_bridge import create_app, valid_frame
from democtl import validate_approval, validate_instances
from cost import estimate
from preflight import price_per_hour

R='http://127.0.0.1:3000'
S='https://aaos.sasmaz.digital'

@pytest.fixture
def bridge():
    state={'parked':True}
    async def parked():return state['parked']
    return TestClient(create_app(parked,{R},{S})),state


def pair(client):
    r=client.post('/bridge/pair',headers={'origin':R},json={'processingConsent':True})
    assert r.status_code==200
    return r.json()


def test_pair_requires_origin_consent_and_park(bridge):
    c,state=bridge
    assert c.post('/bridge/pair',json={'processingConsent':True}).status_code==403
    assert c.post('/bridge/pair',headers={'origin':R},json={'processingConsent':False}).status_code==409
    state['parked']=False
    assert c.post('/bridge/pair',headers={'origin':R},json={'processingConsent':True}).status_code==409
    state['parked']=True
    p=pair(c)
    assert p['receiverKey']!=p['senderKey'] and len(p['senderKey'])>=40
    assert c.post('/bridge/pair',headers={'origin':R},json={'processingConsent':True}).status_code==409


def test_sender_cannot_use_receiver_key(bridge):
    c,_=bridge;p=pair(c)
    with c.websocket_connect('/bridge/sender',headers={'origin':S}) as ws:
        ws.send_json({'key':p['receiverKey'],'consent':True})
        assert ws.receive()['type']=='websocket.close'


def test_transport_preserves_frame_and_revokes_on_drive(bridge):
    c,state=bridge;p=pair(c)
    # Synthetic PNG header tests transport only, not decoding or AI acceptance.
    raw=b'\x89PNG\r\n\x1a\n'+b'\x00'*8+(640).to_bytes(4,'big')+(480).to_bytes(4,'big')
    with c.websocket_connect('/bridge/receiver',headers={'origin':R}) as rx:
        rx.send_json({'key':p['receiverKey'],'consent':True})
        with c.websocket_connect('/bridge/sender',headers={'origin':S}) as tx:
            tx.send_json({'key':p['senderKey'],'consent':True})
            challenge=tx.receive_json()
            tx.send_json(challenge);tx.send_bytes(raw)
            assert rx.receive_json()=={'sourceId':p['sourceId'],'sequence':1,'sourceType':'remote-demo-camera'}
            assert rx.receive_bytes()==raw
            state['parked']=False
            assert tx.receive()['type']=='websocket.close'
            assert rx.receive()['type']=='websocket.close'


def test_stale_challenge_cannot_replay(bridge):
    c,_=bridge;p=pair(c)
    with c.websocket_connect('/bridge/receiver',headers={'origin':R}) as rx:
        rx.send_json({'key':p['receiverKey'],'consent':True})
        with c.websocket_connect('/bridge/sender',headers={'origin':S}) as tx:
            tx.send_json({'key':p['senderKey'],'consent':True});tx.receive_json()
            tx.send_json({'challenge':'old'});tx.send_bytes(b'not-a-frame')
            assert tx.receive()['type']=='websocket.close'


def test_capture_bounds():
    assert not valid_frame(b'bad')
    assert not valid_frame(b'\x89PNG\r\n\x1a\n'+b'\x00'*8+(99999).to_bytes(4,'big')+(480).to_bytes(4,'big'))


def instances():
    from targets import TARGETS
    return [{'InstanceId':key,'InstanceType':value['type'],'State':{'Name':'stopped'},
             'Tags':[{'Key':'Name','Value':value['name']}]} for key,value in TARGETS.items()]


def test_operations_reject_unrelated_instance():
    from targets import IDS
    values=instances();validate_instances(values,IDS)
    values[1]['Tags']=[]
    with pytest.raises(ValueError):validate_instances(values,IDS)
    with pytest.raises(ValueError):validate_instances(instances(),[IDS[0],IDS[0]])
    values=instances();values[0]['InstanceId']='i-other'
    with pytest.raises(ValueError):validate_instances(values,['i-other',IDS[1]])


def test_paid_start_requires_matching_unexpired_approval():
    now=dt.datetime(2026,11,3,tzinfo=dt.timezone.utc)
    receipt={'expiresAt':'2026-11-03T01:00:00+00:00','account':'123','region':'eu-central-1','instanceIds':['a','b'],'paidStartApproved':True,'maximumSessionHours':2,'approvalReference':'user-message'}
    validate_approval(receipt,'123',['a','b'],now)
    for changes in [{'paidStartApproved':False},{'account':'wrong'},{'expiresAt':'2026-11-02T00:00:00+00:00'},{'maximumSessionHours':25}]:
        with pytest.raises(ValueError):validate_approval({**receipt,**changes},'123',['a','b'],now)



def test_completion_scoped_paid_approval_requires_explicit_policy_and_cost_monitoring():
    now = dt.datetime(2026, 11, 3, tzinfo=dt.timezone.utc)
    receipt = {'expiresAt': '2026-11-04T00:00:00+00:00', 'account': '123',
               'region': 'eu-central-1', 'instanceIds': ['a', 'b'],
               'paidStartApproved': True, 'approvalReference': 'user-expanded-scope',
               'executionPolicy': 'until_completion_or_unrecoverable_blocker',
               'noFixedDurationLimit': True, 'monitorCosts': True,
               'maximumSessionHours': None}
    validate_approval(receipt, '123', ['a', 'b'], now)
    for changes in [{'monitorCosts': False}, {'noFixedDurationLimit': False},
                    {'executionPolicy': 'unlimited'}, {'maximumSessionHours': True},
                    {'paidStartApproved': False}, {'approvalReference': ''}]:
        with pytest.raises(ValueError):
            validate_approval({**receipt, **changes}, '123', ['a', 'b'], now)


def test_cost_retains_disk_and_ip_charge_while_stopped():
    r=estimate(1,0.5,0.1,0,ipv4_hour=.005,retained_ipv4_count=2,active_ipv4_count=2)
    assert r['monthly_compute']==0
    assert r['monthly_subtotal']==34.3
    with pytest.raises(ValueError):estimate(1,.5,.1,-2,ipv4_hour=.005,retained_ipv4_count=0,active_ipv4_count=2)


def test_price_rejects_ambiguous_products():
    with pytest.raises(ValueError):price_per_hour([])


def test_infrastructure_has_no_public_admin_ports_or_dns():
    stack=json.loads((ROOT/'infra/aws/stack.json').read_text())
    assert stack['Resources']
    for r in stack['Resources'].values():
        assert r['Type']=='AWS::EC2::SecurityGroupIngress'
        assert r['Properties']['FromPort']==r['Properties']['ToPort']
        assert r['Properties']['FromPort'] in (443,8443)
        assert stack['Parameters'][r['Condition']]['Default']=='no'
        assert r['DeletionPolicy']==r['UpdateReplacePolicy']=='Retain'
        if r['Properties']['FromPort']==8443:
            assert 'SourceSecurityGroupId' in r['Properties'] and 'CidrIp' not in r['Properties']
    from targets import IDS
    assert stack['Parameters']['WebInstanceId']['AllowedValues']==[IDS[0]]
    assert stack['Parameters']['AaosInstanceId']['AllowedValues']==[IDS[1]]


def test_audio_rejects_invalid_pcm():
    import struct
    from audio_bridge import valid_microphone_frame
    assert valid_microphone_frame(struct.pack('<fff',0,.5,-1))
    for raw in [b'',b'bad',struct.pack('<f',float('nan')),struct.pack('<f',2),b'0'*16388]:
        assert not valid_microphone_frame(raw)
