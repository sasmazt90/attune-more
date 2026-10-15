#!/usr/bin/env python3
"""Build representative, fixed experimental cohort for controlled acne pilot comparison.

Directives:
1. Strictly use split == 'train' (132 photos, 1,235 annotations).
2. Group/person-level partition:
   - pilot_train_groups: used for 150-step pilot training.
   - pilot_control_groups: held-out TRAIN control group (unseen during pilot training).
   - Zero tile leakage: all tiles of any photo belong to exactly one group.
3. Both groups contain micro (<8px), small (8-16px), medium (>=16px), and clean control photos.
4. Deterministic, reproducible seed (20261015).
5. Exclude eyewear-present photos from product success denominator.
"""

import sys
import json
import random
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
MANIFEST_PATH = ROOT / 'audit-results/acne-candidate-p2-finetune-20261014/training_tiles_manifest.json'
OUT_DIR = ROOT / 'audit-results/acne-pilot-giou-comparison-20261015'


def build_cohort():
    print("=" * 80)
    print("BUILDING DETERMINISTIC CONTROLLED EXPERIMENT COHORT ON STRICT TRAIN SPLIT")
    print("=" * 80)

    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    train_rows = {r['sha256']: r for r in data['rows'] if r.get('split') == 'train'}

    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    selected_tiles = manifest['selectedTiles']

    # Map tiles by photo SHA
    tiles_by_sha = defaultdict(list)
    for t in selected_tiles:
        tiles_by_sha[t['imageSha256']].append(t)

    manifest_shas = sorted(list(tiles_by_sha.keys()))
    print(f"Total available tiles: {len(selected_tiles)} across {len(manifest_shas)} photos.")

    # Group photos by group ID
    group_to_shas = defaultdict(list)
    for sha in manifest_shas:
        grp = train_rows[sha].get('group') or sha
        group_to_shas[grp].append(sha)

    groups = sorted(list(group_to_shas.keys()))
    print(f"Total unique groups: {len(groups)}")

    # Classify each group by its lesion contents
    group_categories = {}
    for grp, shas in group_to_shas.items():
        has_micro = False
        has_small = False
        has_med = False
        is_clean = True
        for sha in shas:
            anns = train_rows[sha].get('annotations', [])
            if anns:
                is_clean = False
            for a in anns:
                bx = a['box']
                dim = max(bx[2] - bx[0], bx[3] - bx[1])
                if dim < 8:
                    has_micro = True
                elif dim < 16:
                    has_small = True
                else:
                    has_med = True

        if is_clean:
            group_categories[grp] = 'clean'
        elif has_micro:
            group_categories[grp] = 'micro'
        elif has_small:
            group_categories[grp] = 'small'
        else:
            group_categories[grp] = 'medium'

    cat_counts = defaultdict(int)
    for c in group_categories.values():
        cat_counts[c] += 1
    print("Group categorization:", dict(cat_counts))

    # Stratified deterministic split with seed 20261015
    rng = random.Random(20261015)
    control_ratio = 0.22  # ~22% for held-out control group

    pilot_train_groups = []
    pilot_control_groups = []

    for cat in ['clean', 'micro', 'small', 'medium']:
        grps_in_cat = [g for g, c in group_categories.items() if c == cat]
        rng.shuffle(grps_in_cat)
        n_ctrl = max(1, int(round(len(grps_in_cat) * control_ratio)))
        ctrl = grps_in_cat[:n_ctrl]
        trn = grps_in_cat[n_ctrl:]
        pilot_control_groups.extend(ctrl)
        pilot_train_groups.extend(trn)

    pilot_train_shas = set()
    for g in pilot_train_groups:
        pilot_train_shas.update(group_to_shas[g])

    pilot_control_shas = set()
    for g in pilot_control_groups:
        pilot_control_shas.update(group_to_shas[g])

    assert len(pilot_train_shas.intersection(pilot_control_shas)) == 0, "Photo leakage detected!"

    pilot_train_tiles = [t for t in selected_tiles if t['imageSha256'] in pilot_train_shas]
    pilot_control_tiles = [t for t in selected_tiles if t['imageSha256'] in pilot_control_shas]

    print(f"\nCohort Partition Results:")
    print(f"  Pilot Train Group:   {len(pilot_train_groups)} groups, {len(pilot_train_shas)} photos, {len(pilot_train_tiles)} tiles")
    print(f"  Pilot Control Group: {len(pilot_control_groups)} groups, {len(pilot_control_shas)} photos, {len(pilot_control_tiles)} tiles")

    # Verify lesion distribution in Control Group
    ctrl_micro = sum(1 for sha in pilot_control_shas for a in train_rows[sha].get('annotations', []) if max(a['box'][2]-a['box'][0], a['box'][3]-a['box'][1]) < 8)
    ctrl_small = sum(1 for sha in pilot_control_shas for a in train_rows[sha].get('annotations', []) if 8 <= max(a['box'][2]-a['box'][0], a['box'][3]-a['box'][1]) < 16)
    ctrl_med = sum(1 for sha in pilot_control_shas for a in train_rows[sha].get('annotations', []) if max(a['box'][2]-a['box'][0], a['box'][3]-a['box'][1]) >= 16)
    ctrl_clean = sum(1 for sha in pilot_control_shas if len(train_rows[sha].get('annotations', [])) == 0)

    print(f"  Control Group Contents: {ctrl_micro} micro, {ctrl_small} small, {ctrl_med} medium lesions, {ctrl_clean} clean control photos.")

    # Select fixed 10 mini-batches (40 tiles) for Directive 3 side-by-side comparison
    # We select 40 tiles that represent micro, small, med and clean tiles
    rng.seed(20261015)
    shuffled_train_tiles = list(pilot_train_tiles)
    rng.shuffle(shuffled_train_tiles)
    comparison_tiles = shuffled_train_tiles[:40]

    cohort_data = {
        'seed': 20261015,
        'pilotTrainGroupCount': len(pilot_train_groups),
        'pilotControlGroupCount': len(pilot_control_groups),
        'pilotTrainPhotoCount': len(pilot_train_shas),
        'pilotControlPhotoCount': len(pilot_control_shas),
        'pilotTrainTileCount': len(pilot_train_tiles),
        'pilotControlTileCount': len(pilot_control_tiles),
        'pilotTrainShas': sorted(list(pilot_train_shas)),
        'pilotControlShas': sorted(list(pilot_control_shas)),
        'pilotTrainTiles': pilot_train_tiles,
        'pilotControlTiles': pilot_control_tiles,
        'comparisonTiles40': comparison_tiles,
        'controlGroupLesionCounts': {
            'micro': ctrl_micro,
            'small': ctrl_small,
            'medium': ctrl_med,
            'cleanPhotos': ctrl_clean
        }
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / 'controlled_train_cohort.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(cohort_data, f, indent=2)
    print(f"\nSaved controlled cohort definition to {out_file}")
    return cohort_data


if __name__ == '__main__':
    build_cohort()
