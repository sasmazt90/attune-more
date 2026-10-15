import json
from pathlib import Path

p = Path(r'C:\Users\PC\Desktop\AI Workspace\TOGG\research\acne-input-audit-20261015\source-audit-manifest.json')
d = json.load(open(p, encoding='utf-8'))

in_scope_annotations = []
for photo in d['validationScoredPositive']:
    sha = photo['sha256']
    capturable = photo.get('capturable', False)
    q_status = photo.get('quality', {}).get('status', 'UNKNOWN')
    angle = photo.get('productAngle', 'UNKNOWN')
    for ann in photo.get('annotations', []):
        if ann.get('isProductPoseInScope', False):
            box = ann['box']
            bw = box[2] - box[0]
            bh = box[3] - box[1]
            dim = max(bw, bh)
            in_scope_annotations.append({
                'photoSha': sha[:8],
                'photoAngle': angle,
                'capturable': capturable,
                'qualityStatus': q_status,
                'annIndex': ann['annotationIndex'],
                'box': box,
                'dim': round(dim, 1),
                'measurabilityReason': ann.get('measurabilityReason')
            })

print(f"Total In-Scope Annotations: {len(in_scope_annotations)}")
capturable_anns = [a for a in in_scope_annotations if a['capturable']]
uncapturable_anns = [a for a in in_scope_annotations if not a['capturable']]
print(f"  Capturable (Optimal) Photo Targets: {len(capturable_anns)}")
print(f"  Uncapturable (Blurry/Non-optimal) Photo Targets: {len(uncapturable_anns)}")

# Group by photo
by_photo = {}
for a in in_scope_annotations:
    k = (a['photoSha'], a['photoAngle'], a['capturable'], a['qualityStatus'])
    by_photo.setdefault(k, []).append(a)

print("\n--- Breakdown by Positive Photo ---")
for (sha, angle, cap, q_stat), anns in by_photo.items():
    dims = [a['dim'] for a in anns]
    tiny = sum(1 for d in dims if d < 8)
    small = sum(1 for d in dims if 8 <= d < 16)
    med = sum(1 for d in dims if d >= 16)
    print(f"Photo {sha} ({angle}, capturable={cap}, {q_stat}): {len(anns)} targets (tiny={tiny}, small={small}, med={med}, dims={dims})")
