"""Comprehensive regression tests for all blockers, Scenarios A-E, 3-angle fusion, widened pose gates, and local-only cost rules."""
from pathlib import Path
import copy, json, subprocess, sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
import local_skin_type as T
from skin_display_geometry import measured_line_paths
import roboflow_skin_models as RF

NEG_METHODS = {'appearance-cv-6', 'appearance-native-dry-2', 'appearance-native-dry-3'}


def _rows(oil=0.0, dry=0.0, redness=5.0, pose='FRONT', photo_id='photo-front'):
    area = dict(sourcePixels=250, analysisPixels=250, foreheadSourcePixels=120, noseSourcePixels=130)
    return [
        dict(id='oil', value=oil, quality='valid', methodVersion='appearance-cv-6', evaluatedArea=area, capturePose=pose, photoId=photo_id),
        dict(id='dry', value=dry, quality='valid', methodVersion='appearance-native-dry-3', evaluatedArea=area, capturePose=pose, photoId=photo_id),
        dict(id='redness', value=redness, quality='valid', methodVersion='appearance-cv-6', evaluatedArea=area, capturePose=pose, photoId=photo_id),
    ]


def _base(val='dry'):
    return dict(value=val, quality='valid', confidence=None, methodVersion='skin-type-local-vit-v1', modelHash='a' * 64, inferenceKind='local-onnx')


def test_blocker_1_and_2_regional_skin_type_rules_and_scenarios_a_to_e():
    # 1. Missing cheek -> value=None, quality='insufficient', limitationCode='INCOMPLETE_CHEEKS_UNVERIFIED'
    r_missing_cheek = dict(forehead=_rows(8, 0), nose=_rows(9, 0), chin=_rows(5, 0), leftCheek=_rows(0, 3.0))
    res_missing = T.regional_decision(_base('dry'), r_missing_cheek)
    assert res_missing['value'] is None
    assert res_missing['quality'] == 'insufficient'
    assert res_missing['limitationCode'] == 'INCOMPLETE_CHEEKS_UNVERIFIED'

    # 2. Scenario A & B: All regions oil=0, dry=0 without accepted negative-evidence method -> unevaluated, NEVER leaks base ('oily' or 'dry')
    r_zero = {k: _rows(0.0, 0.0) for k in T.REGIONS}
    res_a = T.regional_decision(_base('oily'), r_zero)
    assert res_a['value'] is None
    assert res_a['quality'] == 'insufficient'
    assert res_a['limitationCode'] == 'NEGATIVE_EVIDENCE_METHOD_NOT_ACCEPTED'
    assert res_a['displayValue'] == 'Değerlendirilmedi'
    assert all(res_a['decisionTrace']['regions'][k]['state'] == 'unevaluated' for k in T.REGIONS)

    res_b = T.regional_decision(_base('dry'), r_zero)
    assert res_b['value'] is None
    assert res_b['limitationCode'] == 'NEGATIVE_EVIDENCE_METHOD_NOT_ACCEPTED'

    # 3. Scenario E: With accepted negative-evidence methods, tiny 0.01% oil -> symmetric 'normal', NEVER combination
    r_noise = dict(forehead=_rows(0.01, 0), nose=_rows(0.01, 0), chin=_rows(0, 0), leftCheek=_rows(0, 0), rightCheek=_rows(0, 0))
    res_noise = T.regional_decision(_base('dry'), r_noise, accepted_negative_methods=NEG_METHODS)
    assert res_noise['value'] == 'normal'
    assert res_noise['decisionTrace']['tZone']['state'] == 'non-oily'

    # 4. Scenario C: Intermediate band (1.0 < v < 2.0) -> 'unknown' state and value=None ('INTERMEDIATE_BAND_UNDETERMINED')
    r_inter = dict(forehead=_rows(1.5, 0), nose=_rows(1.4, 0), chin=_rows(0, 3.0), leftCheek=_rows(0, 3.0), rightCheek=_rows(0, 3.0))
    res_inter = T.regional_decision(_base('normal'), r_inter)
    assert res_inter['value'] is None
    assert res_inter['quality'] == 'insufficient'
    assert res_inter['limitationCode'] == 'INTERMEDIATE_BAND_UNDETERMINED'
    assert res_inter['decisionTrace']['regions']['forehead']['state'] == 'unknown'

    # 5. Scenario D: Partial/mixed pattern (forehead oily, chin dry, others dry) -> value=None ('MIXED_REGIONAL_PATTERN_UNDETERMINED'), never leaks base
    r_mixed = dict(forehead=_rows(5.0, 0), nose=_rows(0, 3.0), chin=_rows(0, 5.0), leftCheek=_rows(0, 3.0), rightCheek=_rows(0, 3.0))
    res_mixed = T.regional_decision(_base('oily'), r_mixed)
    assert res_mixed['value'] is None
    assert res_mixed['quality'] == 'insufficient'
    assert res_mixed['limitationCode'] == 'MIXED_REGIONAL_PATTERN_UNDETERMINED'
    assert res_mixed['displayValue'] == 'Karışık desen (Belirlenemedi)'

    # 6. No sensitivity from redness: redness=95.0 never creates 'sensitive'
    r_red = {k: _rows(0.0, 4.0, redness=95.0) for k in T.REGIONS}
    res_red = T.regional_decision(_base('normal'), r_red)
    assert res_red['value'] == 'dry'
    assert all(res_red['decisionTrace']['regions'][k]['state'] == 'dry' for k in T.REGIONS)

    # 7. Combination with positive dry cheeks (no negative-evidence assumption needed):
    r_comb = dict(forehead=_rows(5.5, 0), nose=_rows(0, 3.0), chin=_rows(4.2, 0), leftCheek=_rows(0.01, 3.2), rightCheek=_rows(0.3, 3.5))
    res_comb = T.regional_decision(_base('dry'), r_comb)
    assert res_comb['value'] == 'combination'
    assert res_comb['decisionTrace']['thresholds']['status'] == 'uncalibrated-hypothesis'


