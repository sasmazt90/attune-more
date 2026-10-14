import json

with open(r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\material-closeout-20261013\group-loss-comparison.json') as f:
    d = json.load(f)

print('Summary:', json.dumps(d['summary'], indent=2))

for stage in ['before', 'after']:
    print(f'=== {stage} ===')
    for item in d[stage]:
        if '24031977' in item.get('source', '') or item.get('control') in [0, 9]:
            print(f"control={item['control']}, factor={item['factor']}, split={item['split']}, source={item['source'][:16]}...")
            for obj in item.get('objects', []):
                print(f"   obj {obj['index']}: label={obj['label']}, hit={obj['measure']['objectHit']}, activePixels={obj['measure']['activeSourcePixels']}, largestComp={obj['measure']['largestSourceComponent']}")
            if 'negative' in item:
                neg = item['negative']
                print(f"   negative: activePixels={neg['activeSourcePixels']}, reviewedPixels={neg['reviewedSourcePixels']}")
