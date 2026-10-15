import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

from skin_eyewear import classify_source
from prepare_canonical_validation_cache import load_canonical_validation_cache

cached = load_canonical_validation_cache()
neg_items = [c for c in cached if c['isNegative']]
print(f"Total negative cached items: {len(neg_items)}")
for item in neg_items:
    res = classify_source(item['bgr'], item['landmarks'])
    print(f"{item['sha256'][:8]}: prob={res['probability']:.4f}, status={res['status']}")
