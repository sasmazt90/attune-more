import json
from pathlib import Path
import subprocess


def test_selected_share_model_omits_unselected_and_absent_health_fields(tmp_path):
    root = Path(__file__).resolve().parents[2]
    script = r"""
const fs=require('fs'),ts=require('typescript'),assert=require('assert');
const output=JSON.parse(fs.readFileSync(0,'utf8')).output;
fs.writeFileSync(output,ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/healthShare.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText);
const build=require(output).buildShareSections;
const vision={hasData:true,dateTr:'1 Ekim',acuitySummary:'20/20',contrastSummary:'1.5 LogCS'};
const skin={hasData:true,dateTr:'2 Ekim',regionNameTr:'Burun',changeLabel:'Referans kaydedildi',recommendation:'Takip'};
const mental={hasData:true,dateTr:'3 Ekim',primaryTheme:'PRIVATE MENTAL',sessionCountLabel:'1 görüşme'};
for(let bits=0;bits<8;bits++) {
 const selection={vision:!!(bits&1),skin:!!(bits&2),mental:!!(bits&4)};
 const result=build(selection,vision,skin,mental), serialized=JSON.stringify(result);
 assert.equal(result.length,Number(selection.vision)+Number(selection.skin)+Number(selection.mental));
 assert.equal(serialized.includes('PRIVATE MENTAL'),selection.mental);
 assert.equal(serialized.includes('20/20'),selection.vision);
 assert.equal(serialized.includes('Burun'),selection.skin);
}
const dental={title:'Diş Sağlığı',text:'8 görünür aday',dateTr:'4 Ekim'},hearing={title:'İşitme Sağlığı',text:'−1 dB SNR',dateTr:'5 Ekim'};for(let bits=0;bits<32;bits++){const selected={vision:!!(bits&1),skin:!!(bits&2),mental:!!(bits&4),dental:!!(bits&8),hearing:!!(bits&16)},sections=build(selected,vision,skin,mental,dental,hearing);assert.equal(sections.length,Object.values(selected).filter(Boolean).length);assert.equal(JSON.stringify(sections).includes('8 görünür aday'),selected.dental);assert.equal(JSON.stringify(sections).includes('−1 dB SNR'),selected.hearing);}
assert.deepEqual(build({vision:true,skin:true,mental:true},{hasData:false},{hasData:false},{hasData:false}),[]);
"""
    subprocess.run(['node','-e',"require('./tests/unit/ts_loader.js');\n"+script],cwd=root,check=True,input=json.dumps({'output':str(tmp_path/'share.cjs')}),text=True,encoding='utf-8')
