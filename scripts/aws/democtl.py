#!/usr/bin/env python3
"""Explicit, task-scoped EC2 operations. No timers and no automatic shutdown."""
import argparse
import datetime as dt
import json
from pathlib import Path
from preflight import REGION, TYPES, select_identity


def validate_instances(instances, ids):
    if len(ids)!=2 or len(set(ids))!=2 or {i['InstanceId'] for i in instances} != set(ids):
        raise ValueError('Exactly the two recorded task instances are required')
    if sorted(i['InstanceType'] for i in instances)!=sorted(TYPES):
        raise ValueError('Instance types differ from the Task 13 plan')
    for instance in instances:
        tags={t['Key']:t['Value'] for t in instance.get('Tags',[])}
        if tags.get('Project')!='Attune.more' or tags.get('Task')!='13' or tags.get('Environment')!='oem-demo':
            raise ValueError('Refusing to operate on unrelated resources')


def validate_approval(approval, account, ids, now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    expiry=dt.datetime.fromisoformat(approval['expiresAt'])
    if expiry.tzinfo is None or expiry<=now:
        raise ValueError('Approval has expired or lacks timezone')
    if approval.get('account')!=account or approval.get('region')!=REGION or set(approval.get('instanceIds',[]))!=set(ids) or approval.get('paidStartApproved') is not True:
        raise ValueError('Approval does not match account/region/resources')
    if not 0<approval.get('maximumSessionHours',0)<=4 or not approval.get('approvalReference'):
        raise ValueError('Bounded approval receipt required')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['status','start','stop'])
    p.add_argument('--instances',nargs=2,required=True)
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
        ec2.start_instances(InstanceIds=args.instances)
        ec2.get_waiter('instance_running').wait(InstanceIds=args.instances,WaiterConfig={'Delay':10,'MaxAttempts':60})
        ec2.get_waiter('instance_status_ok').wait(InstanceIds=args.instances,WaiterConfig={'Delay':10,'MaxAttempts':60})
        print('EC2 ready only. Run the bounded application/AAOS smoke before the meeting. No automatic shutdown is scheduled.')
    elif args.action=='stop':
        ec2.stop_instances(InstanceIds=args.instances)
        ec2.get_waiter('instance_stopped').wait(InstanceIds=args.instances,WaiterConfig={'Delay':10,'MaxAttempts':60})
    result={'at':dt.datetime.now(dt.timezone.utc).isoformat(),'action':args.action,'region':REGION,
            'instances':ec2.describe_instances(InstanceIds=args.instances)['Reservations'],
            'remainingCharges':'EBS and retained public IPv4/EIP continue billing while stopped; snapshots and provider API usage may also be billed.'}
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(result,indent=2,default=str)+'\n')

if __name__=='__main__':main()
