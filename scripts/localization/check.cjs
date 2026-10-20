/* Completeness is an inventory check, not a claim of linguistic/clinical review. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),cp=require('node:child_process'),ts=require('typescript');
const {inventory,normalize}=require('./inventory.cjs');
const root=path.resolve(__dirname,'../..'),catalog=require('../../shared/localization/messages.json'),exempt=require('../../shared/localization/exemptions.json');
const failures=[];
const backend=JSON.parse(cp.execFileSync(process.env.ATTUNE_TOOL_PYTHON||'python3',[path.join(__dirname,'backend_inventory.py')],{encoding:'utf8'}));
const rows=[...inventory(),...backend];
for(const row of rows){if(!catalog[row.id]&&!exempt[row.id])failures.push({reason:'Missing message',...row});if(exempt[row.id]&&normalize(exempt[row.id].source)!==normalize(row.tr))failures.push({reason:'Invalid exemption',id:row.id});}
for(const [id,row] of Object.entries(catalog)){
 if(crypto.createHash('sha256').update(normalize(row.tr)).digest('hex').slice(0,16)!==id)failures.push({reason:'Unstable source ID',id});
 const placeholders=s=>JSON.stringify((s.match(/\{\d+\}/g)||[]).sort());
 for(const language of ['tr','en','de'])if(!row[language]?.trim()||placeholders(row[language])!==placeholders(row.tr))failures.push({reason:'Missing translation/placeholder mismatch',id,language});
}
function outputLiterals(n){if(ts.isStringLiteralLike(n))return /\p{L}/u.test(n.text)?[n.text]:[];if(ts.isTemplateExpression(n))return[n.getText()];if(ts.isConditionalExpression(n))return [...outputLiterals(n.whenTrue),...outputLiterals(n.whenFalse)];if(ts.isBinaryExpression(n)&&[ts.SyntaxKind.PlusToken,ts.SyntaxKind.AmpersandAmpersandToken,ts.SyntaxKind.BarBarToken,ts.SyntaxKind.QuestionQuestionToken].includes(n.operatorToken.kind))return n.operatorToken.kind===ts.SyntaxKind.PlusToken?[...outputLiterals(n.left),...outputLiterals(n.right)]:outputLiterals(n.right);return[];}
function visit(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){
 const file=path.join(dir,entry.name);if(entry.isDirectory())visit(file);else if(file.endsWith('.tsx')){
  const source=fs.readFileSync(file,'utf8'),sf=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true);
  function walk(n){
   if(ts.isJsxExpression(n)&&n.expression&&(ts.isJsxElement(n.parent)||ts.isJsxFragment(n.parent))&&outputLiterals(n.expression).length)failures.push({reason:'Unlocalized JSX output expression',file:path.relative(root,file),line:sf.getLineAndCharacterOfPosition(n.pos).line+1,text:outputLiterals(n.expression)});
   if(ts.isJsxText(n)&&/\p{L}/u.test(n.text))failures.push({reason:'Unlocalized JSX text',file:path.relative(root,file),line:sf.getLineAndCharacterOfPosition(n.pos).line+1,text:n.text.trim()});
   if(ts.isJsxAttribute(n)&&['title','alt','placeholder','aria-label','aria-description'].includes(n.name.getText(sf))&&n.initializer&&ts.isStringLiteral(n.initializer)&&/\p{L}/u.test(n.initializer.text))failures.push({reason:'Unlocalized accessible attribute',file:path.relative(root,file),text:n.initializer.text});
   ts.forEachChild(n,walk);
  }walk(sf);
 }
}}
visit(path.join(root,'apps/vehicle-app/src'));
const result={status:failures.length?'FAIL':'PASS',catalogMessages:Object.keys(catalog).length,inventoriedSources:new Set(rows.map(r=>r.id)).size,exemptions:Object.keys(exempt).length,scope:'Frontend JSX/accessibility/source literals and shared modules/guidance; backend API/mental/care/control plus health-module response/error presentation sources. Dynamic/private/provider text needs runtime review.',failures};
process.stdout.write(JSON.stringify(result,null,2)+'\n');if(failures.length)process.exitCode=1;
