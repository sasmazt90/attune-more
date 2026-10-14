import json

for hname in ['encoder-material-head.json', 'encoder-material-balanced-head.json', 'expanded-eight-feature-head.json']:
    p = rf"C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\native-material-contour-20261013\{hname}"
    try:
        with open(p) as f:
            d = json.load(f)
        print(f"=== {hname} ===")
        print(f"  threshold: {d.get('threshold')}, C: {d.get('regularizationC')}, trainRows: {d.get('trainRows')}")
        print(f"  featureGroupSizes: {d.get('featureGroupSizes')}")
        print(f"  lossVersion: {d.get('lossVersion')}")
        print(f"  intercept: {d.get('intercept'):.4f}")
    except Exception as e:
        print(f"{hname}: {e}")
