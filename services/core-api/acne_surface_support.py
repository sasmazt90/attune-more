"""Acne-only analysis support: closed safe cells of the five acne region meshes.

The exported region meshes (apps/vehicle-app/src/utils/skinMesh.ts) draw a cell
diagonal only in alternating cells. appearance_analysis.polygon_mask fills a
triangle only when all three of its edges exist, so every quad cell whose
drawing diagonal is absent stays empty in the classical acne support although
it is a closed skin cell inside the region graph.

This reuses the existing dry/sag closed_surface_mask unchanged: a cell is added
only when it is a convex quadrilateral bounded by four exported (frontend
safe-filtered) edges whose two diagonals are both absent. No convex hull, open
edge, concave shortcut, unsupported point or other-side region is filled.
Eye/lip/nostril/brow holes, ocular margin, hair, glare and gray exclusions are
applied afterwards by the caller exactly as before. The displayed mesh, the
other criteria (they keep their own polygon_mask / closed_surface_mask inputs),
the trained-detector envelopes and region ownership rules are unchanged.
"""
import numpy as np

from appearance_analysis import closed_surface_mask

VERSION = 'acne-closed-cell-support-v1'
ACNE_REGIONS = ('forehead', 'rightCheek', 'leftCheek', 'nose', 'chin')


def acne_region_masks(shape, meshes, scale, origin=(0, 0)):
    """Closed-cell masks for the exported acne regions only (analysis space)."""
    return {k: closed_surface_mask(shape, meshes[k], scale, origin) for k in ACNE_REGIONS if k in meshes}


def acne_support_masks(masks, shape, meshes, scale, origin=(0, 0)):
    """Copy of an existing {region: polygon_mask} dict with ONLY the five acne
    regions replaced by their closed-cell masks. Inputs are not mutated."""
    out = {k: np.array(v, copy=True) for k, v in masks.items()}
    out.update(acne_region_masks(shape, meshes, scale, origin))
    return out
