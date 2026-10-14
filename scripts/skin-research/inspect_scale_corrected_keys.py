import json

with open(r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\native-material-contour-20261013\material-encoder-scale-corrected.json') as f:
    d = json.load(f)

for k in list(d.keys())[:15]:
    if k not in ['summary', 'features']:
        print(k, type(d[k]))

if 'trainIndices' in d:
    print('trainIndices:', d['trainIndices'])
elif 'rows' in d:
    print('rows count:', len(d['rows']))
    print('rows[0]:', d['rows'][0])
