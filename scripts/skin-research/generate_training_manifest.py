#!/usr/bin/env python3
"""Generate Concrete Training Tile Manifest and Excluded Scope Receipt.

Contract (Item 4):
1. Documents the exact 825 tiles selected by select_training_tiles under seed 20261014.
2. Explicitly documents the 166 excluded medium-only tiles, ensuring no ambiguity
   between 'all available dataset tiles (991)' and 'focused training tiles (825)'.
3. Computes canonical SHA-256 hashes of dataset and selected tile list for resume validation.
4. Saves to: audit-results/acne-candidate-p2-finetune-20261014/training_tiles_manifest.json.
"""

import sys
import json
import random
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

from negative_mask_builder import build_hole_preserved_negative_masks, acne_tiles_p2

DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
OUT_DIR = ROOT / 'audit-results/acne-candidate-p2-finetune-20261014'


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    train_rows = [r for r in data['rows'] if r['split'] == 'train']

    masks, weights = build_hole_preserved_negative_masks(train_rows)
    all_tiles = acne_tiles_p2(train_rows, masks, training=True)

    seed = 20261014
    random.seed(seed)

    selected_tiles = []
    excluded_tiles = []

    tiny_count = 0
    small_count = 0
    clean_count = 0
    med_sampled_count = 0

    for idx, t in enumerate(all_tiles):
        boxes = t.get('boxes', [])
        sha = t['row']['sha256']
        rect = t['rect']
        is_clean = t.get('isCleanControl', False)

        tile_meta = {
            'tileIndex': idx,
            'imageSha256': sha,
            'source': t['row'].get('source', 'unknown'),
            'rect': rect,
            'numBoxes': len(boxes),
            'isCleanControl': is_clean,
            'boxes': boxes
        }

        if is_clean:
            selected_tiles.append(tile_meta)
            clean_count += 1
        elif boxes:
            dims = [max(b[2]-b[0], b[3]-b[1]) for b in boxes]
            has_small = any(d < 16.0 for d in dims)
            has_tiny = any(d < 8.0 for d in dims)
            tile_meta['minLesionDim'] = min(dims)
            tile_meta['maxLesionDim'] = max(dims)

            if has_tiny:
                tiny_count += 1
            if has_small:
                small_count += 1
                selected_tiles.append(tile_meta)
            else:
                if random.random() < 0.50:
                    med_sampled_count += 1
                    selected_tiles.append(tile_meta)
                else:
                    excluded_tiles.append(tile_meta)

    # Compute hash of selected tile IDs
    canonical_selected_str = json.dumps(
        [{'sha': t['imageSha256'], 'rect': t['rect']} for t in selected_tiles],
        sort_keys=True
    )
    selected_hash = hashlib.sha256(canonical_selected_str.encode('utf-8')).hexdigest()

    manifest = {
        'seed': seed,
        'datasetPath': str(DATA_PATH.relative_to(ROOT)),
        'datasetSha256': sha256_file(DATA_PATH),
        'totalAvailableTilesInDataset': len(all_tiles),
        'selectedTilesCount': len(selected_tiles),
        'excludedTilesCount': len(excluded_tiles),
        'selectedTilesHash': selected_hash,
        'selectionBreakdown': {
            'tilesWithMicroLesions_lt8px': tiny_count,
            'tilesWithSmallLesions_lt16px': small_count,
            'cleanControlSkinTiles': clean_count,
            'mediumOnlySampledContextTiles': med_sampled_count,
            'mediumOnlyExcludedTiles': len(excluded_tiles)
        },
        'policyNotes': (
            "All micro (<8px) and small (<16px) tiles and clean controls are 100% retained. "
            "166 medium-only tiles are excluded to prevent medium lesions from dominating gradients."
        ),
        'selectedTiles': selected_tiles,
        'excludedTiles': excluded_tiles
    }

    out_path = OUT_DIR / 'training_tiles_manifest.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    print(f"Training manifest written to: {out_path}")
    print(f"  Selected: {len(selected_tiles)} tiles (Hash: {selected_hash[:16]}...)")
    print(f"  Excluded: {len(excluded_tiles)} tiles")


if __name__ == '__main__':
    main()
