'use strict';

// Run in the finite Windows Job harness, not a product process.
const assert = require('node:assert/strict');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const braces = require(path.join(root, 'node_modules/braces'));
const original = process.argv[2] && require(process.argv[2]);
let checks = 0;
const reject = fn => { assert.throws(fn, e => e instanceof RangeError && e.code === 'ERR_BRACES_STRUCTURE'); checks++; };
for (const [input,expected] of [
  ['a{b,c}d',['abd','acd']], ['{1..3}',['1','2','3']],
  ['{01..03}',['01','02','03']], ['{a..e..2}',['a','c','e']],
  ['"{a,b}"',['{a,b}']], ['src/**/*.{ts,tsx}',['src/**/*.ts','src/**/*.tsx']]
]) { assert.deepEqual(braces.expand(input),expected); checks++; }
assert.equal(braces.compile('a{b,c}d'),'a(b|c)d'); checks++;
assert.equal(braces.stringify('a{b,c}d'),'a{b,c}d'); checks++;
const patterns = [
  '', 'x', 'a{b,c}d', '{,a,,b}', '{a,b}{c,d}', '{{a,b},c}',
  '{1..5}', '{01..05}', '{-3..3..2}', '{a..f..2}', '{5..1}',
  'src/**/*.{js,ts,jsx,tsx,mdx}', './app/**/{page,layout}.{js,tsx}',
  'foo/\\{a,b\\}', '\\(x\\)', '[{a,b}]', '"{a,b}"', "'{a,b}'",
  '`{a,b}`', '${a,b}', '{abc}', '{a,b', '(x(y))', '{1..3,a}',
  '{'.repeat(1000).replace(/\{/g, '\\{'), '"' + '{'.repeat(1000) + '"'
];
const options = [{}, { expand: true }, { expand: true, nodupes: true, noempty: true },
  { keepEscaping: true }, { keepQuotes: true }, { escapeInvalid: true }];
for (const pattern of patterns) for (const opts of options) {
  for (const method of ['compile', 'expand', 'stringify']) {
    if (original) assert.deepEqual(braces[method](pattern, opts), original[method](pattern, opts), `${method}: ${pattern}`);
    else braces[method](pattern, opts);
    checks++;
  }
  if (original) assert.deepEqual(braces(pattern, opts), original(pattern, opts));
  checks++;
}
for (const pattern of ['('.repeat(4000)+'x'+')'.repeat(4000), '{'.repeat(4000)+'x'+'}'.repeat(4000), '{1..3,'+'('.repeat(1000)]) {
  for (const method of ['parse','compile','expand','stringify','create']) reject(() => braces[method](pattern));
  reject(() => braces([pattern], { expand: true }));
}
const deep = () => { let n = { type: 'text', value: 'x' }; for (let i=0;i<4000;i++) n = { type: 'root', nodes: [n] }; return n; };
for (const method of ['compile', 'expand', 'stringify']) {
  reject(() => braces[method](deep()));
  reject(() => require(path.join(root, 'node_modules/braces/lib', method))(deep()));
  const cycle={ type:'root', nodes:[] }; cycle.nodes.push(cycle);
  reject(() => braces[method](cycle));
}
const parentCycle={type:'paren',nodes:[]}; parentCycle.parent=parentCycle;
reject(() => braces.expand({type:'root',nodes:[parentCycle]}));
const cyclic=[]; cyclic.push(cyclic);
reject(() => require(path.join(root,'node_modules/braces/lib/utils')).flatten(cyclic));
reject(() => braces.expand('{1..2}', {transform: () => cyclic}));
let nested='x'; for(let i=0;i<300;i++) nested=[nested];
reject(() => braces.expand('{1..2}', {transform: () => nested}));
for (const method of ['compile','expand','stringify']) {
  reject(() => braces[method]({type:'root',nodes:[{type:'text',value:nested}]}));
}
for (const key of ['step','rangeLimit']) reject(() => braces.expand('{1..2}',{[key]:nested}));
for (const method of ['compile','expand']) reject(() => braces[method]({type:'root',nodes:[],ranges:nested}));
reject(() => braces.expand({type:'root',nodes:[{type:'brace',open:true,close:true,nodes:[],commas:nested,ranges:0}]}));
const utilities=require(path.join(root,'node_modules/braces/lib/utils'));
reject(() => utilities.exceedsLimit('1','2',nested,1000));
reject(() => utilities.isInvalidBrace({type:'brace',commas:nested,ranges:0}));
reject(() => utilities.encloseBrace({type:'brace',commas:nested,ranges:0}));
const inherited=Object.assign(Object.create({rangeLimit:false}),{transform:v=>v});
assert.equal(braces.expand('{1..1001}',inherited).length,1001);checks++;
for (const method of ['compile','stringify']) {
  const dormant={type:'text',value:'x',nodes:[]};dormant.nodes.push(dormant);
  assert.equal(braces[method](dormant),'x');checks++;
}
const shared={type:'text',value:'x'};
assert.equal(braces.stringify({type:'root',nodes:[shared,shared]}),'xx'); checks++;
assert.equal(braces.compile({type:'root',nodes:[shared,shared]}),'xx'); checks++;
for (const method of ['compile', 'expand', 'stringify']) {
  const ast=braces.parse('a{b,c}d');
  if(original) assert.deepEqual(braces[method](ast),original[method](original.parse('a{b,c}d')));
  checks++;
}
assert.throws(() => braces.parse(null),TypeError); checks++;
assert.throws(() => braces.parse('x'.repeat(10001)),SyntaxError); checks++;
assert.throws(() => braces.expand('{1..1001}'), e => e instanceof RangeError && !e.code); checks++;
// Actual package aliases and both fast-glob installed option variants.
const mm=require(path.join(root,'node_modules/micromatch'));
for(const method of ['braces','braceExpand','parse']) reject(() => mm[method]('{'.repeat(4000)+'x'+'}'.repeat(4000)));
for(const opts of [{expand:true,nodupes:true},{expand:true,nodupes:true,keepEscaping:true}]) {
  assert.deepEqual(mm.braces('src/**/*.{ts,tsx}',opts),['src/**/*.ts','src/**/*.tsx']); checks++;
}
console.log(JSON.stringify({checks,ordinaryPatterns:patterns.length,optionVariants:options.length,upstreamParity:!!original,allPassed:true}));
