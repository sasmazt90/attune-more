import json

with open(r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\material-closeout-20261013\group-loss-comparison.json') as f:
    d = json.load(f)

for item in d['after']:
    if item.get('control') == 13 and item.get('factor') == 0.5:
        print(json.dumps(item, indent=2))
