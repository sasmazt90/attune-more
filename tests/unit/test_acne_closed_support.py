"""Focused synthetic contracts for the acne-only closed-cell support.
Synthetic geometry is not evidence of detection performance."""
import ast, hashlib, json, sys
from pathlib import Path
import numpy as np, pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts/skin-research'), str(ROOT / 'services/core-api')]
from appearance_analysis import polygon_mask, closed_surface_mask
import acne_surface_support as support
import compare_acne_closed_support as compare
import audit_acne_measurement_scope as audit


def mesh(points, edges):
    return dict(points=[dict(x=float(x), y=float(y)) for x, y in points], edges=[list(e) for e in edges])


SQUARE = [(10, 10), (30, 10), (30, 30), (10, 30)]


def test_closed_cell_without_drawn_diagonal_is_filled():
    m = mesh(SQUARE, [(0, 1), (1, 2), (2, 3), (3, 0)])  # closed cell, no diagonal drawn
    assert not polygon_mask((40, 40), m, 1).any()       # old triangle-union leaves it empty
    new = support.acne_region_masks((40, 40), dict(chin=m), 1)['chin']
    assert new[20, 20] and new[12, 28] and not new[5, 5] and not new[35, 35]


def test_open_concave_and_triangulated_cells_are_not_newly_filled():
    open_cell = mesh(SQUARE, [(0, 1), (1, 2), (2, 3)])  # one edge missing: open
    assert not support.acne_region_masks((40, 40), dict(nose=open_cell), 1)['nose'].any()
    concave = mesh([(10, 10), (30, 10), (14, 14), (10, 30)], [(0, 1), (1, 2), (2, 3), (3, 0)])  # arrow-head quad
    assert not support.acne_region_masks((40, 40), dict(nose=concave), 1)['nose'].any()
    tri = mesh(SQUARE, [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])  # already triangulated: unchanged
    assert np.array_equal(support.acne_region_masks((40, 40), dict(chin=tri), 1)['chin'], polygon_mask((40, 40), tri, 1))


def test_origin_and_scale_follow_the_polygon_contract():
    m = mesh([(110, 210), (150, 210), (150, 250), (110, 250)], [(0, 1), (1, 2), (2, 3), (3, 0)])
    origin, scale = (100, 200), .5
    new = support.acne_region_masks((40, 40), dict(forehead=m), scale, origin)['forehead']
    u, v = audit.source_to_analysis(130, 230, origin, scale)
    assert new[int(v), int(u)] and not new[1, 1] and not new[30, 30]
    assert audit.analysis_to_source(u, v, origin, scale) == (130, 230)


def test_only_acne_regions_replaced_inputs_untouched_and_old_pixels_kept():
    cell = mesh(SQUARE, [(0, 1), (1, 2), (2, 3), (3, 0)])
    meshes = dict(chin=cell, periorbital=cell)
    old = {k: polygon_mask((40, 40), v, 1) for k, v in meshes.items()}; before = {k: v.copy() for k, v in old.items()}
    new = support.acne_support_masks(old, (40, 40), meshes, 1)
    assert all(np.array_equal(old[k], before[k]) for k in old)          # no mutation
    assert np.array_equal(new['periorbital'], old['periorbital'])        # non-acne region unchanged
    assert new['chin'].sum() > old['chin'].sum() and not (old['chin'] & ~new['chin']).any()


def test_exclusions_hair_glare_gray_and_skin_scope_still_apply():
    cell = mesh(SQUARE, [(0, 1), (1, 2), (2, 3), (3, 0)]); shape = (40, 40)
    masks = support.acne_support_masks({'chin': polygon_mask(shape, cell, 1)}, shape, {'chin': cell}, 1)
    exclusion = np.zeros(shape, np.uint8); exclusion[18:22, 18:22] = 255
    hair = np.zeros(shape, bool); hair[12, 12] = True
    clipping = np.zeros(shape, bool); clipping[25, 25] = True
    gray = np.full(shape, .5, np.float32); gray[27, 15] = .05
    acne_skin = np.ones(shape, bool); acne_skin[14, 26] = False
    ctx = dict(exclusion=exclusion, hair=hair, clipping=clipping, gray=gray, acne_skin=acne_skin)
    _, regions, eligible = compare.scoped(ctx, masks)
    assert eligible[15, 15] and not eligible[20, 20] and not eligible[12, 12] and not eligible[25, 25]
    assert not eligible[27, 15] and not eligible[14, 26] and not eligible[5, 5] and set(regions) == {'chin'}


def test_candidate_list_count_and_fill_are_one_list():
    from acne_lab_dog import candidate_result
    a = dict(x=2, y=2, width=3, height=3, areaPixels=9, pixels=np.array([[x, y] for x in range(2, 5) for y in range(2, 5)]))
    b = dict(x=10, y=10, width=2, height=2, areaPixels=4, pixels=np.array([[x, y] for x in range(10, 12) for y in range(10, 12)]))
    result, mask = candidate_result([a, b], (20, 20), (100, 50), .5)
    assert result['candidateCount'] == len(result['candidates']) == 2 and mask.sum() == result['activePixels'] == 13
    assert result['candidates'][0]['x'] == 104 and result['candidates'][0]['areaPixels'] == 36  # origin/scale applied once
    assert compare.boxes(result['candidates'])[1] == [120.0, 70.0, 124.0, 74.0]


def test_other_criteria_and_frozen_geometry_code_unchanged():
    source = (ROOT / 'services/core-api/appearance_analysis.py').read_text('utf8'); tree = ast.parse(source)
    digest = {n.name: hashlib.sha256(ast.get_source_segment(source, n).encode()).hexdigest() for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert digest['analyze_skin'] == 'b022202377cd0adb2ffa1335cab3221065c5eeb15ebe3b981f61d6a1adf96813'
    assert digest['polygon_mask'] == '33dc75fc9d22dfb2fcd325b4faf5cea3b410e6e5e5f7e895a66fe58630c2a477'
    assert digest['closed_surface_mask'] == 'a3d5bc24ceca5f78b0a9bdd333216547e777b3f510b6d387f0a04145316ddb1c'
    assert digest['acne_candidates'] == audit.A_FUNCTION_SHA256


def test_old_records_keep_their_interpretation():
    evidence = json.loads((ROOT / 'docs/acne-measurement-audit-evidence-20261015.json').read_text('utf8'))
    assert evidence['codeIdentities']['scripts/skin-research/audit_acne_measurement_scope.py']['normalizedSHA256'] == \
        audit.normalized_text_sha(ROOT / 'scripts/skin-research/audit_acne_measurement_scope.py')
    ctx = dict(masks=dict(chin=np.eye(4, dtype=bool)))
    assert compare.support(ctx, 'old')['chin'] is ctx['masks']['chin']  # OLD path is the frozen triangle-union
    assert evidence['productionAcneAtInputRoot'] == dict(accepted=False, file=None)
