"""Comprehensive regression tests for all 5 blockers and P0/P1 product refinements."""
from pathlib import Path
import json, subprocess, sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
import local_skin_type as T
from skin_display_geometry import measured_line_paths
from roboflow_skin_models import APPROVED_LESION_THRESHOLDS


def _rows(oil=0.0, dry=0.0, redness=5.0):
    area = dict(sourcePixels=250, analysisPixels=250, foreheadSourcePixels=120, noseSourcePixels=130)
    return [
        dict(id='oil', value=oil, quality='valid', methodVersion='appearance-cv-6', evaluatedArea=area),
        dict(id='dry', value=dry, quality='valid', methodVersion='appearance-native-dry-3', evaluatedArea=area),
        dict(id='redness', value=redness, quality='valid', methodVersion='appearance-cv-6', evaluatedArea=area),
    ]


def _base(val='dry'):
    return dict(value=val, quality='valid', confidence=None, methodVersion='skin-type-local-vit-v1', modelHash='a' * 64, inferenceKind='local-onnx')


def test_blocker_1_and_2_regional_skin_type_rules():
    # 1. Missing cheek -> value=None, quality='insufficient', limitationCode='INCOMPLETE_CHEEKS_UNVERIFIED'
    r_missing_cheek = dict(forehead=_rows(8, 0), nose=_rows(9, 0), chin=_rows(5, 0), leftCheek=_rows(0, 0))
    res_missing = T.regional_decision(_base('dry'), r_missing_cheek)
    assert res_missing['value'] is None
    assert res_missing['quality'] == 'insufficient'
    assert res_missing['limitationCode'] == 'INCOMPLETE_CHEEKS_UNVERIFIED'

    # 2. Tiny 0.01% oil on forehead & nose -> normal, NEVER combination
    r_noise = dict(forehead=_rows(0.01, 0), nose=_rows(0.01, 0), chin=_rows(0, 0), leftCheek=_rows(0, 0), rightCheek=_rows(0, 0))
    res_noise = T.regional_decision(_base('dry'), r_noise)
    assert res_noise['value'] == 'normal'
    assert res_noise['decisionTrace']['tZone']['state'] == 'non-oily'

    # 3. Chin-only oil (1/3 of T-zone) -> NOT combination
    r_chin_only = dict(forehead=_rows(0, 0), nose=_rows(0, 0), chin=_rows(6.5, 0), leftCheek=_rows(0, 0), rightCheek=_rows(0, 0))
    res_chin = T.regional_decision(_base('normal'), r_chin_only)
    assert res_chin['value'] == 'normal'
    assert res_chin['decisionTrace']['tZone']['state'] == 'non-oily'

    # 4. Missing chin -> T-zone incomplete -> value=None, limitationCode='INCOMPLETE_TZONE_UNVERIFIED'
    r_no_chin = dict(forehead=_rows(8, 0), nose=_rows(8, 0), leftCheek=_rows(0, 0), rightCheek=_rows(0, 0))
    res_no_chin = T.regional_decision(_base('normal'), r_no_chin)
    assert res_no_chin['value'] is None
    assert res_no_chin['quality'] == 'insufficient'
    assert res_no_chin['limitationCode'] == 'INCOMPLETE_TZONE_UNVERIFIED'

    # 5. Cheek with 0.01% oil (<= 1.0%) does NOT block combination when 2/3 of T-zone is oily
    r_comb = dict(forehead=_rows(5.5, 0), nose=_rows(0.2, 0), chin=_rows(4.2, 0), leftCheek=_rows(0.01, 0.2), rightCheek=_rows(0.3, 3.5))
    res_comb = T.regional_decision(_base('dry'), r_comb)
    assert res_comb['value'] == 'combination'
    assert res_comb['decisionTrace']['regions']['leftCheek']['state'] == 'normal'
    assert res_comb['decisionTrace']['regions']['rightCheek']['state'] == 'dry'


def test_blocker_5_skeletonized_wrinkle_line_paths_and_thresholds():
    assert set(APPROVED_LESION_THRESHOLDS.keys()) == {'papule', 'pustule', 'open_comedo', 'closed_comedo'}
    ridge = np.zeros((60, 60), np.float32)
    roi = np.ones((60, 60), bool)
    for x in range(10, 48):
        y = int(20 + 0.25 * (x - 10))
        ridge[y, x] = 0.08
    paths = measured_line_paths(ridge, roi, 0.0125)
    assert len(paths) >= 1
    assert paths[0]['source'] == 'skeletonized-highpass-ridge-v1'
    assert len(paths[0]['points']) >= 2


def test_frontend_blockers_3_4_5_and_ui_refinements():
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
const { SkinAnalyzer } = require('./' + prefix + 'utils/skinAnalyzer.ts');

// 1. Redness labels are distinct between whole-face and regional scopes:
assert.equal(indicatorsMod.skinCriterionLabel('redness', 'whole-face'), 'Genel kızarıklık indeksi');
assert.equal(indicatorsMod.skinCriterionLabel('redness', 'regional'), 'Bölgesel kızarıklık farkı');
assert.equal(demoMod.SKIN_REGIONS.nose.nameTr, 'T Bölgesi');

