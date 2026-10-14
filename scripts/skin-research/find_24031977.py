import json

with open(r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\dry-sag-component-followup-20261013\object-labels.json') as f:
    d = json.load(f)

for c in d['controls']:
    if '24031977' in c.get('sourcePath', '') or '24031977' in c.get('sourceSHA256', ''):
        print(f"controlIndex={c['controlIndex']}, kind={c['kind']}, split={c['split']}, path={c['sourcePath']}")
        for i, obj in enumerate(c.get('objects', [])):
            print(f"   obj {i}: label={obj['label']}, polygon_points={len(obj['polygon'])}")
