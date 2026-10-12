"""Focused UI test verifying that TOGG Attune skin overview components correctly
render the 4 skin type Turkish labels (Normal, Kuru, Yağlı, Karma).
Tests data contract in skinOverview.ts and rendered HTML of SkinRegionSummary.
"""
import os, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def get_node_env():
    env = os.environ.copy()
    default_node_path = r"C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\node_modules;C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\apps\vehicle-app\node_modules"
    if 'NODE_PATH' not in env:
        env['NODE_PATH'] = default_node_path
    else:
        env['NODE_PATH'] = f"{env['NODE_PATH']};{default_node_path}"
    return env

def test_skin_type_turkish_labels_mapping():
    """Verify data contract in skinOverview.ts:
    normal -> Normal
    dry -> Kuru
    oily -> Yağlı
    combination -> Karma
    """
    script = r'''
const assert = require('assert/strict');
require('./tests/unit/ts_loader.js');
const { SKIN_TYPE_LABELS, buildSkinViewModel } = require('./apps/vehicle-app/src/utils/skinOverview.ts');

assert.deepEqual(SKIN_TYPE_LABELS, {
  normal: 'Normal',
  dry: 'Kuru',
  oily: 'Yağlı',
  combination: 'Karma'
});

const types = ['normal', 'dry', 'oily', 'combination'];
const expectedTr = ['Normal', 'Kuru', 'Yağlı', 'Karma'];

for (let i = 0; i < types.length; i++) {
  const typeId = types[i];
  const trName = expectedTr[i];
  assert.equal(SKIN_TYPE_LABELS[typeId], trName);

  const mockResult = {
    general: {
      skinType: { value: typeId, quality: 'valid', confidence: 0.95 },
      indicators: []
    }
  };
  const vm = buildSkinViewModel('overview', mockResult);
  assert.equal(vm.id, 'overview');
  assert.equal(vm.nameTr, 'Genel Bakış');
  assert.equal(vm.skinType.value, typeId);
  assert.equal(SKIN_TYPE_LABELS[vm.skinType.value], trName);
}
'''
    res = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True, env=get_node_env())
    assert res.returncode == 0, res.stdout + res.stderr

def test_skin_region_summary_renders_turkish_labels():
    """Verify that SkinRegionSummary renders each Turkish label in the UI element [data-skin-type]."""
    script = r'''
const fs = require('fs');
const ts = require('typescript');
const assert = require('assert/strict');
const Module = require('module');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

require('./tests/unit/ts_loader.js');

function load(path, stubs = {}) {
  const m = new Module(path, module);
  m.paths = module.paths;
  m.require = (id) => id in stubs ? stubs[id] : require(id);
  m._compile(
    ts.transpileModule(fs.readFileSync(path, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2022, esModuleInterop: true }
    }).outputText,
    path
  );
  return m.exports;
}

const { SkinRegionSummary } = load('apps/vehicle-app/src/components/skin/SkinRegionSummary.tsx', {
  '../InformationButton': { InformationButton: () => null }
});

const testCases = [
  { value: 'normal', quality: 'valid', expected: 'Normal' },
  { value: 'dry', quality: 'valid', expected: 'Kuru' },
  { value: 'oily', quality: 'valid', expected: 'Yağlı' },
  { value: 'combination', quality: 'valid', expected: 'Karma' },
  { value: null, quality: 'insufficient', expected: '—' },
  { value: 'normal', quality: 'invalid', expected: '—' }
];

for (const tc of testCases) {
  const region = {
    id: 'overview',
    nameTr: 'Genel Bakış',
    metrics: {},
    indicators: [],
    skinType: { value: tc.value, quality: tc.quality }
  };
  const html = renderToStaticMarkup(
    React.createElement(SkinRegionSummary, {
      currentRegion: region,
      onOpenModal: () => {},
      onNavigateToCare: () => {}
    })
  );

  // Must contain data-skin-type container
  assert(html.includes('data-skin-type'), 'data-skin-type attribute missing');
  assert(html.includes('Cilt tipi'), 'Label "Cilt tipi" missing in overview card');
  assert(html.includes(`<strong class="text-base text-white">${tc.expected}</strong>`),
    `Expected rendered label "${tc.expected}" for skinType value=${tc.value}, quality=${tc.quality}, got html: ${html}`);
}
'''
    res = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True, env=get_node_env())
    assert res.returncode == 0, res.stdout + res.stderr
