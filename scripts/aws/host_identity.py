#!/usr/bin/env python3
"""Fail before host mutation unless IMDSv2 identifies the assigned existing AWS host."""
import argparse
import json
import urllib.request
from targets import REGION, TARGETS


def verify(document, role):
    expected=[key for key,value in TARGETS.items() if value['role']==role]
    if len(expected)!=1 or document.get('instanceId')!=expected[0] or document.get('region')!=REGION or document.get('instanceType')!=TARGETS[expected[0]]['type']:
        raise ValueError('Refusing installation outside the assigned existing Frankfurt instance')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--role',choices=['web','aaos'],required=True)
    args=parser.parse_args()
    # IMDS is link-local on the target EC2, not a public endpoint or credential lookup.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base='http://169.254.169.254/latest/'
    with opener.open(urllib.request.Request(base+'api/token',method='PUT',headers={'X-aws-ec2-metadata-token-ttl-seconds':'60'}),timeout=3) as response:
        token=response.read().decode()
    with opener.open(urllib.request.Request(base+'dynamic/instance-identity/document',headers={'X-aws-ec2-metadata-token':token}),timeout=3) as response:
        verify(json.load(response),args.role)
    print('Existing EC2 role identity verified')

if __name__=='__main__':main()
