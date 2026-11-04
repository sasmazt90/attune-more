#!/usr/bin/env python3
"""Explicit, task-scoped EC2 operations. No timers and no automatic shutdown."""
import argparse
import datetime as dt
import json
from pathlib import Path
from preflight import select_identity
from targets import IDS, REGION, validate_instances
import hashlib


def validate_approval(approval, account, ids, now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    expiry=dt.datetime.fromisoformat(approval['expiresAt'])
    if expiry.tzinfo is None or expiry<=now:
        raise ValueError('Approval has expired or lacks timezone')
    if approval.get('account')!=account or approval.get('region')!=REGION or set(approval.get('instanceIds',[]))!=set(ids) or approval.get('paidStartApproved') is not True:
        raise ValueError('Approval does not match account/region/resources')
    completion_scoped = (approval.get('executionPolicy') == 'until_completion_or_unrecoverable_blocker'
                         and approval.get('noFixedDurationLimit') is True
                         and approval.get('monitorCosts') is True
                         and approval.get('maximumSessionHours') is None)
    hours = approval.get('maximumSessionHours', 0)
    bounded = isinstance(hours, (int, float)) and not isinstance(hours, bool) and 0 < hours <= 4
    if not (bounded or completion_scoped) or not approval.get('approvalReference'):
        raise ValueError('Explicit bounded or completion-scoped approval receipt required')


def validate_start_inventory(raw, approval, account, instances, now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    inventory=json.loads(raw)
    observed=dt.datetime.fromisoformat(inventory['observedAt'])
    if observed.tzinfo is None or not 0 <= (now-observed).total_seconds() <= 1800:
        raise ValueError('Inventory must be observed within the last 30 minutes')
    if inventory.get('status')!='OBSERVED' or inventory.get('region')!=REGION or set(inventory.get('targetIds',[]))!=set(IDS):
        raise ValueError('Complete inventory of exactly the existing targets is required')
    if inventory['checks']['account'].get('value')!=account or any(c['status']!='OBSERVED' for c in inventory['checks'].values()):
        raise ValueError('Inventory account/checks are not verified')
    if approval.get('inventorySha256')!=hashlib.sha256(raw).hexdigest() or approval.get('configurationReviewed') is not True:
        raise ValueError('Approval must identify the reviewed inventory and configuration')
    if not approval.get('testScope') or not isinstance(approval.get('estimatedSessionUsd'),(float,int)) or not 0 < approval['estimatedSessionUsd'] < float('inf'):
        raise ValueError('A concrete cost estimate and test scope must be presented before start')
    validate_instances(instances)
    if any(i['State']['Name']!='stopped' for i in instances):
        raise ValueError('Both existing instances must be stopped before this start')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['status','start','stop'])
    p.add_argument('--instances',nargs=2,default=list(IDS))
    p.add_argument('--inventory',type=Path,help='Fresh reviewed inventory required for start')
    p.add_argument('--identity-alias')
    p.add_argument('--approval',type=Path)
    p.add_argument('--receipt',type=Path,required=True)
    args=p.parse_args()
    select_identity(args.identity_alias)
    import boto3
    session=boto3.Session();ec2=session.client('ec2',region_name=REGION)
    account=session.client('sts',region_name=REGION).get_caller_identity()['Account']
    instances=[i for r in ec2.describe_instances(InstanceIds=args.instances)['Reservations'] for i in r['Instances']]
    validate_instances(instances,args.instances)
    if args.action=='start':
        if not args.approval:raise ValueError('Paid start requires an existing explicit approval receipt')
        approval=json.loads(args.approval.read_text());validate_approval(approval,account,args.instances)
        if not args.inventory:raise ValueError('Reviewed existing-resource inventory required')
        validate_start_inventory(args.inventory.read_bytes(), approval, account, instances)
        ec2.start_instances(InstanceIds=args.instances)
        ec2.get_waiter('instance_running').wait(InstanceIds=args.instances,WaiterConfig={'Delay':10,'MaxAttempts':60})
        ec2.get_waiter('instance_status_ok').wait(InstanceIds=args.instances,WaiterConfig={'Delay':10,'MaxAttempts':60})
        print('EC2 ready only. Follow the approved execution/stop policy. No automatic shutdown is scheduled.')
    elif args.action=='stop':
        ec2.stop_instances(InstanceIds=args.instances)
        ec2.get_waiter('instance_stopped').wait(InstanceIds=args.instances,WaiterConfig={'Delay':10,'MaxAttempts':60})
    result={'at':dt.datetime.now(dt.timezone.utc).isoformat(),'action':args.action,'region':REGION,
            'instances':ec2.describe_instances(InstanceIds=args.instances)['Reservations'],
            'remainingCharges':'EBS and retained public IPv4/EIP continue billing while stopped; snapshots and provider API usage may also be billed.'}
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(result,indent=2,default=str)+'\n')

if __name__=='__main__':main()
