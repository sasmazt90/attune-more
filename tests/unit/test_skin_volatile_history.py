"""Current-session source identity, bounds, deletion and privacy; no image persistence."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_volatile_snapshots_never_write_and_follow_existing_privacy(tmp_path):
 script=r'''
const fs=require('fs'),assert=require('assert/strict'),load=require('./tests/unit/ts_source_loader.cjs')(JSON.parse(fs.readFileSync(0,'utf8')).dir);
const events=new EventTarget(),data=new Map([['attune_privacy_skin_save_allowed','true'],['togg_health_skin_history',JSON.stringify([{id:'one'},{id:'two'},{id:'three'}])]]);
global.window=events;global.localStorage={getItem:key=>data.get(key)||null,setItem:()=>{throw Error('Must not persist pixels')}};
const H=load('skinVolatileHistory'),front={photoId:'actual-front',dataUrl:'volatile-only'},side={photoId:'actual-side'},frames={FRONT:front,LEFT:side};
let notifications=0;const unsubscribe=H.subscribeSkinSnapshots(()=>notifications++);
H.rememberSkinSnapshots('one',frames);assert.equal(H.readSkinSnapshots('one').FRONT,front);assert.equal(H.readSkinSnapshots('one').LEFT,side);assert.equal(H.skinSnapshotVersion(),1);
H.rememberSkinSnapshots('two',frames);H.rememberSkinSnapshots('three',frames);assert.equal(H.readSkinSnapshots('one'),undefined);assert(H.readSkinSnapshots('two'));
data.set('togg_health_skin_history',JSON.stringify([{id:'three'}]));window.dispatchEvent(new Event('attune-records'));assert.equal(H.readSkinSnapshots('two'),undefined);assert(H.readSkinSnapshots('three'));
data.set('attune_privacy_skin_save_allowed','false');window.dispatchEvent(new Event('attune-privacy'));assert.equal(H.readSkinSnapshots('three'),undefined);H.rememberSkinSnapshots('three',frames);assert.equal(H.readSkinSnapshots('three'),undefined);
assert(notifications>=5);unsubscribe();assert(![...data.values()].some(value=>value.includes('dataUrl')));
'''
 r=subprocess.run(['node','-e',script],input=json.dumps({'dir':str(tmp_path)}),text=True,capture_output=True,cwd=ROOT);assert r.returncode==0,r.stdout+r.stderr
