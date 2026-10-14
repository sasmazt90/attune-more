import json
import numpy as np

with open(r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\native-material-contour-20261013\added-components-reviewed.json') as f:
    d_added = json.load(f)

with open(r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\dry-sag-component-followup-20261013\object-labels.json') as f:
    d_obj = json.load(f)

# Inspect control 0
c0 = d_obj['controls'][0]
print(f"C0: split={c0['split']}, sourceSHA256={c0['sourceSHA256']}")
for i, o in enumerate(c0['objects']):
    poly = np.array(o['polygon'])
    print(f"  obj {i}: label={o['label']}, poly bbox=[{poly[:,0].min()}, {poly[:,1].min()}, {poly[:,0].max()}, {poly[:,1].max()}]")

# Inspect control 9
c9 = d_obj['controls'][9]
print(f"\nC9: split={c9['split']}, sourceSHA256={c9['sourceSHA256']}")
for i, o in enumerate(c9['objects']):
    poly = np.array(o['polygon'])
    print(f"  obj {i}: label={o['label']}, poly bbox=[{poly[:,0].min()}, {poly[:,1].min()}, {poly[:,0].max()}, {poly[:,1].max()}]")
