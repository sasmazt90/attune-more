#!/usr/bin/env python3
"""Apply only the three existing-SG rules explicitly requested on 2026-11-03.

Default is dry-run. No EC2 start, new resource, egress edit or existing-rule removal.
All missing rules must pass authorization preflight before any rule is added.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

from preflight import select_identity
from targets import IDS, REGION, validate_instances

ACCOUNT = '798886013428'
WEB = 'sg-023659b3a447ab759'
AAOS = 'sg-0476f580c44063a5d'
SOURCE = '91.14.212.184/32'
RULES = [
    (WEB, {'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443,
           'IpRanges': [{'CidrIp': SOURCE}]}),
    (AAOS, {'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443,
            'IpRanges': [{'CidrIp': SOURCE}]}),
    (WEB, {'IpProtocol': 'tcp', 'FromPort': 8443, 'ToPort': 8443,
           'UserIdGroupPairs': [{'GroupId': AAOS}]}),
]


def present(permissions, wanted):
    for rule in permissions:
        if any(rule.get(k) != wanted[k] for k in ('IpProtocol', 'FromPort', 'ToPort')):
            continue
        kind, field = ('IpRanges', 'CidrIp') if 'IpRanges' in wanted else ('UserIdGroupPairs', 'GroupId')
        if any(x.get(field) == wanted[kind][0][field] for x in rule.get(kind, [])):
            return True
    return False


def validate_topology(instances, groups, interfaces):
    validate_instances(instances)
    expected = {IDS[0]: WEB, IDS[1]: AAOS}
    for instance in instances:
        if {g['GroupId'] for g in instance['SecurityGroups']} != {expected[instance['InstanceId']]}:
            raise ValueError('Target security-group attachment changed')
    if len({i['VpcId'] for i in instances}) != 1:
        raise ValueError('Targets must share one VPC')
    if {g['GroupId'] for g in groups} != {WEB, AAOS} or any(
        g['OwnerId'] != ACCOUNT or g['VpcId'] != instances[0]['VpcId'] for g in groups
    ):
        raise ValueError('Security-group ownership/VPC mismatch')
    if not interfaces or any(e.get('Attachment', {}).get('InstanceId') not in IDS for e in interfaces):
        raise ValueError('Security group is shared with an unrelated interface or inventory is empty')


def configure(session, apply=False):
    account = session.client('sts', region_name=REGION).get_caller_identity()['Account']
    if account != ACCOUNT:
        raise ValueError('Unexpected AWS account')
    ec2 = session.client('ec2', region_name=REGION)
    instances = [i for r in ec2.describe_instances(InstanceIds=list(IDS))['Reservations'] for i in r['Instances']]
    groups = ec2.describe_security_groups(GroupIds=[WEB, AAOS])['SecurityGroups']
    interfaces = [e for p in ec2.get_paginator('describe_network_interfaces').paginate(
        Filters=[{'Name': 'group-id', 'Values': [WEB, AAOS]}]) for e in p['NetworkInterfaces']]
    validate_topology(instances, groups, interfaces)
    by_id = {g['GroupId']: g for g in groups}
    missing = [(gid, rule) for gid, rule in RULES if not present(by_id[gid]['IpPermissions'], rule)]
    report = {'observedAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'account': account,
              'sourceCidr': SOURCE, 'applyRequested': apply, 'authorization': [], 'createdRuleIds': [],
              'status': 'READY', 'rules': RULES}
    for gid, rule in missing:
        for operation in ('authorize_security_group_ingress', 'revoke_security_group_ingress'):
            try:
                getattr(ec2, operation)(GroupId=gid, IpPermissions=[rule], DryRun=True)
                code = 'UNEXPECTED_SUCCESS'
            except Exception as error:
                code = getattr(error, 'response', {}).get('Error', {}).get('Code', type(error).__name__)
            report['authorization'].append({'groupId': gid, 'port': rule['FromPort'], 'operation': operation, 'code': code})
            if code != 'DryRunOperation':
                report['status'] = 'BLOCKED'
    if apply and report['status'] == 'READY':
        try:
            for gid, rule in missing:
                response = ec2.authorize_security_group_ingress(GroupId=gid, IpPermissions=[rule])
                report['createdRuleIds'].extend({'groupId': gid, 'ruleId': r['SecurityGroupRuleId']}
                                               for r in response.get('SecurityGroupRules', []))
            after = {g['GroupId']: g for g in ec2.describe_security_groups(GroupIds=[WEB, AAOS])['SecurityGroups']}
            report['verified'] = all(present(after[gid]['IpPermissions'], rule) for gid, rule in RULES)
            report['status'] = 'APPLIED' if report['verified'] else 'BLOCKED'
        except Exception as error:
            report['status'] = 'BLOCKED'
            report['error'] = getattr(error, 'response', {}).get('Error', {}).get('Code', type(error).__name__)
            # Keep receipt of any successful additions; never revoke pre-existing rules.
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity-alias', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    select_identity(args.identity_alias)
    import boto3
    report = configure(boto3.Session(), args.apply)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['status'])
    return 2 if report['status'] == 'BLOCKED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
