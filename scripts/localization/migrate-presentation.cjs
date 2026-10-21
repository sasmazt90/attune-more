/* One-time source migration: changes JSX display boundaries, never clinical expressions. */
const fs=require('node:fs'),path=require('node:path'),ts=require('typescript');
const root=path.resolve(__dirname,'../../apps/vehicle-app/src');
function hasJSX(node){let found=false;function walk(n){if(ts.isJsxElement(n)||ts.isJsxSelfClosingElement(n)||ts.isJsxFragment(n)){found=true;return;}ts.forEachChild(n,walk);}walk(node);return found;}
function run(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){
 const file=path.join(dir,entry.name);if(entry.isDirectory()){if(entry.name!=='i18n')run(file);continue;}
 if(!file.endsWith('.tsx')||file===path.join(root,'app/layout.tsx'))continue;
 const source=fs.readFileSync(file,'utf8');if(source.includes('useTranslations'))continue;
 const sf=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true),edits=[];let hooks=0;
 const add=(start,end,text)=>edits.push({start,end,text});
 function visit(n){
  if(ts.isFunctionDeclaration(n)&&n.name&&/^[A-Z]/.test(n.name.text)&&n.body&&hasJSX(n.body)){
   add(n.body.getStart(sf)+1,n.body.getStart(sf)+1,'\n const {text:i18nText,node:i18nNode}=useTranslations();');hooks++;
  } else if(ts.isArrowFunction(n)&&ts.isVariableDeclaration(n.parent)&&/^[A-Z]/.test(n.parent.name.getText(sf))&&ts.isBlock(n.body)&&hasJSX(n.body)){
   add(n.body.getStart(sf)+1,n.body.getStart(sf)+1,'\n const {text:i18nText,node:i18nNode}=useTranslations();');hooks++;
  }
  if(ts.isJsxText(n)&&/[\p{L}]/u.test(n.text)){
   const text=n.text.replace(/&amp;/g,'&').replace(/&quot;/g,'"').replace(/&apos;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/\s+/g,' ').trim();
   const before=/^ +[^\n]/.test(n.text)?' ':'',after=/[^\n] +$/.test(n.text)?' ':'';
   add(n.pos,n.end,`{i18nText(${JSON.stringify(before+text+after)})}`);
  }else if(ts.isJsxExpression(n)&&n.expression&&(ts.isJsxElement(n.parent)||ts.isJsxFragment(n.parent))&&!hasJSX(n.expression)){
   const raw=n.expression.getText(sf);
   // User authored notes/transcripts/identity are data, not application copy.
   if(!/(?:spokenText\([^)]*\.text|\.displayName|\.driverName|\.transcript|userMessage|\.summaryText)/.test(raw))add(n.expression.getStart(sf),n.expression.end,`i18nNode(${raw})`);
   return;
  }else if(ts.isJsxAttribute(n)&&['title','alt','placeholder','aria-label','aria-description','aria-valuetext'].includes(n.name.getText(sf))&&n.initializer){
   if(ts.isStringLiteral(n.initializer)&&n.initializer.text.trim())add(n.initializer.getStart(sf),n.initializer.end,`{i18nText(${JSON.stringify(n.initializer.text)})}`);
   else if(ts.isJsxExpression(n.initializer)&&n.initializer.expression){const v=n.initializer.expression;add(v.getStart(sf),v.end,`i18nText(${v.getText(sf)})`);return;}
  }
  ts.forEachChild(n,visit);
 }visit(sf);
 if(!edits.length)continue;
 let result=source;for(const e of edits.sort((a,b)=>b.start-a.start))result=result.slice(0,e.start)+e.text+result.slice(e.end);
 const rel=path.relative(path.dirname(file),path.join(root,'i18n')).replaceAll('\\','/');const prefix=rel.startsWith('.')?rel:'./'+rel;
 const imports=`\nimport {useTranslations} from '${prefix}/LanguageProvider';\nimport {t as i18nText} from '${prefix}/core';\nimport {localizedNode as i18nNode} from '${prefix}/render';\n`;
 const directive=/^(['"])use client\1;?/.exec(result);result=directive?result.slice(0,directive[0].length)+imports+result.slice(directive[0].length):"'use client';\n"+imports+result;
 fs.writeFileSync(file,result);console.log(path.relative(root,file),hooks,'component subscriptions',edits.length,'display boundaries');
}}
run(root);
