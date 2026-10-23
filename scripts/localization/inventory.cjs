/* Read source messages without executing app/model/assessment code. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),ts=require('typescript');
const root=path.resolve(__dirname,'../..');
const normalize=s=>s.normalize('NFC').replace(/\s+/g,' ').trim();
const decode=s=>s.replace(/&amp;/g,'&').replace(/&quot;/g,'"').replace(/&apos;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&#(\d+);/g,(_,n)=>String.fromCodePoint(Number(n)));
function inventory(){
 const records=new Map();
 const add=(text,file,line,kind)=>{text=normalize(text);if(!text||text.length>6000||!/[\p{L}]/u.test(text.replace(/\{\d+\}/g,'')))return;const id=crypto.createHash('sha256').update(text).digest('hex').slice(0,16);if(!records.has(id))records.set(id,{id,tr:text,references:[]});records.get(id).references.push({file,line,kind});};
 const read=(dir)=>{for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory()){if(e.name!=='i18n')read(p);}else if(/\.tsx?$/.test(p)){
  const s=fs.readFileSync(p,'utf8'),sf=ts.createSourceFile(p,s,ts.ScriptTarget.Latest,true);const file=path.relative(root,p);
  // Follow display expressions to local dictionaries, tuple arrays, helper
  // returns and notice setters. ASCII-only Turkish is otherwise invisible.
  const declarations=new Map(),setters=new Map(),calls=new Map(),assignments=new Map();
  function index(n){
   if(ts.isVariableDeclaration(n)&&n.initializer){
    if(ts.isIdentifier(n.name))declarations.set(n.name.text,n.initializer);
    else if(ts.isArrayBindingPattern(n.name)&&ts.isCallExpression(n.initializer)&&n.initializer.expression.getText(sf)==='useState'){
     const [value,setter]=n.name.elements;if(value?.name&&ts.isIdentifier(value.name)){declarations.set(value.name.text,n.initializer.arguments[0]);if(setter?.name&&ts.isIdentifier(setter.name))setters.set(value.name.text,setter.name.text);}
    }
   }
   if(ts.isFunctionDeclaration(n)&&n.name)declarations.set(n.name.text,n);
   if(ts.isBinaryExpression(n)&&n.operatorToken.kind===ts.SyntaxKind.EqualsToken&&ts.isIdentifier(n.left)){if(!assignments.has(n.left.text))assignments.set(n.left.text,[]);assignments.get(n.left.text).push(n.right);}
   if(ts.isCallExpression(n)&&ts.isIdentifier(n.expression)){const name=n.expression.text;if(!calls.has(name))calls.set(name,[]);calls.get(name).push(n);}
   ts.forEachChild(n,index);
  }index(sf);
  const active=new Set();
  function output(n){
   if(!n||active.has(n))return;active.add(n);try{display(n);}finally{active.delete(n);}
  }
  function display(n){
   if(ts.isStringLiteralLike(n)){if(/[\p{L}]/u.test(n.text))add(n.text,file,sf.getLineAndCharacterOfPosition(n.pos).line+1,'display-literal');}
   else if(ts.isTemplateExpression(n)){add(n.head.text+n.templateSpans.map((x,i)=>`{${i}}`+x.literal.text).join(''),file,sf.getLineAndCharacterOfPosition(n.pos).line+1,'display-template');for(const span of n.templateSpans)output(span.expression);}
   else if(ts.isConditionalExpression(n)){output(n.whenTrue);output(n.whenFalse);}
   else if(ts.isParenthesizedExpression(n))output(n.expression);
   else if(ts.isAsExpression(n)||ts.isTypeAssertionExpression(n)||ts.isSatisfiesExpression(n))output(n.expression);
   else if(ts.isBinaryExpression(n)&&[ts.SyntaxKind.PlusToken,ts.SyntaxKind.BarBarToken,ts.SyntaxKind.QuestionQuestionToken,ts.SyntaxKind.AmpersandAmpersandToken].includes(n.operatorToken.kind)){
    if(n.operatorToken.kind===ts.SyntaxKind.PlusToken){
     let index=0;const parts=[];
     const flatten=v=>{if(ts.isBinaryExpression(v)&&v.operatorToken.kind===ts.SyntaxKind.PlusToken){flatten(v.left);flatten(v.right);}else if(ts.isStringLiteralLike(v))parts.push(v.text);else parts.push('{'+index+++'}');};flatten(n);
     if(parts.some(p=>/\p{L}/u.test(p)))add(parts.join(''),file,sf.getLineAndCharacterOfPosition(n.pos).line+1,'display-concatenation');
    }if(n.operatorToken.kind!==ts.SyntaxKind.AmpersandAmpersandToken)output(n.left);output(n.right);
   }
   else if(ts.isArrayLiteralExpression(n))n.elements.forEach(output);
   else if(ts.isObjectLiteralExpression(n))n.properties.forEach(p=>{if(ts.isPropertyAssignment(p))output(p.initializer);else if(ts.isShorthandPropertyAssignment(p))output(p.name);});
   else if(ts.isIdentifier(n)){
    output(declarations.get(n.text));
    (assignments.get(n.text)||[]).forEach(output);
    for(const call of calls.get(setters.get(n.text))||[])call.arguments.forEach(output);
    // A mapped tuple's label/value comes from the array being mapped.
    for(let parent=n.parent;parent;parent=parent.parent){
     if((ts.isArrowFunction(parent)||ts.isFunctionExpression(parent)||ts.isFunctionDeclaration(parent))&&parent.parameters.some(p=>p.name.getText(sf).split(/\W+/).includes(n.text))){
      const call=parent.parent;
      if(ts.isCallExpression(call)&&ts.isPropertyAccessExpression(call.expression)&&call.expression.name.text==='map')output(call.expression.expression);
      else {
       const name=ts.isFunctionDeclaration(parent)?parent.name?.text:ts.isVariableDeclaration(parent.parent)&&ts.isIdentifier(parent.parent.name)?parent.parent.name.text:undefined;
       const position=parent.parameters.findIndex(p=>ts.isIdentifier(p.name)&&p.name.text===n.text);
       if(name&&position>=0)for(const invocation of calls.get(name)||[])output(invocation.arguments[position]);
      }
      break;
     }
    }
   }
   else if(ts.isElementAccessExpression(n)||ts.isPropertyAccessExpression(n))output(n.expression);
   else if(ts.isCallExpression(n)){
    if(ts.isIdentifier(n.expression)){const declaration=declarations.get(n.expression.text);if(declaration&&ts.isFunctionDeclaration(declaration))output(declaration);}
    else if(ts.isPropertyAccessExpression(n.expression)&&['map','join','filter','slice'].includes(n.expression.name.text))output(n.expression.expression);
   }
   else if(ts.isFunctionDeclaration(n)||ts.isArrowFunction(n)||ts.isFunctionExpression(n)){
    if(n.body&&ts.isBlock(n.body)){const returns=node=>{if(ts.isReturnStatement(node))output(node.expression);else if(node===n.body||!ts.isFunctionLike(node))ts.forEachChild(node,returns);};returns(n.body);}else output(n.body);
   }
  }
  function walk(n){
   if(ts.isShorthandPropertyAssignment(n)&&['name','nameTr','label','title','text','description','summaryText','detail','details','displayValue','badgeText','unit'].includes(n.name.text))output(n.name);
   // Controlled display dictionaries also contain ASCII-only Turkish (Kuru,
   // Karma, Gergin). Character-based discovery alone cannot find these labels.
   if(ts.isVariableDeclaration(n)&&/(?:^|_)(?:LABELS|GUIDANCE|UNITS)$/.test(n.name.getText(sf))&&n.initializer)output(n.initializer);
   if(ts.isCallExpression(n)&&['t','i18nText','i18nNode'].includes(n.expression.getText(sf)))n.arguments.forEach(output);
   if(ts.isPropertyAssignment(n)&&['name','nameTr','label','title','text','description','disclaimer','recommendation','hint','notice','subtitle','summary','summaryText','headline','detail','details','displayValue','badgeText','unit','date','statusLabel','statusText','providerLabel','reasonText','buttonText','emptyText','tooltip','toast'].includes(n.name.getText(sf).replace(/^['"]|['"]$/g,'')))output(n.initializer);
   if(ts.isJsxText(n)){const v=decode(n.text);if(/[\p{L}]/u.test(v))add(v,file,sf.getLineAndCharacterOfPosition(n.pos).line+1,'jsx-text');}
   else if(ts.isStringLiteralLike(n)||ts.isTemplateExpression(n)){
    const text=ts.isTemplateExpression(n)?n.head.text+n.templateSpans.map((x,i)=>`{${i}}`+x.literal.text).join(''):n.text;
    const attr=ts.isJsxAttribute(n.parent)?n.parent.name.getText(sf):'';
    if((/[çğıöşüÇĞİÖŞÜ]/.test(text)||['title','label','status','unit','caption','description','emptyText','alt','placeholder','aria-label','aria-description','aria-valuetext'].includes(attr))&&!/[<>]|=>/.test(text)&&!text.includes('://')&&!/^[.#][\w-]+\s/.test(text))add(text,file,sf.getLineAndCharacterOfPosition(n.pos).line+1,attr||ts.SyntaxKind[n.kind]);
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
