import json

with open(r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\material-closeout-20261013\group-loss-comparison.json') as f:
    d = json.load(f)

for stage in ['before', 'after']:
    print(f"=== {stage} ===")
    for item in d[stage]:
        if item.get('control') == 13:
            print(f"control=13, factor={item['factor']}, split={item['split']}, source={item['source'][:16]}")
            for obj in item.get('objects', []):
                print(f"   obj {obj['index']}: label={obj['label']}, hit={obj['measure']['objectHit']}, activePixels={obj['measure']['activeSourcePixels']}")
            neg = item.get('negative', {})
            print(f"   negative: activePixels={neg.get('activeSourcePixels')}, reviewed={neg.get('reviewedSourcePixels')}")
