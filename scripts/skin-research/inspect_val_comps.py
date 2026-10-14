import json

with open(r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\native-material-contour-20261013\material-encoder-scale-corrected.json') as f:
    d = json.load(f)

val_comps = d.get('validationComponents', [])
print(f"Validation components count: {len(val_comps)}")
if val_comps:
    print("Sample val component:", val_comps[0])
