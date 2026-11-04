import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/aws'))
from configure_ingress import ACCOUNT, AAOS, WEB, RULES, configure, present, validate_topology
from targets import TARGETS


def topology():
    instances = [{'InstanceId': ident, 'InstanceType': target['type'],
                  'Tags': [{'Key': 'Name', 'Value': target['name']}],
                  'VpcId': 'vpc-existing', 'SecurityGroups': [{'GroupId': group}]}
                 for (ident, target), group in zip(TARGETS.items(), (WEB, AAOS))]
    groups = [{'GroupId': group, 'OwnerId': ACCOUNT, 'VpcId': 'vpc-existing', 'IpPermissions': []}
              for group in (WEB, AAOS)]
    interfaces = [{'Attachment': {'InstanceId': ident}} for ident in TARGETS]
    return instances, groups, interfaces


def test_sources_are_exact_and_descriptions_do_not_break_idempotency():
    for _, rule in RULES:
        observed = copy.deepcopy(rule)
        key = 'IpRanges' if 'IpRanges' in rule else 'UserIdGroupPairs'
        observed[key][0]['Description'] = 'existing rule'
        assert present([observed], rule)
    broad = dict(RULES[0][1], IpRanges=[{'CidrIp': '0.0.0.0/0'}])
    assert not present([broad], RULES[0][1])


def test_shared_interface_and_changed_attachment_are_rejected():
    instances, groups, interfaces = topology()
    validate_topology(instances, groups, interfaces)
    with pytest.raises(ValueError, match='unrelated'):
        validate_topology(instances, groups, interfaces + [{'Attachment': {'InstanceId': 'i-unrelated'}}])
    instances[0]['SecurityGroups'] = [{'GroupId': AAOS}]
    with pytest.raises(ValueError, match='attachment'):
        validate_topology(instances, groups, interfaces)


def test_any_denied_preflight_prevents_all_writes():
    instances, groups, interfaces = topology()
    calls = []
    class AwsError(Exception):
        def __init__(self, code):
            self.response = {'Error': {'Code': code}}
    def mutation(**kwargs):
        calls.append(kwargs)
        assert kwargs.get('DryRun') is True
        raise AwsError('UnauthorizedOperation' if kwargs['GroupId'] == AAOS else 'DryRunOperation')
    ec2 = SimpleNamespace(
        describe_instances=lambda **kw: {'Reservations': [{'Instances': instances}]},
        describe_security_groups=lambda **kw: {'SecurityGroups': groups},
        get_paginator=lambda *a: SimpleNamespace(paginate=lambda **kw: [{'NetworkInterfaces': interfaces}]),
        authorize_security_group_ingress=mutation, revoke_security_group_ingress=mutation)
    session = SimpleNamespace(client=lambda name, **kw: ec2 if name == 'ec2' else
                              SimpleNamespace(get_caller_identity=lambda: {'Account': ACCOUNT}))
    report = configure(session, apply=True)
    assert report['status'] == 'BLOCKED'
    assert report['createdRuleIds'] == []
    assert len(calls) == 6
