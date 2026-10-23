/* Read source messages without executing app/model/assessment code. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),ts=require('typescript');
const root=path.resolve(__dirname,'../..');
const normalize=s=>s.normalize('NFC').replace(/\s+/g,' ').trim();
const decode=s=>s.replace(/&amp;/g,'&').replace(/&quot;/g,'"').replace(/&apos;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&#(\d+);/g,(_,n)=>String.fromCodePoint(Number(n)));
function inventory(){
 const records=new Map();
 const add=(text,file,line,kind)=>{text=normalize(text);if(!text||text.length>6000)return;const id=crypto.createHash('sha256').update(text).digest('hex').slice(0,16);if(!records.has(id))records.set(id,{id,tr:text,references:[]});records.get(id).references.push({file,line,kind});};
 const read=(dir)=>{for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory()){if(e.name!=='i18n')read(p);}else if(/\.tsx?$/.test(p)){
  const s=fs.readFileSync(p,'utf8'),sf=ts.createSourceFile(p,s,ts.ScriptTarget.Latest,true);const file=path.relative(root,p);
  function output(n){
   if(ts.isStringLiteralLike(n)){if(/[\p{L}]/u.test(n.text))add(n.text,file,sf.getLineAndCharacterOfPosition(n.pos).line+1,'display-literal');}
   else if(ts.isTemplateExpression(n)){add(n.head.text+n.templateSpans.map((x,i)=>`{${i}}`+x.literal.text).join(''),file,sf.getLineAndCharacterOfPosition(n.pos).line+1,'display-template');for(const span of n.templateSpans)output(span.expression);}
   else if(ts.isConditionalExpression(n)){output(n.whenTrue);output(n.whenFalse);}
   else if(ts.isParenthesizedExpression(n))output(n.expression);
   else if(ts.isAsExpression(n)||ts.isTypeAssertionExpression(n)||ts.isSatisfiesExpression(n))output(n.expression);
   else if(ts.isBinaryExpression(n)&&[ts.SyntaxKind.PlusToken,ts.SyntaxKind.BarBarToken,ts.SyntaxKind.QuestionQuestionToken].includes(n.operatorToken.kind)){
    if(n.operatorToken.kind===ts.SyntaxKind.PlusToken){
     let index=0;const parts=[];
     const flatten=v=>{if(ts.isBinaryExpression(v)&&v.operatorToken.kind===ts.SyntaxKind.PlusToken){flatten(v.left);flatten(v.right);}else if(ts.isStringLiteralLike(v))parts.push(v.text);else parts.push('{'+index+++'}');};flatten(n);
     if(parts.some(p=>/\p{L}/u.test(p)))add(parts.join(''),file,sf.getLineAndCharacterOfPosition(n.pos).line+1,'display-concatenation');
    }output(n.left);output(n.right);
   }
   else if(ts.isArrayLiteralExpression(n))n.elements.forEach(output);
   else if(ts.isObjectLiteralExpression(n))n.properties.forEach(p=>{if(ts.isPropertyAssignment(p))output(p.initializer);});
  }
  function walk(n){
   // Controlled display dictionaries also contain ASCII-only Turkish (Kuru,
   // Karma, Gergin). Character-based discovery alone cannot find these labels.
   if(ts.isVariableDeclaration(n)&&['SKIN_TYPE_LABELS','SIGN_LABELS','MOOD_LABELS','REGION_LABELS','DENTAL_GUIDANCE','APPEARANCE_UNITS'].includes(n.name.getText(sf))&&n.initializer)output(n.initializer);
   if(ts.isCallExpression(n)&&['t','i18nText','i18nNode'].includes(n.expression.getText(sf)))n.arguments.forEach(output);
   if(ts.isPropertyAssignment(n)&&['name','nameTr','label','title','text','description','disclaimer','recommendation','hint','notice','subtitle','summaryText'].includes(n.name.getText(sf).replace(/^['"]|['"]$/g,'')))output(n.initializer);
   if(ts.isJsxText(n)){const v=decode(n.text);if(/[\p{L}]/u.test(v))add(v,file,sf.getLineAndCharacterOfPosition(n.pos).line+1,'jsx-text');}
   else if(ts.isStringLiteralLike(n)||ts.isTemplateExpression(n)){
    const text=ts.isTemplateExpression(n)?n.head.text+n.templateSpans.map((x,i)=>`{${i}}`+x.literal.text).join(''):n.text;
    const attr=ts.isJsxAttribute(n.parent)?n.parent.name.getText(sf):'';
    if((/[çğıöşüÇĞİÖŞÜ]/.test(text)||['title','alt','placeholder','aria-label','aria-description','aria-valuetext'].includes(attr))&&!/[<>]|=>/.test(text)&&!text.includes('://')&&!/^[.#][\w-]+\s/.test(text))add(text,file,sf.getLineAndCharacterOfPosition(n.pos).line+1,attr||ts.SyntaxKind[n.kind]);
   }
   ts.forEachChild(n,walk);
  }walk(sf);
 }}};
 read(path.join(root,'apps/vehicle-app/src'));
 for(const file of ['shared/healthModules.json','apps/vehicle-app/public/audio/guidance/manifest.json','apps/vehicle-app/public/audio/vision-speech/manifest.json']){
  const visit=(v,key)=>{if(typeof v==='string'&&(/[çğıöşüÇĞİÖŞÜ]/.test(v)||['text','name','specialties'].includes(key)))add(v,file,1,key);else if(Array.isArray(v))v.forEach(x=>visit(x,key));else if(v&&typeof v==='object')Object.entries(v).forEach(([k,x])=>visit(x,k));};
  if(fs.existsSync(path.join(root,file)))visit(JSON.parse(fs.readFileSync(path.join(root,file),'utf8')),'');
 }
 return [...records.values()].sort((a,b)=>a.tr.localeCompare(b.tr,'tr'));
}
module.exports={inventory,normalize};
if(require.main===module)process.stdout.write(JSON.stringify(inventory(),null,2)+'\n');
