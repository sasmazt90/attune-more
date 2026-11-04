#!/usr/bin/env python3
"""Read existing EC2 dependencies, including stopped hosts; never create or mutate AWS resources."""
import argparse
import datetime as dt
import json
from pathlib import Path
from targets import IDS, REGION, TARGETS, validate_instances
from preflight import select_identity


def collect(session):
    report = {'region': REGION, 'observedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
              'targetIds': list(IDS), 'checks': {}, 'findings': [], 'mutations': []}
    def read(name, call):
        try:
            value = call()
            report['checks'][name] = {'status': 'OBSERVED', 'value': value}
            return value
        except Exception as error:
            code = getattr(error, 'response', {}).get('Error', {}).get('Code', type(error).__name__)
            report['checks'][name] = {'status': 'BLOCKED', 'reason': code}
            return None
    ec2 = session.client('ec2', region_name=REGION)
    account = read('account', lambda: session.client('sts', region_name=REGION).get_caller_identity()['Account'])
    reservations = read('reservations', lambda: ec2.describe_instances(InstanceIds=list(IDS))['Reservations'])
    if account is None or reservations is None:
        report['status'] = 'BLOCKED'
        return report
    instances = [i for r in reservations for i in r['Instances']]
    try:
        validate_instances(instances)
        if any(r['OwnerId'] != account for r in reservations):
            raise ValueError('Account does not own both targets')
    except (ValueError, KeyError):
        report['status'] = 'BLOCKED'
        report['findings'].append('Target identity/account mismatch; no dependency inspection or mutation permitted')
        return report
    volume_ids = sorted({b['Ebs']['VolumeId'] for i in instances for b in i.get('BlockDeviceMappings', []) if 'Ebs' in b})
    group_ids = sorted({g['GroupId'] for i in instances for g in i.get('SecurityGroups', [])})
    subnet_ids = sorted({i['SubnetId'] for i in instances})
    vpc_ids = sorted({i['VpcId'] for i in instances})
    volumes = read('volumes', lambda: ec2.describe_volumes(VolumeIds=volume_ids)['Volumes']) if volume_ids else None
    groups = read('securityGroups', lambda: ec2.describe_security_groups(GroupIds=group_ids)['SecurityGroups']) if group_ids else None
    read('subnets', lambda: ec2.describe_subnets(SubnetIds=subnet_ids)['Subnets'])
    read('vpcs', lambda: ec2.describe_vpcs(VpcIds=vpc_ids)['Vpcs'])
    read('images', lambda: ec2.describe_images(ImageIds=sorted({i['ImageId'] for i in instances}))['Images'])
    read('addresses', lambda: ec2.describe_addresses(Filters=[{'Name': 'instance-id', 'Values': list(IDS)}])['Addresses'])
    read('routeTables', lambda: ec2.describe_route_tables(Filters=[{'Name': 'vpc-id', 'Values': vpc_ids}])['RouteTables'])
    read('networkAcls', lambda: ec2.describe_network_acls(Filters=[{'Name': 'association.subnet-id', 'Values': subnet_ids}])['NetworkAcls'])
    read('internetGateways', lambda: ec2.describe_internet_gateways(Filters=[{'Name': 'attachment.vpc-id', 'Values': vpc_ids}])['InternetGateways'])
    read('vpcEndpoints', lambda: ec2.describe_vpc_endpoints(Filters=[{'Name': 'vpc-id', 'Values': vpc_ids}])['VpcEndpoints'])
    enis = read('groupInterfaces', lambda: [v for p in ec2.get_paginator('describe_network_interfaces').paginate(
        Filters=[{'Name': 'group-id', 'Values': group_ids}]) for v in p['NetworkInterfaces']]) if group_ids else None
    ssm = session.client('ssm', region_name=REGION)
    read('ssm', lambda: ssm.describe_instance_information(Filters=[{'Key': 'InstanceIds', 'Values': list(IDS)}])['InstanceInformationList'])
    iam = session.client('iam')
    for instance in instances:
        ident = instance['InstanceId']
        arn = instance.get('IamInstanceProfile', {}).get('Arn')
        if not arn:
            report['findings'].append(f'{ident}: no instance profile; SSM role attachment must be reviewed')
            continue
        profile = read('profile:' + ident, lambda arn=arn: iam.get_instance_profile(InstanceProfileName=arn.rsplit('/', 1)[-1])['InstanceProfile'])
        for role in (profile or {}).get('Roles', []):
            name = role['RoleName']
            read('role:' + name, lambda name=name: iam.get_role(RoleName=name)['Role'])
            attached = read('managedPolicies:' + name, lambda name=name: [p for page in iam.get_paginator('list_attached_role_policies').paginate(RoleName=name) for p in page['AttachedPolicies']])
            inline = read('inlinePolicyNames:' + name, lambda name=name: [p for page in iam.get_paginator('list_role_policies').paginate(RoleName=name) for p in page['PolicyNames']])
            for policy_name in inline or []:
                read(f'inlinePolicy:{name}:{policy_name}', lambda name=name, p=policy_name: iam.get_role_policy(RoleName=name, PolicyName=p)['PolicyDocument'])
            policies = [p['PolicyArn'] for p in attached or []]
            if role.get('PermissionsBoundary'):
                policies.append(role['PermissionsBoundary']['PermissionsBoundaryArn'])
            for policy_arn in policies:
                policy = read('policy:' + policy_arn, lambda arn=policy_arn: iam.get_policy(PolicyArn=arn)['Policy'])
                if policy:
                    read('policyVersion:' + policy_arn, lambda arn=policy_arn, version=policy['DefaultVersionId']: iam.get_policy_version(PolicyArn=arn, VersionId=version)['PolicyVersion'])
    report['findings'].extend(assess(instances, volumes, groups, enis))
    report['status'] = 'BLOCKED' if any(c['status'] == 'BLOCKED' for c in report['checks'].values()) else 'OBSERVED'
    report['deploymentReadiness'] = 'REVIEW_REQUIRED'  # Raw API success is never a networking/IAM/runtime PASS.
    return report


