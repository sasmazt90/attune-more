"""Fixed TRAIN object replay; never used as held-out acceptance evidence."""
import argparse
import json

from acne_takeover_support import OUT, read, digest
from heavy_job_lease import HeavyJobLease


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['control', 'hard-negative'], required=True)
    args = parser.parse_args()
    baseline = read(OUT / 'source-negative-repair-probe.json')
    rows = {r['sha256']: r for r in read(OUT / 'inputs/original-reviewed-detector-data.json')['rows'] if r['split'] == 'train'}
    curated = {r['sha256']: r for r in read(OUT / 'inputs/train-data-engineering-reviewed-20261013.json')['rows'] if r['split'] == 'train'}
    model = OUT / ('clean-pilot-' + args.model) / 'model.safetensors'
    receipt = read(model.parent / 'receipt.json')
    assert digest(model) == receipt['checkpointSHA256']
    result = []
    with HeavyJobLease('CDC-acne-fixed-TRAIN-replay-' + args.model, peak_mib=1350, minimum_available_mib=1600, memory_metric='private') as lease:
        import cv2
        import numpy as np
        import torch
        from pathlib import Path
        from safetensors.torch import load_file
        from yolox_p2 import build_yolox_p2_model
        from acne_object_negatives import reviewed_object_negative_mask
        torch.set_num_threads(4)
        net = build_yolox_p2_model()
        net.load_state_dict(load_file(str(model)), strict=True)
        net.eval()
        for item in baseline['components']:
            lease.check()
            row = rows[item['sha256']]
            source = Path(row['absolutePath'])
            assert digest(source) == item['sha256']
            image = cv2.imread(str(source))
            a, b, c, d = item['selectedTile']['rect']
            tile = np.full((384, 384, 3), 114, np.uint8)
            patch = image[b:d, a:c]
            tile[:patch.shape[0], :patch.shape[1]] = patch
            with torch.inference_mode():
                pred = net(torch.from_numpy(tile.transpose(2, 0, 1).copy()).float()[None])[0]
            x, y, ex, ey = item['box']
            objects = torch.tensor([[x-a, y-b, ex-a, ey-b]], dtype=torch.float32)
            protected = row['annotations'] + [z for z in curated[item['sha256']]['annotations'] if z.get('reviewStatus') == 'engineering_review' and z.get('sourceId') not in item['overriddenPseudoSourceIds']]
            protected = torch.tensor([[z['box'][0]-a-16, z['box'][1]-b-16, z['box'][2]-a+16, z['box'][3]-b+16] for z in protected], dtype=torch.float32).reshape(-1, 4)
            mask = reviewed_object_negative_mask(pred[:, :4], objects, protected)[:, 0]
            scores = pred[:, 4] * pred[:, 5]
            result.append(dict(sha256=item['sha256'], sourceAnnotationId=item['sourceAnnotationId'], fixedTile=item['selectedTile']['rect'], matchingAnchors=int(mask.sum()), aboveThresholdAnchors=int((mask & (scores >= .30)).sum()), maxConfidence=float(scores[mask].max()) if mask.any() else None, step0=item['selectedTile'], interpretation='raw matched TRAIN anchors, not unique product false detections or held-out success'))
        report = dict(model=args.model, modelSHA256=digest(model), baselineProbeSHA256=digest(OUT/'source-negative-repair-probe.json'), fixedThreshold=.30, trainOnly=True, rows=result, resource=lease.receipt())
    (OUT / ('source-negative-repair-replay-' + args.model + '.json')).write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in report.items() if k != 'resource'}), flush=True)


if __name__ == '__main__':
    main()
