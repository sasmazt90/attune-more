const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const app = path.join(root, 'apps/vehicle-app');
const { ESLint } = require(path.join(root, 'node_modules/eslint'));
const lint = new ESLint({ cwd: app });
const baseHead = 'f8f08d98cf23eb23c5a171b5b50411364d79adf6';
const files = execFileSync('git', ['ls-tree', '-r', '--name-only', baseHead], { cwd: root, encoding: 'utf8' }).trim().split('\n').filter(f => /\.(?:ts|tsx|js|cjs|mjs)$/.test(f));
const probes = ['src/app/parity-probe.ts', 'src/app/parity-probe.tsx', 'src/app/parity-probe.js', 'src/app/parity-probe.cjs', 'src/app/parity-probe.mjs', 'src/components/parity.tsx', 'src/utils/parity.ts', 'src/utils/parity.worker.ts', 'src/data/parity.ts', 'pages/_document.tsx', 'pages/api/parity.ts', 'tests/parity.tsx'];
const active = value => ![0, 'off'].includes(Array.isArray(value) ? value[0] : value);
(async () => {
  const results = [];
  for (const item of [...files.map(f => ({file:f, tracked:true})), ...probes.map(f => ({file:'apps/vehicle-app/'+f, tracked:false}))]) {
    const absolute = path.join(root, item.file);
    try {
      const config = await lint.calculateConfigForFile(absolute);
      const rules = Object.fromEntries(Object.entries(config.rules || {}).filter(([,v]) => active(v)).sort(([a],[b]) => a.localeCompare(b)));
      results.push({...item, ignored:await lint.isPathIgnored(absolute), activeCount:Object.keys(rules).length, nextCount:Object.keys(rules).filter(r=>r.startsWith('@next/')).length, rules, config, rulesHash:crypto.createHash('sha256').update(JSON.stringify(rules)).digest('hex')});
    } catch (error) { results.push({...item, error:String(error.message)}); }
  }
  const nextConstants = require(path.join(root,'node_modules/next/dist/lib/constants'));
  const summary = {baseHead, sourceHead:execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(), nextLintDefaultDirectories:nextConstants.ESLINT_DEFAULT_DIRS, trackedFiles:files.length, results};
  fs.writeFileSync(path.join(__dirname,'effective-configurations.json'),JSON.stringify(summary,null,2)+'\n');
  console.log(JSON.stringify(results.map(({file,tracked,ignored,activeCount,nextCount,rulesHash,error})=>({file,tracked,ignored,activeCount,nextCount,rulesHash,error})),null,2));
})();