def assess(instances, volumes, groups, enis):
    findings = []
    if len({i['VpcId'] for i in instances}) != 1:
        findings.append('Hosts are in different VPCs; private routing requires review; do not create a VPC or replacement host')
    if any(e.get('Attachment', {}).get('InstanceId') not in IDS for e in enis or []):
        findings.append('A security group is shared with other interfaces; changes could affect unrelated workloads')
    for instance in instances:
        ident = instance['InstanceId']
        if instance['State']['Name'] != 'stopped':
            findings.append(f'{ident}: state is not stopped; inspect active work before any operation')
        if instance.get('MetadataOptions', {}).get('HttpTokens') != 'required':
            findings.append(f'{ident}: IMDSv2 is not required; review in-place metadata option change')
        if TARGETS[ident]['role'] == 'aaos' and instance.get('CpuOptions', {}).get('NestedVirtualization') != 'enabled':
            findings.append(f'{ident}: nested virtualization is not observed enabled; review stopped-instance CPU options')
        root_ids = {b['Ebs']['VolumeId'] for b in instance.get('BlockDeviceMappings', []) if b.get('DeviceName') == instance.get('RootDeviceName') and 'Ebs' in b}
        roots = [v for v in volumes or [] if v['VolumeId'] in root_ids]
        if len(roots) != 1 or roots[0]['VolumeType'] != 'gp3' or roots[0]['Size'] != TARGETS[ident]['rootGiB']:
            findings.append(f'{ident}: root disk differs from declared {TARGETS[ident]["rootGiB"]} GiB gp3 or is unobserved; do not resize/replace automatically')
        if any(not v.get('Encrypted') for v in roots):
            findings.append(f'{ident}: root volume is unencrypted; encryption requires a separate migration, no replacement authorized')
    for group in groups or []:
        for rule in group.get('IpPermissions', []):
            if (rule.get('IpRanges') or rule.get('Ipv6Ranges') or rule.get('PrefixListIds')) and not (rule.get('IpProtocol') == 'tcp' and rule.get('FromPort') == rule.get('ToPort') == 443):
                findings.append(f'{group["GroupId"]}: non-HTTPS CIDR/prefix-list ingress needs review; do not revoke shared rules blindly')
    findings.append('Review routes/NACLs, 443 source CIDRs, private 8443 SG pair, egress and SSM policies against live evidence; stopped SSM offline is expected')
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity-alias')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        select_identity(args.identity_alias)
        import boto3
        report = collect(boto3.Session())
    except Exception as error:
        report = {'status': 'BLOCKED', 'reason': type(error).__name__, 'region': REGION, 'targetIds': list(IDS), 'mutations': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + '\n')
    print(args.output)
    return 2 if report['status'] == 'BLOCKED' else 0

if __name__ == '__main__':
    raise SystemExit(main())
