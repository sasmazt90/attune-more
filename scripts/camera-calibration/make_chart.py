"""Writes the printable Attune camera calibration chart (A4 landscape, 300 dpi): PNG + PDF.

usage: python scripts/camera-calibration/make_chart.py OUT_DIR
Print at 100 % (no "fit to page"), matte paper. Nominal patch colours = ColorChecker Classic sRGB values; for production
calibration measure the printed patches (spectrophotometer) and pass them to fit_profile.py --reference.
"""
import sys
from pathlib import Path
import cv2
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/core-api'))
import camera_calibration as C

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
img = C.render_chart()
cv2.imwrite(str(out / 'attune-camera-chart-v1.png'), img)
from PIL import Image
Image.fromarray(img[..., ::-1]).save(out / 'attune-camera-chart-v1.pdf', resolution=300)
print(out / 'attune-camera-chart-v1.png'); print(out / 'attune-camera-chart-v1.pdf')
