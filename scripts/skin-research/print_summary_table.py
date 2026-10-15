import sys, json
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

d = json.load(open('audit-results/acne-input-audit-20261015/acne-stage-failure-audit.json', encoding='utf-8'))
print("Idx | Photo | Ann | Dim(px) | Step 0 Stage (IoU / Score)           | Epoch 4 Stage (IoU / Score)")
print("-" * 95)
for t in d['targetFailureTable']:
    idx = t['targetIndex']
    sha = t['imageSha8']
    ann = t['annotationIndex']
    dim = t['dim']
    s0 = t['step0Fate']
    ep = t['epoch4Fate']
    s0_tc = s0.get('trackedCandidate') or {}
    ep_tc = ep.get('trackedCandidate') or {}
    s0_str = f"{s0['failureStage']} ({s0_tc.get('iou', 0.0):.2f}/{s0_tc.get('score', 0.0):.3f})"
    ep_str = f"{ep['failureStage']} ({ep_tc.get('iou', 0.0):.2f}/{ep_tc.get('score', 0.0):.3f})"
    print(f"T{idx:02d} | {sha} | #{ann:2d} | {dim:5.1f}px | {s0_str:37s} | {ep_str:37s}")
