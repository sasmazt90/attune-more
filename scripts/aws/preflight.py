#!/usr/bin/env python3
"""Read-only AWS evidence. Unknown permissions/quota/capacity are never PASS."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path

from targets import REGION, TARGETS
TYPES = tuple(t['type'] for t in TARGETS.values())


def select_identity(alias):
    path = os.getenv('OIC_MANIFEST_PATH')
    if not path:
        # Normal short-lived STS SDK credentials are the documented fallback.
        if alias:
            raise ValueError('Identity alias requested but OIC_MANIFEST_PATH is missing')
        return
    manifest = json.loads(Path(path).read_text())
    matches = [c for c in manifest.get('connections', [])
               if c.get('provider_kind') == 'aws' and c.get('alias') == alias]
    if manifest.get('version') != 1 or len(matches) != 1 or not matches[0].get('config_file'):
        raise ValueError('Select one configured AWS alias from the version-1 manifest')
    os.environ['AWS_PROFILE'] = matches[0]['alias']
    os.environ['AWS_CONFIG_FILE'] = matches[0]['config_file']


def price_per_unit(products, unit):
    prices = set()
    for raw in products:
        product = json.loads(raw)
        for term in product.get('terms', {}).get('OnDemand', {}).values():
            for dimension in term.get('priceDimensions', {}).values():
                if dimension['unit'] == unit:
                    prices.add(float(dimension['pricePerUnit']['USD']))
    if len(prices) != 1:
        raise ValueError('Expected exactly one matching On-Demand unit price')
    return prices.pop()


def price_per_hour(products):
    return price_per_unit(products, 'Hrs')


def collect(session):
    report = {'region': REGION, 'observedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
              'checks': {}, 'capacity': 'BLOCKED: offerings do not guarantee launch capacity'}
    def check(name, call):
        try:
            value = call()
            report['checks'][name] = {'status': 'OBSERVED', 'value': value}
            return value
        except Exception as error:
            # Never include SDK credential objects or request headers in evidence.
            code = getattr(error, 'response', {}).get('Error', {}).get('Code', type(error).__name__)
            report['checks'][name] = {'status': 'BLOCKED', 'reason': code}
    ec2 = session.client('ec2', region_name=REGION)
    quota = session.client('service-quotas', region_name=REGION)
    pricing = session.client('pricing', region_name='us-east-1')
    check('identity', lambda: session.client('sts', region_name=REGION).get_caller_identity()['Account'])
    for name, code in [('g_vt_quota', 'L-DB2E81BA'), ('standard_quota', 'L-1216C47A')]:
        check(name, lambda code=code: quota.get_service_quota(ServiceCode='ec2', QuotaCode=code)['Quota']['Value'])
    check('types', lambda: ec2.describe_instance_types(InstanceTypes=list(TYPES))['InstanceTypes'])
    check('offerings', lambda: [i for page in ec2.get_paginator('describe_instance_type_offerings').paginate(
        LocationType='availability-zone', Filters=[{'Name':'instance-type','Values':list(TYPES)}]) for i in page['InstanceTypeOfferings']])
    # All live/pending instances matter to shared quotas, not just task-tagged resources.
    check('existing_usage', lambda: [
        {'type':i['InstanceType'],'state':i['State']['Name'], 'id':i['InstanceId']}
        for page in ec2.get_paginator('describe_instances').paginate(Filters=[{'Name':'instance-state-name','Values':['pending','running','stopping']}])
        for reservation in page['Reservations'] for i in reservation['Instances']])
    for typ in TYPES:
        filters = [{'Type':'TERM_MATCH','Field':k,'Value':v} for k,v in {
            'instanceType':typ,'regionCode':REGION,'operatingSystem':'Linux',
            'tenancy':'Shared','preInstalledSw':'NA','capacitystatus':'Used'}.items()]
        check('price_'+typ, lambda filters=filters: price_per_hour([
            p for page in pricing.get_paginator('get_products').paginate(ServiceCode='AmazonEC2',Filters=filters)
            for p in page['PriceList']]))
    for name, service, unit, attributes in [
        ('price_gp3_gb_month', 'AmazonEC2', 'GB-Mo', {'regionCode':REGION, 'volumeApiName':'gp3', 'productFamily':'Storage'}),
        ('price_ipv4_in_use', 'AmazonVPC', 'Hrs', {'regionCode':REGION, 'usagetype':'EUC1-PublicIPv4:InUseAddress'}),
        ('price_ipv4_idle', 'AmazonVPC', 'Hrs', {'regionCode':REGION, 'usagetype':'EUC1-PublicIPv4:IdleAddress'}),
    ]:
        filters=[{'Type':'TERM_MATCH','Field':key,'Value':value} for key,value in attributes.items()]
        check(name, lambda service=service, filters=filters, unit=unit: price_per_unit([
            p for page in pricing.get_paginator('get_products').paginate(ServiceCode=service,Filters=filters)
            for p in page['PriceList']], unit))
    report['provisioningAuthorized'] = False
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--identity-alias')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        select_identity(args.identity_alias)
        import boto3
        report = collect(boto3.Session())
    except Exception as error:
        report = {'region':REGION,'status':'BLOCKED','reason':type(error).__name__, 'provisioningAuthorized':False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,default=str)+'\n')
    print(args.output)
    return 2 if report.get('status') == 'BLOCKED' or any(v['status']=='BLOCKED' for v in report.get('checks',{}).values()) else 0

if __name__ == '__main__':
    raise SystemExit(main())