def test_three_angle_fusion_changes_cheek_and_overall_decision():
    # FRONT has oily T-zone (forehead=6.0, nose=5.2, chin=3.1) and placeholder front cheeks
    front = dict(
        photoId='front-001',
        pose='FRONT',
        general=dict(skinType=_base('normal')),
        measurements=dict(
            forehead=_rows(6.0, 0.2, pose='FRONT', photo_id='front-001'),
            nose=_rows(5.2, 0.1, pose='FRONT', photo_id='front-001'),
            chin=_rows(3.1, 0.2, pose='FRONT', photo_id='front-001'),
            leftCheek=_rows(5.0, 0.1, pose='FRONT', photo_id='front-001'),
            rightCheek=_rows(5.0, 0.1, pose='FRONT', photo_id='front-001'),
        ),
    )
    # Case 1: LEFT (rightCheek) and RIGHT (leftCheek) are dry -> fused result is 'combination'
    left_dry = dict(
        photoId='left-dry-002',
        pose='LEFT',
        measurements=dict(rightCheek=_rows(0.2, 3.8, pose='LEFT', photo_id='left-dry-002')),
    )
    right_dry = dict(
        photoId='right-dry-003',
        pose='RIGHT',
        measurements=dict(leftCheek=_rows(0.1, 4.1, pose='RIGHT', photo_id='right-dry-003')),
    )
    fused_comb = T.fuse_multi_angle_skin(front, left_dry, right_dry)
    assert fused_comb['general']['skinType']['value'] == 'combination'
    rmap_comb = fused_comb['general']['regionalSkinMap']['regions']
    assert rmap_comb['forehead']['sourcePose'] == 'FRONT' and rmap_comb['forehead']['sourcePhotoId'] == 'front-001'
    assert rmap_comb['rightCheek']['sourcePose'] == 'LEFT' and rmap_comb['rightCheek']['sourcePhotoId'] == 'left-dry-002'
    assert rmap_comb['rightCheek']['state'] == 'dry'
    assert rmap_comb['leftCheek']['sourcePose'] == 'RIGHT' and rmap_comb['leftCheek']['sourcePhotoId'] == 'right-dry-003'
    assert rmap_comb['leftCheek']['state'] == 'dry'

    # Case 2: Holding FRONT constant, change LEFT and RIGHT to oily cheeks -> fused result changes to 'oily'!
    left_oily = dict(
        photoId='left-oily-004',
        pose='LEFT',
        measurements=dict(rightCheek=_rows(5.8, 0.1, pose='LEFT', photo_id='left-oily-004')),
    )
    right_oily = dict(
        photoId='right-oily-005',
        pose='RIGHT',
        measurements=dict(leftCheek=_rows(6.4, 0.2, pose='RIGHT', photo_id='right-oily-005')),
    )
    fused_oily = T.fuse_multi_angle_skin(front, left_oily, right_oily)
    assert fused_oily['general']['skinType']['value'] == 'oily'
    rmap_oily = fused_oily['general']['regionalSkinMap']['regions']
    assert rmap_oily['rightCheek']['state'] == 'oily' and rmap_oily['rightCheek']['sourcePhotoId'] == 'left-oily-004'
    assert rmap_oily['leftCheek']['state'] == 'oily' and rmap_oily['leftCheek']['sourcePhotoId'] == 'right-oily-005'


