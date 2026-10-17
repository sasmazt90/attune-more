"""Real frontend window planner protects backend limits for long ASR turns."""
import json,subprocess
from pathlib import Path

def test_message_and_character_windows_keep_completed_pairs_and_do_not_skip_prefix():
    root=Path(__file__).resolve().parents[2]
    code=r'''
const fs=require('fs'),ts=require('typescript'),Module=require('module');
const path='apps/vehicle-app/src/utils/mentalContextWindow.ts';
const mod=new Module(path);mod._compile(ts.transpileModule(fs.readFileSync(path,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,path);
const plan=mod.exports.contextWindowThrough;
const cases=[{n:220,size:40,previous:0},{n:22,size:6000,previous:0},{n:12,size:6000,previous:0},{n:42,size:100,previous:18}];
console.log(JSON.stringify(cases.map(c=>{const rows=Array.from({length:c.n},()=>({text:'x'.repeat(c.size)})),through=plan(rows,c.previous);return {...c,through,recentChars:rows.slice(through).reduce((n,m)=>n+m.text.length,0),recentCount:c.n-through};})));
'''
    rows=json.loads(subprocess.check_output([r'C:\nvm4w\nodejs\node.exe','-e',code],cwd=root,text=True))
    assert rows[0]['through']==204 and rows[0]['recentCount']==16
    assert rows[1]['recentChars']<=48000 and rows[1]['through']%2==0
    assert rows[2]['through']==0 # No needless compaction or lost prefix.
    assert rows[3]['through']==18 # Already summarized prefix is not processed twice.
    assert all(r['recentChars']<=120000 and r['recentCount']<=40 for r in rows)