// 2. Landmark-scaled exclusionBoxes and exclusionPolygons cover eyes, lips, brows, nostrils:
const lms = Array.from({ length: 468 }, (_, i) => ({ x: 0.25 + (i % 20) * 0.025, y: 0.2 + Math.floor(i / 20) * 0.025, z: 0 }));
const geom = SkinAnalyzer.regionGeometry(640, 480, { faceDetected: true, isMediaPipeActive: true, yaw: 0, pitch: 0, roll: 0, scaleRatio: 0.5, isAligned: true, guidanceTextTr: '', landmarks: lms });
assert.equal(geom.exclusionPolygons.length, 6);
assert.deepEqual(geom.exclusionPolygons.map(p => p.id), ['rightEye', 'leftEye', 'lips', 'rightBrow', 'leftBrow', 'nostrils']);

// 3. SkinRegionSummary shows "Belirsiz (Yanak verisi eksik)" when cheek is missing (value: null, quality: 'insufficient'):
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
const { SkinIndicatorValue } = loadTsx(prefix + 'components/skin/SkinIndicatorValue.tsx', fs.readFileSync(prefix + 'components/skin/SkinIndicatorValue.tsx', 'utf8'), stubs);

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

// 4. SkinFacePanel: combination with normal leftCheek and dry rightCheek colors ONLY rightCheek blue and T-zone green, leaving leftCheek colorless:
const meshTri = { points: [{ x: 100, y: 100 }, { x: 160, y: 100 }, { x: 130, y: 150 }], edges: [[0, 1], [1, 2], [0, 2]], major: [0], boundary: [], excluded: [] };
const snapshot = {
  width: 640,
  height: 480,
  angle: 'FRONT',
  crop: { x: 0, y: 0, width: 640, height: 480 },
  previewCrop: { x: 0.1, y: 0.1, width: 0.8, height: 0.8 },
  dataUrl: 'data:image/png;base64,AAA',
  meshes: { forehead: meshTri, nose: meshTri, chin: meshTri, leftCheek: meshTri, rightCheek: meshTri },
  exclusions: [{ x: 200, y: 200, w: 30, h: 20 }],
  exclusionPolygons: [{ id: 'lips', points: [{ x: 290, y: 290 }, { x: 330, y: 290 }, { x: 330, y: 330 }, { x: 290, y: 330 }] }],
  acneCandidates: {
    overview: [
      { x: 120, y: 110, width: 10, height: 10, canonicalClass: 'papule', pointSource: 'box_centroid', photoId: 'p1' },
      { x: 300, y: 300, width: 10, height: 10, canonicalClass: 'other', pointSource: 'box_centroid', photoId: 'p1' }, // inside lips polygon -> must be excluded!
    ],
  },
  localMaps: {
    'periorbital:lines': {
      criterion: 'lines', region: 'periorbital', pose: 'FRONT', photoId: 'p1', sourceWidth: 640, sourceHeight: 480,
      x: 0, y: 0, step: 1, width: 640, height: 480, unit: '%', method: 'cv', validation: 'appearance-proxy',
      colorMapping: 'cyan-fixed-100-v1', dataUrl: 'data:image/png;base64,AAA', validMaskUrl: 'data:image/png;base64,AAA',
      sampleCount: 100, values: new Float32Array(0), validMask: new Uint8Array(0),
      linePaths: [{ id: 'line-1', strength: 0.8, source: 'skeletonized-highpass-ridge-v1', points: [{ x: 110, y: 110 }, { x: 140, y: 125 }] }],
    },
  },
  photoId: 'p1',
};
const combOverview = {
  ...demoMod.SKIN_REGIONS.forehead,
  id: 'overview',
  nameTr: 'Genel Bakış',
  skinType: {
    value: 'combination',
    quality: 'valid',
    decisionTrace: {
      regions: {
        forehead: { state: 'oily' },
        nose: { state: 'oily' },
        chin: { state: 'normal' },
        leftCheek: { state: 'normal' },
        rightCheek: { state: 'dry' },
      },
    },
  },
};
const overlayHtml = renderToStaticMarkup(React.createElement(SkinFacePanel, { currentRegion: combOverview, snapshot, mode: 'result', selectedCriterion: null }));
assert(overlayHtml.includes('data-skin-type-region="forehead" data-skin-type-state="oily" fill="#22c55e"'));
assert(overlayHtml.includes('data-skin-type-region="rightCheek" data-skin-type-state="dry" fill="#3b82f6"'));
assert(!overlayHtml.includes('data-skin-type-region="leftCheek"'));
assert(!overlayHtml.includes('data-skin-type-region="chin"'));
assert(!overlayHtml.includes('data-skin-mesh'));

// 5. Acne markers exclude lips polygon and carry data-point-source="box_centroid":
const acneHtml = renderToStaticMarkup(React.createElement(SkinFacePanel, { currentRegion: combOverview, snapshot, mode: 'result', selectedCriterion: 'acne' }));
assert.equal((acneHtml.match(/data-acne-candidate=/g) || []).length, 1);
assert(acneHtml.includes('data-acne-class="papule"'));
assert(acneHtml.includes('data-point-source="box_centroid"'));

// 6. Wrinkle linePaths render SVG <path data-skin-line-path="line-1">:
const periorbitalRegion = { ...demoMod.SKIN_REGIONS.periorbital, id: 'periorbital' };
const snapshotPeriorbital = { ...snapshot, meshes: { ...snapshot.meshes, periorbital: meshTri } };
const linesHtml = renderToStaticMarkup(React.createElement(SkinFacePanel, { currentRegion: periorbitalRegion, snapshot: snapshotPeriorbital, mode: 'result', selectedCriterion: 'lines' }));
assert(linesHtml.includes('data-skin-line-path="line-1"'));
'''
    r = subprocess.run(['node', '-e', script], cwd=ROOT, text=True, capture_output=True, encoding='utf8')
    assert r.returncode == 0, r.stdout + r.stderr
