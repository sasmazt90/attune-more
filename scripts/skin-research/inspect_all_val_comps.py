import json

with open(r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\native-material-contour-20261013\material-encoder-scale-corrected.json') as f:
    d = json.load(f)

val_comps = d.get('validationComponents', [])
print("All 28 validation components:")
for i, c in enumerate(val_comps):
    print(f"[{i:02d}] ctrl={c['controlIndex']}, compId={c['componentId']}, label={c['label']}, class={c.get('class')}, p={c.get('encoderProbability'):.4f}, geomAcc={c.get('geometryAccepted')}, encAcc={c.get('encoderAccepted')}")
