import json

with open(r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\material-closeout-20261013\group-loss-comparison.json') as f:
    d = json.load(f)

for item in d['after']:
    if item['split'] == 'validation' and item['factor'] == 0.5:
        neg = item.get('negative', {})
        if neg.get('activeSourcePixels', 0) > 0:
            print(f"control={item['control']}, source={item['source'][:16]}, negActive={neg['activeSourcePixels']}, negReviewed={neg['reviewedSourcePixels']}")
            for obj in item.get('objects', []):
                print(f"   obj {obj['index']}: label={obj['label']}, hit={obj['measure']['objectHit']}, activePixels={obj['measure']['activeSourcePixels']}")

for item in d['before']:
    if item['split'] == 'validation' and item['factor'] == 0.5:
        neg = item.get('negative', {})
        if neg.get('activeSourcePixels', 0) > 0:
            print(f"[BEFORE] control={item['control']}, source={item['source'][:16]}, negActive={neg['activeSourcePixels']}")
