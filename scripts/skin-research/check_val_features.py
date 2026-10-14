import json
import numpy as np

features_path = r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\native-material-contour-20261013\7c916c52e1364b83-encoder-features.npz'
data = np.load(features_path, allow_pickle=True)
features = data['features']

with open(r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\material-closeout-20261013\source-group-head.json') as f:
    head = json.load(f)

# The validation rows are the last 28 rows of features (or check where validation features are)
print('Total features rows:', features.shape[0])
# Earlier we saw 63 train rows, 28 validation rows
# Let's check which rows of features correspond to the 28 validation components
