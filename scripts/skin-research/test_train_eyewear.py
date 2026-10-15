import sys, json, cv2
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))

from skin_eyewear import classify_source

DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
data = json.load(open(DATA_PATH, encoding='utf-8'))
train_rows_by_sha = {r['sha256']: r for r in data['rows'] if r['split'] == 'train'}

target_shas = [
    '041e9e1973e0b3d65a4d181ed73b6b8884534db968e91b417b61afc6602b27b3',
    '00446fa8cf27f1d8b2ec9d1bc03501d5255292e4b0c44d7da11d0cbc58cf2c3d',
    '0b5a3d87bf2a7f93af62e24c39360d6798e12538345eb6ac0713a29966b03a70'
]

print("=== CHECKING TRAINING EYEWEAR SOURCES ===")
for sha in target_shas:
    r = train_rows_by_sha.get(sha)
    if not r:
        print(f"{sha[:8]}: Not found in train rows!")
        continue
    img_path = Path(r.get('absolutePath')) if r.get('absolutePath') and Path(r['absolutePath']).exists() else (LIVE_TEST / r['path'])
    bgr = cv2.imread(str(img_path))
    points = r.get('landmarks', [])
    if not points:
        print(f"{sha[:8]}: No landmarks in row!")
        continue
    res = classify_source(bgr, points)
    print(f"{sha[:8]}: prob={res['probability']:.4f}, status={res['status']}, source={r.get('source')}, boxes={len(r.get('annotations', []))}")
