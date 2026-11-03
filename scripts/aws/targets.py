"""Owner-supplied existing resources. Never infer or discover replacement targets."""
REGION = 'eu-central-1'
TARGETS = {
    'i-0b25450afc6633494': {'role': 'web', 'name': 'attune-web-ai', 'type': 'r7i.2xlarge', 'rootGiB': 150},
    'i-0f4cca4e92e94c351': {'role': 'aaos', 'name': 'attune-aaos-demo', 'type': 'm8i.2xlarge', 'rootGiB': 120},
}
IDS = tuple(TARGETS)


def validate_instances(instances, ids=IDS):
    if len(ids) != 2 or set(ids) != set(IDS) or len(instances) != 2 or {i['InstanceId'] for i in instances} != set(IDS):
        raise ValueError('Only the two owner-supplied existing instance IDs are permitted')
    for instance in instances:
        target = TARGETS[instance['InstanceId']]
        tags = {t['Key']: t['Value'] for t in instance.get('Tags', [])}
        if instance['InstanceType'] != target['type'] or tags.get('Name') != target['name']:
            raise ValueError('Existing instance name/type does not match its recorded ID')
