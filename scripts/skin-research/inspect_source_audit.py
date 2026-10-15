#!/usr/bin/env python3
"""Inspect existing source audit manifest in research directory."""

import json
from pathlib import Path

p = Path(r'C:\Users\PC\Desktop\AI Workspace\TOGG\research\acne-input-audit-20261015\source-audit-manifest.json')
d = json.load(open(p, encoding='utf-8'))

print("=== VALIDATION SCORED POSITIVE (9 PHOTOS) ===")
pos_in_scope = 0
for r in d['validationScoredPositive']:
    q = r.get('quality', {})
    a = r.get('alignment', {})
    in_sc = r.get('inScopeTruthCount', 0)
    pos_in_scope += in_sc
    print(f"{r['sha256'][:8]}: angle={r.get('productAngle')}, capturable={r.get('capturable')}, q_status={q.get('status')}, q_valid={q.get('isValid')}, blur={q.get('blurScore')}, lum={q.get('avgLuminance')}, yaw={a.get('yaw')}, pitch={a.get('pitch')}, roll={a.get('roll')}, inScopeTruth={in_sc}")

print(f"Total positive in-scope truth: {pos_in_scope}")

print("\n=== VALIDATION NEGATIVE (15 PHOTOS) ===")
for r in d['validationNegative']:
    q = r.get('quality', {})
    a = r.get('alignment', {})
    print(f"{r['sha256'][:8]}: capturable={r.get('capturable')}, q_status={q.get('status')}, q_valid={q.get('isValid')}, blur={q.get('blurScore')}, lum={q.get('avgLuminance')}")
