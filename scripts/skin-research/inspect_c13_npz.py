import numpy as np

for name in ['C13-scale0.5-gated-field.npz', 'C13-scale0.5-gated-field-crop-v2.npz', 'C13-scale0.5-gated-field-balanced.npz']:
    p = rf"C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\native-material-contour-20261013\{name}"
    data = np.load(p, allow_pickle=True)
    print(name, 'keys:', data.files)
    for k in data.files:
        val = data[k]
        if isinstance(val, np.ndarray):
            print(f"   {k}: shape={val.shape}, sum={val.sum():.1f}, max={val.max():.4f}")
        else:
            print(f"   {k}: {val}")
