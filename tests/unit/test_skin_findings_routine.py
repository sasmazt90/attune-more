"""Finding provenance, measured line geometry, and compatible routine behavior."""
from pathlib import Path
import subprocess
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
from skin_display_geometry import measured_line_paths


def test_lines_follow_measured_support_and_source_coordinates():
    support = np.zeros((7, 9), dtype=float)
    support[3, 1:8] = 1
    paths = measured_line_paths(support, np.ones_like(support, dtype=bool), 10, 20, 2, (100, 200))
    assert len(paths) == 1 and len(paths[0]) == 7
    assert {p['y'] for p in paths[0]} == {211.75}
    assert {p['x'] for p in paths[0]} == {105.75 + i / 2 for i in range(7)}
    assert measured_line_paths(support, np.zeros_like(support, dtype=bool), 0, 0, 1) == []
    isolated = np.zeros((3, 3)); isolated[1, 1] = 1
    assert measured_line_paths(isolated, np.ones_like(isolated, dtype=bool), 0, 0, 1) == []


def test_routine_and_findings_reject_missing_or_wrong_source_data():
    script = r'''
require('./tests/unit/ts_loader.js');
const assert = require('assert/strict');
const {buildSkinRoutine} = require('./apps/vehicle-app/src/utils/skinRoutine.ts');
const {sourceMatchedFindings} = require('./apps/vehicle-app/src/utils/skinFindingPresentation.ts');
const {matchesSkinAngle} = require('./apps/vehicle-app/src/utils/skinMultiAngle.ts');
const pose={faceDetected:true,isMediaPipeActive:true,sourceFramed:true,scaleRatio:.4,pitch:0,roll:0};
assert(!matchesSkinAngle({...pose,yaw:.399},'LEFT'));
assert(matchesSkinAngle({...pose,yaw:.4},'LEFT'));
assert(matchesSkinAngle({...pose,yaw:-.65},'RIGHT'));
assert(!matchesSkinAngle({...pose,yaw:-.651},'RIGHT'));
const row = (id, score, quality='valid') => ({id,score,measurement:{quality}});
assert.deepEqual(buildSkinRoutine([]), []);
assert.deepEqual(buildSkinRoutine([row('acne',95,'insufficient')]), []);
const acne = buildSkinRoutine([row('acne',30)]);
assert.deepEqual(acne.map(s=>s.id), ['cleanse','care','moisturize','sunscreen']);
assert(acne.find(s=>s.id==='care').items.join(' ').includes('salisilik'));
const red = buildSkinRoutine([row('acne',30),row('redness',10)]);
assert(!red.flatMap(s=>s.items).join(' ').includes('salisilik'));
const neutral = buildSkinRoutine([row('acne',0)]);
assert(!neutral.flatMap(s=>s.items).join(' ').includes('salisilik'));
const combo = buildSkinRoutine([row('oil',12)],{value:'combination',quality:'valid'});
assert(combo.flatMap(s=>s.items).join(' ').includes('Karma'));
const source={photoId:'photo-a',angle:'FRONT',width:640,height:480};
const good={criterion:'dry',photoId:'photo-a',pose:'FRONT',sourceWidth:640,sourceHeight:480,modelHash:'a'.repeat(64),confidence:.8,box:{x:10,y:20,width:50,height:30}};
assert.equal(sourceMatchedFindings([good],source,'dry').length,1);
assert.equal(sourceMatchedFindings([{...good,photoId:undefined}],{...source,photoId:undefined},'dry').length,0);
for(const change of [{photoId:'photo-b'},{pose:'LEFT'},{sourceWidth:1280},{modelHash:'unverified'},{confidence:NaN},{box:{x:630,y:20,width:50,height:30}}])
  assert.equal(sourceMatchedFindings([{...good,...change}],source,'dry').length,0);
'''
    result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
