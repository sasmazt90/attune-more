#!/usr/bin/env python3
"""Offline gate for a reviewed additive rules change set. Never executes CloudFormation."""
import argparse
import json
from pathlib import Path

ALLOWED = {'WebHttps', 'AaosHttps', 'PrivateApi'}


def validate(change_set, stack):
    if stack.get('StackStatus') != 'REVIEW_IN_PROGRESS' or not stack.get('StackId') or stack['StackId'] != change_set.get('StackId') or change_set.get('ImportExistingResources') or change_set.get('IncludeNestedStacks') or change_set.get('ParentChangeSetId'):
        raise ValueError('Only a separate CREATE rules stack is permitted; never UPDATE/IMPORT the old infrastructure stack')
    if change_set.get('Status') != 'CREATE_COMPLETE' or change_set.get('ExecutionStatus') != 'AVAILABLE':
        raise ValueError('Change set must be complete and available for inspection')
    if change_set.get('NextToken'):
        raise ValueError('Read every change-set page before review; partial evidence is refused')
    changes=change_set.get('Changes', [])
    if not changes:
        raise ValueError('No missing rules to apply')
    names=set()
    for change in changes:
        resource=change.get('ResourceChange', {})
        name=resource.get('LogicalResourceId')
        if (change.get('Type')!='Resource' or resource.get('Action')!='Add' or
            resource.get('ResourceType')!='AWS::EC2::SecurityGroupIngress' or
            name not in ALLOWED or name in names or resource.get('Replacement') not in (None,'False') or
            resource.get('PhysicalResourceId') or resource.get('ChangeSetId')):
            raise ValueError('Refusing new infrastructure, duplicate rules, nested stacks, imports, updates, replacements or deletions')
        names.add(name)
    return sorted(names)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('change_set',type=Path);parser.add_argument('stack',type=Path,help='DescribeStacks response for the same new rules stack')
    args=parser.parse_args()
    print(json.dumps({'reviewedRuleNames':validate(json.loads(args.change_set.read_text()),json.loads(args.stack.read_text())['Stacks'][0]),
                      'executed':False,'note':'Also review template/parameters against live inventory; this gate is not authorization.'}))
