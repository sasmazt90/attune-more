import json
import numpy as np

features_path = r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\native-material-contour-20261013\7c916c52e1364b83-encoder-features.npz'
data = np.load(features_path, allow_pickle=True)
features = data['features']
print('Features shape:', features.shape)

with open(r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\native-material-contour-20261013\material-encoder-scale-corrected.json') as f:
    d = json.load(f)

print('Train rows:', d['trainRows'])
print('Train groups:', d['trainGroups'])
print('Train class counts:', d['trainClassCounts'])
print('Validation rows:', d['validationRows'])
