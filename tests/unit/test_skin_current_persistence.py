"""The actual backend response must pass the ordinary frontend record contract."""
import json,subprocess
from pathlib import Path
import numpy as np
from test_local_appearance_health import skin_input
from appearance_analysis import analyze_skin
ROOT=Path(__file__).resolve().parents[2]
def test_current_response_and_old_versions_remain_valid(tmp_path):
 result=analyze_skin(skin_input(np.full((400,500,3),(100,130,175),np.uint8)))
 script=r'''
const fs=require('fs'),assert=require('assert/strict'),input=JSON.parse(fs.readFileSync(0,'utf8')),load=require('./tests/unit/ts_source_loader.cjs')(input.dir);
const S=load('skinIndicators'),A=load('appearanceMeasurements'),indicators={};
for(const [region,rows] of Object.entries(input.result.measurements))indicators[region]=S.indicatorIds(region).map(id=>({id,label:S.SIGN_LABELS[id],score:null,reason:'not measured',method:'unavailable',unit:'',sampleCount:0}));
A.attachAppearance(indicators,input.result);assert(S.validSkinIndicators(indicators));
for(const version of ['appearance-cv-1','appearance-cv-2']){const old=structuredClone(indicators);for(const rows of Object.values(old))for(const r of rows){r.appearance.methodVersion=version;r.method=version;r.measurement.methodVersion=version;}assert(S.validSkinIndicators(old));}
const invalid=structuredClone(indicators);invalid.forehead[0].appearance.methodVersion='unknown';assert(!S.validSkinIndicators(invalid));
'''
 r=subprocess.run(['node','-e',script],cwd=ROOT,input=json.dumps({'dir':str(tmp_path),'result':result}),text=True,capture_output=True);assert r.returncode==0,r.stdout+r.stderr
