import sys
import json
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

p = Path("audit-results/acne-input-audit-20261015/acne-stage-failure-audit.json")
with open(p, "r", encoding="utf-8") as f:
    d = json.load(f)

print("=" * 90)
print("14 PRODUCT-GATED TARGETS: STAGE-BY-STAGE FAILURE AUDIT")
print("=" * 90)

for t in d["targetFailureTable"][:7]:
    idx = t["targetIndex"]
    sha = t["imageSha8"]
    dim = t["dim"]
    bx = t["targetBox"]
    s0 = t["step0Fate"]
    ep = t["epoch4Fate"]
    s0_tc = s0.get("trackedCandidate") or {}
    ep_tc = ep.get("trackedCandidate") or {}

    s0_iou = s0_tc.get("iou", 0.0)
    s0_score = s0_tc.get("score", 0.0)
    s0_obj = s0_tc.get("objectness", 0.0)
    s0_cls = s0_tc.get("classScore", 0.0)

    ep_iou = ep_tc.get("iou", 0.0)
    ep_score = ep_tc.get("score", 0.0)
    ep_obj = ep_tc.get("objectness", 0.0)
    ep_cls = ep_tc.get("classScore", 0.0)

    print(f"\nTarget {idx:02d} [{sha}] | Dim: {dim:4.1f}px | Box: {bx}")
    print(f"  Step 0: {s0['failureStage']:26s} | IoU: {s0_iou:.3f} | Score: {s0_score:.4f} [Obj: {s0_obj:.3f}, Cls: {s0_cls:.3f}]")
    print(f"          Reason: {s0['explanation']}")
    print(f"  Ep 4:   {ep['failureStage']:26s} | IoU: {ep_iou:.3f} | Score: {ep_score:.4f} [Obj: {ep_obj:.3f}, Cls: {ep_cls:.3f}]")
    print(f"          Reason: {ep['explanation']}")

print("\n" + "=" * 90)
print("FALSE POSITIVES AUDIT (STEP 0 vs EPOCH 4)")
print("=" * 90)
print(f"\nStep 0 False Positives ({len(d['step0FalsePositives'])} total):")
for i, fp in enumerate(d["step0FalsePositives"]):
    print(f"  FP {i+1}: Photo {fp['imageSha8']} | Region: {fp['region']} | Score: {fp['confidence']:.4f} | Box: {fp['box']}")

print(f"\nEpoch 4 False Positives ({len(d['epoch4FalsePositives'])} total):")
for fp in d["epoch4FalsePositives"]:
    print(f"  FP {fp['fpIndex']:02d}: Photo {fp['imageSha8']} | Region: {fp['region']} | Score: {fp['confidence']:.4f} | Box: {fp['box']}")
    print(f"        Nature: {fp['fpNature']} | Step 0 Present: {fp['presentInStep0']}")
    print(f"        Desc:   {fp['fpDescription']}")

print("\n" + "=" * 90)
print("VISUAL TARGETS AUDIT SUMMARY")
print("=" * 90)
for vt in d["visualTargetsAudit"]:
    print(f"Target {vt['targetIndex']:02d} [{vt['imageSha8']}] | Dim: {vt['dim']:4.1f}px | Nature: {vt['visualNature']:18s} | Crop: {vt['cropFileName']}")
    print(f"  Desc: {vt['visualDescription']}")
