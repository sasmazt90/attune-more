import copy
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/aws'))
from targets import IDS, TARGETS, REGION
from democtl import validate_start_inventory
from inventory import assess, collect
from host_identity import verify
from check_changeset import validate
from cost import estimate


def hosts():
    return [{'InstanceId':key,'InstanceType':target['type'],'Tags':[{'Key':'Name','Value':target['name']}],
             'State':{'Name':'stopped'},'VpcId':'vpc-existing','MetadataOptions':{'HttpTokens':'required'},
             'CpuOptions':{'NestedVirtualization':'enabled'},'RootDeviceName':'/dev/sda1',
             'BlockDeviceMappings':[{'DeviceName':'/dev/sda1','Ebs':{'VolumeId':'vol-'+target['role']}}]}
            for key,target in TARGETS.items()]


def test_install_refuses_laptop_wrong_host_role_region_and_type():
    doc={'instanceId':IDS[0],'region':REGION,'instanceType':'g6.2xlarge'}
    verify(doc,'web')
    for bad,role in [({},'web'),(doc,'aaos'),({**doc,'region':'us-east-1'},'web'),({**doc,'instanceType':'g6.xlarge'},'web')]:
        with pytest.raises(ValueError):verify(bad,role)


def test_start_requires_fresh_complete_reviewed_inventory_and_concrete_cost_scope():
    now=dt.datetime.now(dt.timezone.utc)
    inv={'observedAt':now.isoformat(),'status':'OBSERVED','region':REGION,'targetIds':list(IDS),'checks':{'account':{'status':'OBSERVED','value':'123'}}}
    raw=json.dumps(inv).encode()
    approval={'inventorySha256':hashlib.sha256(raw).hexdigest(),'configurationReviewed':True,'testScope':['boot','real-input'],'estimatedSessionUsd':10}
    validate_start_inventory(raw,approval,'123',hosts(),now)
    for changes in [{'configurationReviewed':False},{'inventorySha256':'wrong'},{'testScope':[]},{'estimatedSessionUsd':float('nan')},{'estimatedSessionUsd':0}]:
        with pytest.raises(ValueError):validate_start_inventory(raw,{**approval,**changes},'123',hosts(),now)
    with pytest.raises(ValueError):validate_start_inventory(raw,approval,'123',hosts(),now+dt.timedelta(hours=1))
    with pytest.raises(ValueError):validate_start_inventory(raw,approval,'456',hosts(),now)
    running=hosts();running[0]['State']['Name']='running'
    with pytest.raises(ValueError):validate_start_inventory(raw,approval,'123',running,now)
    inv['checks']['volumes']={'status':'BLOCKED','reason':'AccessDenied'}
    raw=json.dumps(inv).encode();approval['inventorySha256']=hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError):validate_start_inventory(raw,approval,'123',hosts(),now)


def test_audit_surfaces_shared_sg_disk_and_nested_mismatch_without_changes():
    values=hosts();values[1]['CpuOptions']={}
    vols=[{'VolumeId':'vol-web','VolumeType':'gp3','Size':150,'Encrypted':True},
          {'VolumeId':'vol-aaos','VolumeType':'gp3','Size':100,'Encrypted':False}]
    groups=[{'GroupId':'sg-shared','IpPermissions':[{'IpProtocol':'tcp','FromPort':22,'ToPort':22,'IpRanges':[{'CidrIp':'0.0.0.0/0'}]}]}]
    before=copy.deepcopy((values,vols,groups))
    found=assess(values,vols,groups,[{'Attachment':{'InstanceId':'i-unrelated'}}])
    assert any('shared' in f for f in found) and any('120 GiB' in f for f in found)
    assert any('nested virtualization' in f for f in found) and any('unencrypted' in f for f in found)
    assert any('non-HTTPS' in f for f in found)
    assert (values,vols,groups)==before


def test_missing_aws_permission_is_blocked_without_mutation():
    class Client:
        def get_caller_identity(self):return {'Account':'123'}
        def describe_instances(self, **kwargs):
            assert kwargs=={'InstanceIds':list(IDS)}
            raise PermissionError('Do not expose arbitrary error detail')
    class Session:
        def client(self,*args,**kwargs):return Client()
    result=collect(Session())
    assert result['status']=='BLOCKED' and result['mutations']==[]
    assert result['checks']['reservations']=={'status':'BLOCKED','reason':'PermissionError'}


def test_only_additive_rules_on_a_new_stack_pass_offline_gate():
    stack={'StackId':'arn:aws:cloudformation:eu-central-1:123:stack/rules/id','StackStatus':'REVIEW_IN_PROGRESS'}
    change={'StackId':stack['StackId'],'Status':'CREATE_COMPLETE','ExecutionStatus':'AVAILABLE','Changes':[
        {'Type':'Resource','ResourceChange':{'Action':'Add','ResourceType':'AWS::EC2::SecurityGroupIngress','LogicalResourceId':'PrivateApi'}}]}
    assert validate(change,stack)==['PrivateApi']
    for update in [{'Action':'Remove'},{'Action':'Modify'},{'ResourceType':'AWS::EC2::Instance'},{'Replacement':'True'},{'PhysicalResourceId':'existing'}]:
        bad=copy.deepcopy(change);bad['Changes'][0]['ResourceChange'].update(update)
        with pytest.raises(ValueError):validate(bad,stack)
    with pytest.raises(ValueError):validate(change,{**stack,'StackStatus':'UPDATE_COMPLETE'})
    with pytest.raises(ValueError):validate({**change,'ImportExistingResources':True},stack)
    with pytest.raises(ValueError):validate({**change,'NextToken':'more-resources'},stack)


def test_non_eip_addresses_are_not_billed_as_retained():
    r=estimate(1,.5,.1,2,ipv4_hour=.005,retained_ipv4_count=0,active_ipv4_count=2)
    assert r['storage_gb']==270 and r['monthly_retained_ebs_and_ipv4']==27
    assert r['session_incremental_compute_and_ipv4']==3.02
    for changes in [{'g6':float('inf')},{'hours':float('nan')},{'retained_ipv4_count':3}]:
        args=dict(g6=1,m8i=.5,ebs_gb_month=.1,hours=2,ipv4_hour=.005,retained_ipv4_count=0,active_ipv4_count=2)
        with pytest.raises(ValueError):estimate(**{**args,**changes})