def test_blocker_5_skeletonized_wrinkle_line_paths_and_isolated_roboflow_gate(monkeypatch):
    assert set(RF.APPROVED_LESION_THRESHOLDS.keys()) == {'papule', 'pustule', 'open_comedo', 'closed_comedo'}
    assert RF.REGIONAL_SEG_DECLARED_CLASSES == ('Oily', 'Redness')
    # Even if ROBOFLOW_API_KEY is present, hosted research is disabled unless ATTUNE_EXPERIMENTAL_HOSTED_SKIN_RESEARCH=1 and consent+opt_in are True
    monkeypatch.setenv('ROBOFLOW_API_KEY', 'dummy-key-never-called')
    monkeypatch.delenv('ATTUNE_EXPERIMENTAL_HOSTED_SKIN_RESEARCH', raising=False)
    assert RF.research_flag_enabled({'experimentalHostedSkinResearch': True, 'hostedResearchModelConsent': True}) is False
    res = RF.infer_lesion_large(np.zeros((32, 32, 3), np.uint8), hosted_research_consent=True)
    assert res['valid'] is False
    assert res['reason'] == 'HOSTED_RESEARCH_FLAG_DISABLED'

    ridge = np.zeros((60, 60), np.float32)
    roi = np.ones((60, 60), bool)
    for x in range(10, 48):
        y = int(20 + 0.25 * (x - 10))
        ridge[y, x] = 0.08
    paths = measured_line_paths(ridge, roi, 0.0125)
    assert len(paths) >= 1
    assert paths[0]['source'] == 'skeletonized-highpass-ridge-v1'
    assert len(paths[0]['points']) >= 2


