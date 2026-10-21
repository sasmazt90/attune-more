/** Execute actual JSX gate and route-effect bodies; no synthetic audio/capture. */
const fs=require('fs'),ts=require('typescript'),assert=require('assert/strict');
const text=fs.readFileSync('apps/vehicle-app/src/components/LanguageSelector.tsx','utf8');
const ast=ts.createSourceFile('LanguageSelector.tsx',text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);let gate,routeEffect;
function visit(node){
 if(ts.isJsxAttribute(node)&&node.name.getText(ast)==='disabled'&&node.initializer?.expression?.getText(ast).includes("pathname!=='/'"))gate=node.initializer.expression.getText(ast);
 if(ts.isCallExpression(node)&&node.expression.getText(ast)==='useEffect'&&node.arguments[1]?.getText(ast)==='[pathname]')routeEffect=node.arguments[0].body.getText(ast);
 ts.forEachChild(node,visit);
}visit(ast);assert(gate);assert(routeEffect);
const disabled=new Function('permitted','pathname','sample','selectedVoice','preview','return '+gate);
assert.equal(disabled(true,'/','Nonpersonal 1287',{},''),false);
for(const path of ['/mental','/vision','/hearing','/vocal','/dental','/skin','/health-summary'])assert.equal(disabled(true,path,'Nonpersonal 1287',{},''),true,path);
assert(disabled(false,'/','Text',{},''));assert(disabled(true,'/',' ',{},''));assert(disabled(true,'/','Text',null,''));for(const state of ['starting','speaking'])assert(disabled(true,'/','Text',{},state));
let aborted=0,sample='old',preview='speaking';const controller={current:{abort(){aborted++;}}};
new Function('previewController','setSample','setPreview',routeEffect)(controller,v=>sample=v,v=>preview=v);
assert.equal(aborted,1);assert.equal(controller.current,null);assert.equal(sample,'');assert.equal(preview,'');
console.log('PASS actual preview route gate, parked/text/voice/concurrency guards and cancellation on navigation; no synthesis or capture');
