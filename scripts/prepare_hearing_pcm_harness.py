"""Inject exact hashed runtime modules only into an isolated browser test."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent/'cdc-progress/hearing-technical-closeout-20261017'
modules={};hashes={}
focus=len(sys.argv)>1 and sys.argv[1]=='focus'
for name in ['hearingProtocol','playbackMeter','hearingAudio']+(['streamSpeech'] if focus else []):
 p=ROOT/f'apps/vehicle-app/src/utils/{name}.ts';hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
 modules['./'+name]=subprocess.check_output(['node','-e',"const fs=require('fs'),ts=require('typescript');process.stdout.write(ts.transpileModule(fs.readFileSync(process.argv[1],'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)",str(p)],cwd=ROOT,text=True,encoding='utf8')
source=(ROOT/('tests/e2e/hearing_focus_template.js' if focus else 'tests/e2e/hearing_pcm_template.js')).read_text('utf8').replace('__MODULES__',json.dumps(modules)).replace('__HASHES__',json.dumps(hashes))
(OUT/('focus-harness.js' if focus else 'pcm-harness.js')).write_text(source,'utf8')