def test_frontend_blockers_3_4_5_three_angle_fusion_and_localization():
    script = r'''
const fs = require('fs'), ts = require('typescript'), Module = require('module'), assert = require('assert/strict');
const React = require('react'), { renderToStaticMarkup } = require('react-dom/server');
require('./tests/unit/ts_loader.js');

function loadTsx(path, source, stubs = {}) {
  const m = new Module(path, module);
  m.paths = module.paths;
  m.require = id => id in stubs ? stubs[id] : require(id);
  m._compile(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true } }).outputText, path);
  return m.exports;
}

const prefix = 'apps/vehicle-app/src/';
const surface = require('./' + prefix + 'utils/skinSurfaceAnalysis.ts');
const indicatorsMod = require('./' + prefix + 'utils/skinIndicators.ts');
const demoMod = require('./' + prefix + 'data/skinDemoFixture.ts');
const { SkinAnalyzer, detectCameraMirrored } = require('./' + prefix + 'utils/skinAnalyzer.ts');
const { fuseMultiAngleSkinOverview } = require('./' + prefix + 'utils/skinMultiAngle.ts');

// 1. detectCameraMirrored measures actual mirror state instead of hardcoding false:
assert.equal(detectCameraMirrored(null, null, [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]), false);
assert.equal(detectCameraMirrored(null, null, [-1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]), true);
assert.equal(detectCameraMirrored(null, { getTransform: () => ({ a: -1 }) }, null), true);

// 2. Redness labels are distinct between whole-face and regional scopes:
assert.equal(indicatorsMod.skinCriterionLabel('redness', 'whole-face'), 'Genel kızarıklık indeksi');
assert.equal(indicatorsMod.skinCriterionLabel('redness', 'regional'), 'Bölgesel kızarıklık farkı');
assert.equal(demoMod.SKIN_REGIONS.nose.nameTr, 'T Bölgesi');

// 3. Landmark-scaled exclusionBoxes and exclusionPolygons cover eyes, lips, brows, nostrils:
const lms = Array.from({ length: 468 }, (_, i) => ({ x: 0.25 + (i % 20) * 0.025, y: 0.2 + Math.floor(i / 20) * 0.025, z: 0 }));
const geom = SkinAnalyzer.regionGeometry(640, 480, { faceDetected: true, isMediaPipeActive: true, yaw: 0, pitch: 0, roll: 0, scaleRatio: 0.5, isAligned: true, guidanceTextTr: '', landmarks: lms });
assert.equal(geom.exclusionPolygons.length, 6);
assert.deepEqual(geom.exclusionPolygons.map(p => p.id), ['rightEye', 'leftEye', 'lips', 'rightBrow', 'leftBrow', 'nostrils']);

// 4. SkinRegionSummary shows "Belirsiz (Yanak verisi eksik)" and "Değerlendirilmedi":
const stubs = {
  '../InformationButton': { InformationButton: () => null },
  'next/image': { default: () => null },
  './SkinRegionNavigator': { SkinRegionNavigator: () => React.createElement('nav', null, 'Nav') },
  '../CameraPreparation': { cameraCrop: () => ({}) },
  '../../utils/cameraStability': { StablePreviewCrop: class {} },
  '../../utils/skinSurfaceAnalysis': surface,
};
const { SkinRegionSummary } = loadTsx(prefix + 'components/skin/SkinRegionSummary.tsx', fs.readFileSync(prefix + 'components/skin/SkinRegionSummary.tsx', 'utf8'), stubs);
const { SkinFacePanel } = loadTsx(prefix + 'components/skin/SkinFacePanel.tsx', fs.readFileSync(prefix + 'components/skin/SkinFacePanel.tsx', 'utf8'), stubs);

const incompleteOverview = {
  ...demoMod.SKIN_REGIONS.forehead,
  id: 'overview',
  nameTr: 'Genel Bakış',
  skinType: { value: null, quality: 'insufficient', limitationCode: 'INCOMPLETE_CHEEKS_UNVERIFIED' },
  indicators: [{ id: 'oil', label: 'Yağlı görünüm', score: null, reason: 'unmeasured', method: 'cv', unit: '%', sampleCount: 0, appearance: { limitationCode: 'INSUFFICIENT_VISIBLE_AREA' } }],
};
const summaryHtml = renderToStaticMarkup(React.createElement(SkinRegionSummary, { currentRegion: incompleteOverview, onOpenModal: () => {}, onNavigateToCare: () => {} }));
assert(summaryHtml.includes('Belirsiz (Yanak verisi eksik)'));
assert(summaryHtml.includes('Ölçülemedi'));

const unevalOverview = {
  ...demoMod.SKIN_REGIONS.forehead,
  id: 'overview',
  nameTr: 'Genel Bakış',
  skinType: { value: null, quality: 'insufficient', limitationCode: 'NEGATIVE_EVIDENCE_METHOD_NOT_ACCEPTED', displayValue: 'Değerlendirilmedi' },
  indicators: [],
};
const unevalHtml = renderToStaticMarkup(React.createElement(SkinRegionSummary, { currentRegion: unevalOverview, onOpenModal: () => {}, onNavigateToCare: () => {} }));
assert(unevalHtml.includes('Değerlendirilmedi'));

// 5. fuseMultiAngleSkinOverview in TypeScript updates skinType and regionalSkinMap when side captures change:
function makeInd(oil, dry, pose, photoId) {
  return [
    { id: 'oil', score: oil, appearance: { value: oil, quality: 'valid', methodVersion: 'appearance-cv-6', evaluatedArea: { sourcePixels: 250, analysisPixels: 250 }, capturePose: pose, photoId } },
    { id: 'dry', score: dry, appearance: { value: dry, quality: 'valid', methodVersion: 'appearance-native-dry-2', evaluatedArea: { sourcePixels: 250, analysisPixels: 250 }, capturePose: pose, photoId } },
  ];
}
const frontGen = {
  ...demoMod.SKIN_REGIONS.forehead,
  id: 'overview',
  skinType: { value: null, quality: 'insufficient', methodVersion: 'local-vit+regional-v2', decisionTrace: { baseValue: 'normal' } },
};
const fusedDryCheeks = fuseMultiAngleSkinOverview(
  frontGen,
  {
    forehead: makeInd(6.0, 0.2, 'FRONT', 'p-front'),
    nose: makeInd(5.5, 0.1, 'FRONT', 'p-front'),
    chin: makeInd(3.0, 0.1, 'FRONT', 'p-front'),
    rightCheek: makeInd(0.2, 4.0, 'LEFT', 'p-left-dry'),
    leftCheek: makeInd(0.1, 3.8, 'RIGHT', 'p-right-dry'),
  },
  { FRONT: { photoId: 'p-front', pose: 'FRONT' }, LEFT: { photoId: 'p-left-dry', pose: 'LEFT' }, RIGHT: { photoId: 'p-right-dry', pose: 'RIGHT' } }
);
assert.equal(fusedDryCheeks.skinType.value, 'combination');
assert.equal(fusedDryCheeks.regionalSkinMap.regions.rightCheek.sourcePose, 'LEFT');
assert.equal(fusedDryCheeks.regionalSkinMap.regions.rightCheek.sourcePhotoId, 'p-left-dry');

const fusedOilyCheeks = fuseMultiAngleSkinOverview(
  frontGen,
  {
    forehead: makeInd(6.0, 0.2, 'FRONT', 'p-front'),
    nose: makeInd(5.5, 0.1, 'FRONT', 'p-front'),
    chin: makeInd(3.0, 0.1, 'FRONT', 'p-front'),
    rightCheek: makeInd(6.5, 0.2, 'LEFT', 'p-left-oily'),
    leftCheek: makeInd(5.9, 0.1, 'RIGHT', 'p-right-oily'),
  },
  { FRONT: { photoId: 'p-front', pose: 'FRONT' }, LEFT: { photoId: 'p-left-oily', pose: 'LEFT' }, RIGHT: { photoId: 'p-right-oily', pose: 'RIGHT' } }
);
assert.equal(fusedOilyCheeks.skinType.value, 'oily');
assert.equal(fusedOilyCheeks.regionalSkinMap.regions.rightCheek.state, 'oily');

// 6. SkinFacePanel: never paints a FRONT cheek onto a side (LEFT) snapshot, only renders matching sourcePose/sourcePhotoId:
const meshTri = { points: [{ x: 100, y: 100 }, { x: 160, y: 100 }, { x: 130, y: 150 }], edges: [[0, 1], [1, 2], [0, 2]], major: [0], boundary: [], excluded: [] };
const sideSnapshot = {
  width: 640,
  height: 480,
  angle: 'LEFT',
  crop: { x: 0, y: 0, width: 640, height: 480 },
  previewCrop: { x: 0.1, y: 0.1, width: 0.8, height: 0.8 },
  dataUrl: 'data:image/png;base64,AAA',
  meshes: { rightCheek: meshTri, leftCheek: meshTri },
  exclusions: [],
  exclusionPolygons: [],
  photoId: 'p-left-dry',
};
const sideHtml = renderToStaticMarkup(React.createElement(SkinFacePanel, { currentRegion: fusedDryCheeks, snapshot: sideSnapshot, mode: 'result', selectedCriterion: null }));
assert(sideHtml.includes('data-skin-type-region="rightCheek" data-skin-type-state="dry" data-source-pose="LEFT" data-source-photoid="p-left-dry" fill="#3b82f6"'));
assert(!sideHtml.includes('data-skin-type-region="leftCheek"'));

// 7. Localization: verify "Karma" and new status/guidance strings in i18n/core.ts and messages.json:
const { translateText } = require('./' + prefix + 'i18n/core.ts');
assert.equal(translateText('Karma', 'en'), 'Combination');
assert.equal(translateText('Karma', 'de'), 'Mischhaut');
assert.equal(translateText('Değerlendirilmedi', 'en'), 'Unevaluated');
assert(translateText('Sol yanağınızı kameraya göstermek için başınızı hafifçe sağa çevirin (12°–45°).', 'en').includes('12°–45°'));
'''
    r = subprocess.run(['node', '-e', script], cwd=ROOT, text=True, capture_output=True, encoding='utf8')
    assert r.returncode == 0, r.stdout + r.stderr
