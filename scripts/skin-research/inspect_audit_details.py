import json
from pathlib import Path

report_path = Path("audit-results/acne-input-audit-20261015/acne-dual-scope-audit-report.json")
with open(report_path, "r", encoding="utf-8") as f:
    data = json.load(f)

print("=" * 80)
print("AUDIT PREFLIGHT MANIFEST BREAKDOWN")
print("=" * 80)

pos_accepted = []
pos_rejected = []
neg_accepted = []
neg_rejected = []

for item in data["preflightManifest"]:
    sha = item["sha256"][:8]
    is_neg = item["isNegative"]
    acc = item["accepted"]
    reasons = item.get("rejectionReasons", [])
    truth = item.get("inScopeTruth", 0)
    angle = item.get("productAngle", "N/A")
    eyewear = item.get("eyewear", {})
    quality = item.get("quality", {})
    pose = item.get("pose", {})

    if not is_neg:
        if acc:
            pos_accepted.append((sha, angle, truth, quality.get("blurScore"), quality.get("avgLuminance")))
        else:
            pos_rejected.append((sha, angle, truth, reasons, quality.get("blurScore")))
    else:
        if acc:
            neg_accepted.append(sha)
        else:
            neg_rejected.append((sha, reasons, eyewear.get("status"), eyewear.get("probability")))

print(f"\n[Positive Photos Accepted into Scope B: {len(pos_accepted)} photos, sum truth: {sum(x[2] for x in pos_accepted)}]")
for sha, angle, truth, blur, lum in pos_accepted:
    print(f"  + SHA: {sha} | Angle: {angle:5s} | Truth: {truth:2d} targets | blur: {blur:.2f} | lum: {lum:.1f}")

print(f"\n[Positive Photos Rejected from Scope B: {len(pos_rejected)} photos, sum truth: {sum(x[2] for x in pos_rejected)}]")
for sha, angle, truth, reasons, blur in pos_rejected:
    blur_str = f"{blur:.2f}" if blur is not None else "N/A"
    angle_str = str(angle) if angle is not None else "None"
    truth_val = truth if truth is not None else 0
    print(f"  - SHA: {sha} | Angle: {angle_str:5s} | Truth: {truth_val:2d} targets | blur: {blur_str} | Reasons: {reasons}")

print(f"\n[Negative Photos Accepted into Scope B: {len(neg_accepted)} photos]")
print(f"  SHAs: {neg_accepted}")

print(f"\n[Negative Photos Rejected from Scope B: {len(neg_rejected)} photos]")
for sha, reasons, ew_stat, ew_prob in neg_rejected:
    print(f"  - SHA: {sha} | Eyewear: {ew_stat} (p={ew_prob}) | Reasons: {reasons}")

print("\n" + "=" * 80)
print("MODEL COMPARISON METRICS SUMMARY (SCOPE A vs SCOPE B)")
print("=" * 80)

for m in data["modelsComparison"]:
    sa = m["scopeA_Canonical"]
    sb = m["scopeB_ProductPreflight"]
    sbf = m["scopeB_FrontOnly"]
    name = m["modelName"]
    sha = m["modelSha256"][:16]
    ep = m["epoch"]
    st = m["globalStep"]

    print(f"\nModel: {name} (Epoch {ep}, Step {st}, SHA: {sha}...)")
    print(f"  Scope A (43 items, 53 truth, 15 neg):")
    print(f"    Recall: {sa['inScopeTp50']}/{sa['inScopeTruth']} ({sa['rec50']:.1%})")
    print(f"    FP on Negatives: {sa['negTotalFp']} total ({sa['fpPerPhoto']:.2f}/photo), {sa['negPhotosWithFp']}/{sa['negativePhotos']} photos with FP")
    print(f"    Sizes: <8px: {sa['sizeBreakdown']['tiny_less_8px']['tp50']}/{sa['sizeBreakdown']['tiny_less_8px']['total']} | 8-16px: {sa['sizeBreakdown']['small_8_to_16px']['tp50']}/{sa['sizeBreakdown']['small_8_to_16px']['total']} | 16-32px: {sa['sizeBreakdown']['medium_16_to_32px']['tp50']}/{sa['sizeBreakdown']['medium_16_to_32px']['total']}")

    print(f"  Scope B (12 items, 14 truth, 9 neg):")
    print(f"    Recall: {sb['inScopeTp50']}/{sb['inScopeTruth']} ({sb['rec50']:.1%})")
    print(f"    FP on Negatives: {sb['negTotalFp']} total ({sb['fpPerPhoto']:.2f}/photo), {sb['negPhotosWithFp']}/{sb['negativePhotos']} photos with FP")
    print(f"    Sizes: <8px: {sb['sizeBreakdown']['tiny_less_8px']['tp50']}/{sb['sizeBreakdown']['tiny_less_8px']['total']} | 8-16px: {sb['sizeBreakdown']['small_8_to_16px']['tp50']}/{sb['sizeBreakdown']['small_8_to_16px']['total']} | 16-32px: {sb['sizeBreakdown']['medium_16_to_32px']['tp50']}/{sb['sizeBreakdown']['medium_16_to_32px']['total']}")

    print(f"  Scope B Front-Only ({len(sbf)} items evaluated, {sbf['inScopeTruth']} truth):")
    print(f"    Recall: {sbf['inScopeTp50']}/{sbf['inScopeTruth']} ({sbf['rec50']:.1%}) | FP: {sbf['negTotalFp']}")

print("\n" + "=" * 80)
print("PER-TARGET COMPARISON: STEP 0 vs EPOCH 4")
print("=" * 80)

step0_targets = { (t['imageSha256'][:8], t['targetIndex']): t for t in data["modelsComparison"][0]["scopeA_Canonical"]["targetDetails"] }
ep4_targets = { (t['imageSha256'][:8], t['targetIndex']): t for t in data["modelsComparison"][4]["scopeA_Canonical"]["targetDetails"] }

print("Targets detected by Step 0:")
for k, t in step0_targets.items():
    if t['detected']:
        ep4_det = ep4_targets[k]['detected']
        print(f"  SHA: {k[0]} idx {k[1]:2d} | dim: {t['dim']:4.1f}px ({t['sizeGroup']:15s}) | Step0: YES | Ep4: {'YES' if ep4_det else 'NO (LOST)'}")

print("\nTargets detected by Epoch 4 but NOT Step 0:")
for k, t in ep4_targets.items():
    if t['detected'] and not step0_targets[k]['detected']:
        print(f"  SHA: {k[0]} idx {k[1]:2d} | dim: {t['dim']:4.1f}px ({t['sizeGroup']:15s}) | Step0: NO  | Ep4: YES (GAINED)")

