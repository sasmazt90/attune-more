from pathlib import Path
import json, collections

OUT=Path(__file__).resolve().parent
inventory=json.loads((OUT/'effective-configurations.json').read_text())
rules=next(x['rules'] for x in inventory['results'] if x['file'].endswith('src/app/page.tsx'))
diagnostics=json.loads((OUT/'diagnostics.json').read_text())
assert len(rules)==47 and len(diagnostics)==101
assert all(v['rawStdout'] is None for x in diagnostics for v in x['results'].values())
assert not any(d.get('category')=='parse' for x in diagnostics for d in x['results']['biome']['allDiagnostics'])

differences={
 'import/no-anonymous-default-export':'noDefaultExport forbids even a named default export. Positive old target 0 / candidate 1; no anonymous-only option in pinned schema.',
 'jsx-a11y/alt-text':'Builtin img sample matches. Original options elements=[img], img=[Image] are not expressible in pinned UseAltTextOptions (empty object); custom Next Image negative old=1 / candidate=0.',
 'react-hooks/exhaustive-deps':'Missing dependency sample matches. Extra useEffect dependency is valid under original but candidate reports it. Pinned candidate reportUnnecessaryDependencies default and hook-specific semantics require further parity; not accepted.',
 'react-hooks/rules-of-hooks':'Conditional hook negative matches for TS/TSX/JS/CJS/MJS, with equal error severity/exit. Limited samples do not prove all hook order/alias/async behavior.',
 '@next/next/no-document-import-in-page':'Native rule exists; App Router-shaped test is missed. A separate rooted research project catches pages/test.tsx but misses src/app/page.tsx. Scope parity not proven.',
 '@next/next/no-head-element':'Native rule exists but Windows pages-shaped negative is missed, including rooted path control. Filename/project-root behavior remains unresolved; no Linux equivalence claim.',
 'react/no-deprecated':'noDeprecatedImports checks imports, not React class lifecycle deprecation; componentWillMount negative old=1 / candidate=0.',
 'react/jsx-no-undef':'noUndeclaredVariables detects the sample but has a broader symbol/type scope; full JSX resolution parity not proven.',
 'react/jsx-uses-react':'ESLint bookkeeping marks React references; it does not independently emit an invalid-source diagnostic. Candidate equivalence is not proven and this active rule is not waived.',
 'react/jsx-uses-vars':'ESLint bookkeeping marks JSX component references; it does not independently emit an invalid-source diagnostic. Candidate equivalence is not proven and this active rule is not waived.',
}
rows=[]
for rule,options in rules.items():
    pos=next(x for x in diagnostics if x['rule']==rule and x['id'][:2].isdigit() and x['kind']=='positive')
    neg=next(x for x in diagnostics if x['rule']==rule and x['id'][:2].isdigit() and x['kind']=='negative')
    native=neg['native']
    counts=lambda x:{k:{'targetDiagnostics':len(v['targetDiagnostics']),'exitCode':v['exitCode']} for k,v in x['results'].items()}
    p,n=counts(pos),counts(neg)
    if 'jsx-uses-' in rule: result='BOOKKEEPING_NOT_PROVEN'
    elif not native: result='NO_NATIVE_EQUIVALENT'
    elif n['biome']['targetDiagnostics']==0:result='NEGATIVE_MISSED'
    elif p['biome']['targetDiagnostics']>0 or rule in ['jsx-a11y/alt-text','react-hooks/exhaustive-deps']:result='BEHAVIOR_OPTIONS_DIFFERENCE'
    else:result='SAMPLE_MATCH_ONLY_NOT_FULL_PARITY'
    difference=differences.get(rule,'No native candidate found in pinned schema/migration; original control retained.' if not native else 'Positive/negative sample and severity match only; complete options/path/edge-case equivalence not demonstrated.')
    if rule=='@next/next/next-script-for-ga':difference+=' Global candidate exit 1 comes from the distinct noSyncScripts check, not GA-specific coverage.'
    rows.append({'rule':rule,'severity':options[0],'options':options[1:],'scope':'S1-S5; original configured app files and exact extension config probes; path-sensitive cases listed individually','nativeCandidate':native,'difference':difference,'positiveCase':pos['id'],'negativeCase':neg['id'],'positive':p,'negative':n,'result':result})
    if rule not in ['react/jsx-uses-react','react/jsx-uses-vars']:
        assert n['eslint']['targetDiagnostics']>0,rule
summary={'decision':'NO-GO','baseHead':inventory['baseHead'],'activeRules':47,'nextRules':21,'nativeNextMigrationMappings':11,'unmappedNextControls':10,'pairedCases':101,'toolExecutions':202,'originalNegativeControlsTriggered':45,'bookkeepingControlsNotIndependentlyDiagnostic':2,'resultCounts':dict(collections.Counter(r['result'] for r in rows)),'rows':rows,'skippedGateReason':'Mandatory lint parity failed; no Tailwind migration/removal of original lint/full regression/CSS visual acceptance.', 'newPaidCalls':0,'physicalMicrophoneCapture':0,'adminStatus':'PENDING_ADMIN_EVIDENCE'}
(OUT/'decision-data.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
table=['## Tüm aktif kontrollerin eşdeğerlik tablosu','',
       'S1–S5: TS, TSX, JS, CJS, MJS etkili konfigürasyonları. Uygulama dizinlerinin ayrıntısı effective-configurations.json içindedir. Tüm satırlar eski severity/options değerlerini korur; kapsamı olmayan repo dışı dosyalara yeni koruma varmış gibi yaklaşılmaz.',
       '', 'P/N sütunları hedef tanı sayısı **ESLint/Biome**; exit sütunu gerçek süreç çıkışı **ESLint/Biome**, P ve N ayrı. Warning tanıları exit 0 dönebilir. Başka bir kuralın süreci başarısız yapması hedef kontrolün eşdeğerliği değildir.', '',
       '| Eski kural | Severity / options | Biome adayı | P; N hedef tanısı | P; N exit | Sonuç / fark |',
       '|---|---|---|---|---|---|']
for r in rows:
    p,n=r['positive'],r['negative']
    target=f"{p['eslint']['targetDiagnostics']}/{p['biome']['targetDiagnostics']}; {n['eslint']['targetDiagnostics']}/{n['biome']['targetDiagnostics']}"
    exits=f"{p['eslint']['exitCode']}/{p['biome']['exitCode']}; {n['eslint']['exitCode']}/{n['biome']['exitCode']}"
    opts=json.dumps(r['options'],ensure_ascii=False,separators=(',',':'))
    table.append(f"| `{r['rule']}` | `{r['severity']}` / `{opts}` | `{r['nativeCandidate'] or 'none'}` | {target} | {exits} | **{r['result']}**. {r['difference']} [P](cases/{r['positiveCase']}/{next(x['virtualPath'] for x in diagnostics if x['id']==r['positiveCase'])}) / [N](cases/{r['negativeCase']}/{next(x['virtualPath'] for x in diagnostics if x['id']==r['negativeCase'])}) |")
(OUT/'rule-table.md').write_text('\n'.join(table)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='rows'},ensure_ascii=False))
