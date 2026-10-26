"""Fits the vehicle camera colour profile from photos of the printed Attune chart taken with the cabin camera.

usage: python scripts/camera-calibration/fit_profile.py --profile-id ID --yuv-matrix bt601|bt709|bt2020 --yuv-full-range 0|1
                                                         [--reference measured.json] --out profile.json PHOTO [PHOTO ...]
PHOTO: PNG/JPEG frames exported from the cabin camera after YUV->RGB with the same matrix/range as given here
(or frames of the app's raw path). The YUV fields describe the camera (datasheet / ISP configuration).
Writes the profile only when every quality gate passes; always prints the report. Use the profile with
ATTUNE_CAMERA_PROFILE=/path/profile.json for core-api.
"""
import argparse, hashlib, json, sys
from pathlib import Path
import cv2
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/core-api'))
import camera_calibration as C

a = argparse.ArgumentParser()
a.add_argument('--profile-id', required=True); a.add_argument('--yuv-matrix', choices=['bt601', 'bt709', 'bt2020'], required=True)
a.add_argument('--yuv-full-range', type=int, choices=[0, 1], required=True); a.add_argument('--reference'); a.add_argument('--out', required=True)
a.add_argument('photos', nargs='+'); args = a.parse_args()
reference, kind = C.NOMINAL, 'nominal-colorchecker-srgb'
if args.reference:
    reference = json.load(open(args.reference)); kind = 'measured:' + hashlib.sha256(open(args.reference, 'rb').read()).hexdigest()[:16]
    assert len(reference) == 24 and all(len(r) == 3 for r in reference), 'reference: 24 sRGB triplets in chart order'
meas, sources = [], []
for p in args.photos:
    img = cv2.imread(p, cv2.IMREAD_COLOR); assert img is not None, p
    meas.append(C.measure_chart(img)); sources.append(hashlib.sha256(open(p, 'rb').read()).hexdigest())
profile, report = C.fit_profile(meas, args.profile_id, yuv={'matrix': args.yuv_matrix, 'fullRange': bool(args.yuv_full_range)},
                                reference=reference, reference_kind=kind, sources=sources)
print(json.dumps(report, indent=1, ensure_ascii=False))
if profile is None:
    sys.exit(2)
print('profile', args.out, 'sha256', C.write_profile(profile, args.out))
