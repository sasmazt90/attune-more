"""Localized result text and rigid dental side pose acceptance."""
import subprocess
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
from localization import translate


def test_frontend_result_localization():
    r=subprocess.run(['node','tests/unit/result_localization_runtime.cjs'],cwd=ROOT,text=True,capture_output=True,timeout=40)
    assert r.returncode==0,r.stdout+r.stderr


@pytest.mark.parametrize('language,region',[('en','Forehead'),('de','Stirn')])
def test_backend_zero_result_with_optional_sign_stays_localized(language,region):
    source='Alın: kızarıklık piksel göstergesinde referansa göre 0% değişim.'
    result=translate(source,language)
    assert region in result and '0%' in result
    assert 'kızarıklık' not in result and 'değişim' not in result
    assert translate('PRIVATE Öztürk Straße İı',language)=='PRIVATE Öztürk Straße İı'


def test_dental_side_rotation_is_more_distinct_without_relaxing_other_pose_gates():
    script=r'''
require('./tests/unit/ts_loader.js');
const assert=require('assert/strict'),D=require('./apps/vehicle-app/src/utils/dentalCapture.ts');
const rotation=yaw=>({yaw,pitch:0,roll:0});
assert(!D.matchesDentalPose(rotation(Math.PI/12),'LEFT'));
assert(!D.matchesDentalPose(rotation(-Math.PI/12),'RIGHT'));
assert(D.matchesDentalPose(rotation(Math.PI/6),'LEFT'));
assert(D.matchesDentalPose(rotation(-Math.PI/6),'RIGHT'));
assert(D.matchesDentalPose(rotation(.4),'LEFT'));
assert(!D.matchesDentalPose(rotation(.399),'LEFT'));
assert(D.matchesDentalPose(rotation(-.65),'RIGHT'));
assert(!D.matchesDentalPose(rotation(-.651),'RIGHT'));
assert(!D.matchesDentalPose(rotation(.5),'RIGHT'));
for(const pose of ['FRONT','BITE']){assert(D.matchesDentalPose(rotation(.2),pose));assert(!D.matchesDentalPose(rotation(.201),pose));}
assert(!D.matchesDentalPose({yaw:.5,pitch:.23,roll:0},'LEFT'));
assert(!D.matchesDentalPose({yaw:.5,pitch:0,roll:.16},'LEFT'));
assert(!D.matchesDentalPose(null,'LEFT'));
assert(!D.matchesDentalPose(rotation(NaN),'LEFT'));
const matrix=Array(16).fill(0);matrix[0]=matrix[5]=matrix[10]=matrix[15]=1;matrix[8]=Math.sin(Math.PI/6);matrix[10]=Math.cos(Math.PI/6);
const measured=D.dentalPose({faceTransform:matrix});assert(Math.abs(measured.yaw-Math.PI/6)<1e-12);assert(D.matchesDentalPose(measured,'LEFT'));
'''
    r=subprocess.run(['node','-e',script],cwd=ROOT,text=True,capture_output=True,timeout=30)
    assert r.returncode==0,r.stdout+r.stderr
