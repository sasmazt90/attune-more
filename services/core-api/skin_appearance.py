"""Görünüm skoru (appearance score) of red-appearance findings: affected area x colour intensity, fixed 0-100 scale.

Contract `appearance-v1` (the same formula lives in apps/vehicle-app/src/utils/skinAppearance.ts; parity is tested):

  Input per region (one photo per region, MEASURE_POSE: FRONT forehead/nose/chin, LEFT right cheek, RIGHT left cheek),
  measured on the light-corrected image (skin_findings_det.light_redness, research light model):
    usablePx   usable skin pixels of the region polygon (hair, eyes, lips, specular and unusable pixels excluded)
    affectedPx pixels of those whose a* > am + 4, am = median a* of the usable skin of the whole face (reference skin)
                -> a real pixel mask, never a detection box
    intensity  mean (a* - am) over the affected pixels, CIE Lab a* units (0 when no pixel is affected)
  Pooled over several regions (a page, the whole face): area = sum(affectedPx) / sum(usablePx),
    intensity = sum(affectedPx * intensity) / sum(affectedPx). Regional percentages are never added up; each anatomical
    region comes from one photo only, so it is never counted twice.
  Score:
    A = min(1, area / AREA_FULL)          AREA_FULL = 0.50   (half of the usable region skin affected)
    I = min(1, intensity / INTENSITY_FULL) INTENSITY_FULL = 16 a* units above the reference skin
    score = round(100 * sqrt(A * I))      0 when nothing is affected; never decreases when area or intensity grows
  The constants are fixed (not rescaled per photo, the first scan is not set to 100). They are engineering choices
  for a readable scale, NOT validated against clinical severity; the score is not a detection probability, not the
  affected-area percentage and not a disease severity.
Missing input -> no score (callers carry `unavailable` with a reason)."""
import math

VERSION = 'appearance-v1'
AREA_FULL = 0.50
INTENSITY_FULL = 16.0
THRESHOLD_A = 4.0          # a* above the face median that marks a pixel as affected (research redness_feats.py)
FINDINGS = ('redness', 'rosacea', 'eczema')
NO_MASK = {'melasma': 'AFFECTED_MASK_NOT_AVAILABLE', 'acneMarks': 'AFFECTED_MASK_NOT_AVAILABLE'}


def score(area: float, intensity: float) -> int:
    a = min(1.0, max(0.0, area) / AREA_FULL)
    i = min(1.0, max(0.0, intensity) / INTENSITY_FULL)
    return int(round(100 * math.sqrt(a * i)))


def region(usable_px: int, affected_px: int, intensity: float) -> dict | None:
    """One region's raw values + score; None without usable pixels (no score is invented)."""
    if not usable_px or usable_px <= 0 or affected_px is None or affected_px < 0 or affected_px > usable_px:
        return None
    area = affected_px / usable_px
    inten = float(intensity) if affected_px else 0.0
    return dict(version=VERSION, usablePx=int(usable_px), affectedPx=int(affected_px), areaPct=round(100 * area, 2),
                intensity=round(inten, 2), score=score(area, inten))


def pool(regions: list) -> dict | None:
    """Pooled over regions (pixel sums, never summed percentages). None when any input is missing."""
    if not regions or any(r is None for r in regions):
        return None
    usable = sum(r['usablePx'] for r in regions); affected = sum(r['affectedPx'] for r in regions)
    if usable <= 0:
        return None
    inten = sum(r['affectedPx'] * r['intensity'] for r in regions) / affected if affected else 0.0
    area = affected / usable
    return dict(version=VERSION, usablePx=usable, affectedPx=affected, areaPct=round(100 * area, 2),
                intensity=round(inten, 2), score=score(area, inten))
