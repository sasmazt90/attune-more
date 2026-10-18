"""Presses are events, not extra presentations or adaptive responses."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_all_press_classes_and_completed_presentations(tmp_path):
 script=r'''
const fs=require('fs'),assert=require('assert/strict'),load=require('./tests/unit/ts_source_loader.cjs')(JSON.parse(fs.readFileSync(0,'utf8')).dir);
const {HearingTrialLog}=load('hearingProgress'),log=new HearingTrialLog();
assert.equal(log.press(5),'early');
const p={id:1,ear:'left',frequency:1000,level:-60,silent:false,scheduledAt:10,startedAt:null,deadline:null,completedAt:null,answered:false};log.presentations.push(p);
assert.equal(log.press(20,p),'early');p.startedAt=30;p.deadline=100;
assert.equal(log.press(31,p),'valid');assert.equal(log.press(32,p),'duplicate');assert.equal(log.press(101,p),'late');assert.equal(log.completed(),0);
p.completedAt=101;assert.equal(log.completed('left'),1);assert.equal(log.completed('right'),0);assert.equal(log.press(102),'late');
const s={...p,id:2,ear:'right',silent:true,startedAt:150,deadline:200,completedAt:null,answered:false};log.presentations.push(s);
assert.equal(log.press(151,s),'silent');assert.equal(log.press(152,s),'duplicate');s.completedAt=201;
assert.equal(log.completed(),2);assert.equal(log.presses.length,8);assert.equal(log.presentations.length,2);
'''
 r=subprocess.run(['node','-e',script],cwd=ROOT,input=json.dumps({'dir':str(tmp_path)}),text=True,capture_output=True);assert r.returncode==0,r.stdout+r.stderr
