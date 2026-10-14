import numpy as np
import json

with open(r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\dry-sag-component-followup-20261013\object-labels.json') as f:
    d_obj = json.load(f)

for c_num, name in [(0, 'C00'), (9, 'C09')]:
    c_info = d_obj['controls'][c_num]
    roi = c_info.get('roi', [0, 0, 0, 0])
    print(f"\n=== Control {c_num} ({name}) ===")
    print(f"ROI: {roi}")
    
    # Load gated field
    for suffix in ['balanced', 'crop-v2', '']:
        fname = f"{name}-scale1.0-gated-field{'-' + suffix if suffix else ''}.npz"
        p = rf"C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\native-material-contour-20261013\{fname}"
        try:
            d = np.load(p, allow_pickle=True)
            fld = d['field']
            print(f"  {fname}: field shape={fld.shape}, sum={fld.sum():.1f}, nonzeros={(fld>0).sum()}")
        except Exception as e:
            print(f"  {fname}: {e}")
