"""Bounded research only: original ESLint and exact Biome on synthetic files.

No production files are lint-fixed or changed. Full original configs stay active;
all native candidate rule severities follow the original control. A sample match
is evidence for that sample, never a universal equivalence assertion.
"""
from pathlib import Path
import json, subprocess, concurrent.futures, hashlib, time, urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
APP = ROOT / 'apps/vehicle-app'
BIOME = OUT / 'toolchain/node_modules/@biomejs/biome/bin/biome'
ESLINT = ROOT / 'node_modules/eslint/bin/eslint.js'
inventory = json.loads((OUT/'effective-configurations.json').read_text())
rules = next(x['rules'] for x in inventory['results'] if x['file'].endswith('src/app/page.tsx'))

# old rule: native candidate, deliberately valid/invalid source, virtual path.
# Unmapped controls are still executed; they are never silently dropped.
data = {
 'google-font-display': ('useGoogleFontDisplay', '<link href="https://fonts.googleapis.com/css2?family=Roboto&display=swap" />', '<link href="https://fonts.googleapis.com/css2?family=Roboto" />'),
 'google-font-preconnect': ('useGoogleFontPreconnect', '<link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />', '<link href="https://fonts.gstatic.com" />'),
 'inline-script-id': ('useInlineScriptId', 'import Script from "next/script"; export default function C(){return <Script id="ok">{"ok()"}</Script>}', 'import Script from "next/script"; export default function C(){return <Script>{"ok()"}</Script>}'),
 'next-script-for-ga': (None, '<div />', '<script src="https://www.google-analytics.com/analytics.js" />'),
 'no-assign-module-variable': (None, 'const moduleName = {};', 'const module = {};'),
 'no-async-client-component': ('noNextAsyncClientComponent', '"use client"; export default function C(){return <div/>}', '"use client"; export default async function C(){return <div/>}'),
 'no-before-interactive-script-outside-document': ('noBeforeInteractiveScriptOutsideDocument', 'import Script from "next/script"; export default function C(){return <Script src="https://example.com/a.js" strategy="afterInteractive"/>}', 'import Script from "next/script"; export default function C(){return <Script src="https://example.com/a.js" strategy="beforeInteractive"/>}', 'pages/index.tsx'),
 'no-css-tags': (None, '<div/>', '<link rel="stylesheet" href="/theme.css"/>'),
 'no-document-import-in-page': ('noDocumentImportInPage', 'import Head from "next/head"; export default function C(){return <Head/>}', 'import Document from "next/document"; export default function C(){return <Document/>}'),
 'no-duplicate-head': (None, 'import Document,{Head} from "next/document"; export default class C extends Document{render(){return <div><Head/></div>}}', 'import Document,{Head} from "next/document"; export default class C extends Document{render(){return <div><Head/><Head/></div>}}', 'pages/_document.tsx'),
 'no-head-element': ('noHeadElement', '<header/>', '<head/>', 'pages/index.tsx'),
 'no-head-import-in-document': ('noHeadImportInDocument', 'import { Head } from "next/document"; export default function C(){return <Head/>}', 'import Head from "next/head"; export default function C(){return <Head/>}', 'pages/_document.tsx'),
 'no-html-link-for-pages': (None, 'import Link from "next/link"; export default function C(){return <Link href="/">Home</Link>}', 'export default function C(){return <a href="/">Home</a>}'),
 'no-img-element': ('noImgElement', '<span/>', '<img alt="sample" src="/image.png"/>'),
 'no-page-custom-font': (None, '<div/>', '<link href="https://fonts.googleapis.com/css2?family=Roboto&display=swap" rel="stylesheet"/>', 'pages/index.tsx'),
 'no-script-component-in-head': (None, 'import Head from "next/head"; export default function C(){return <Head><title>ok</title></Head>}', 'import Head from "next/head"; import Script from "next/script"; export default function C(){return <Head><Script src="/a.js"/></Head>}'),
 'no-styled-jsx-in-document': (None, '<div/>', '<style jsx>{"body { color: red }"}</style>', 'pages/_document.tsx'),
 'no-sync-scripts': ('noSyncScripts', '<script async src="/a.js"/>', '<script src="/a.js"/>'),
 'no-title-in-document-head': (None, 'import { Head } from "next/document"; export default function C(){return <Head/>}', 'import { Head } from "next/document"; export default function C(){return <Head><title>bad</title></Head>}', 'pages/_document.tsx'),
 'no-typos': (None, 'export const getServerSideProps = async () => ({props:{}});', 'export const getServerSideProp = async () => ({props:{}});', 'pages/index.tsx'),
 'no-unwanted-polyfillio': ('noUnwantedPolyfillio', '<script async src="https://example.com/s.js"/>', '<script async src="https://polyfill.io/v3/polyfill.min.js?features=Array.prototype.copyWithin"/>'),
 'import/no-anonymous-default-export': ('noDefaultExport', 'const config={}; export default config;', 'export default {};'),
 'jsx-a11y/alt-text': ('useAltText', '<img alt="sample" src="/a.png"/>', '<img src="/a.png"/>'),
 'jsx-a11y/aria-props': ('useValidAriaProps', '<div aria-label="ok"/>', '<div aria-labl="bad"/>'),
 'jsx-a11y/aria-proptypes': ('useValidAriaValues', '<div aria-hidden="true"/>', '<div aria-hidden="sometimes"/>'),
 'jsx-a11y/aria-unsupported-elements': ('noAriaUnsupportedElements', '<meta name="ok"/>', '<meta aria-label="bad"/>'),
 'jsx-a11y/role-has-required-aria-props': ('useAriaPropsForRole', '<div role="checkbox" aria-checked="false"/>', '<div role="checkbox"/>'),
 'jsx-a11y/role-supports-aria-props': ('useAriaPropsSupportedByRole', '<div role="button" aria-label="ok"/>', '<div role="button" aria-checked="true"/>'),
 'react-hooks/exhaustive-deps': ('useExhaustiveDependencies', 'import {useEffect} from "react"; export function C({value}){useEffect(()=>{console.log(value)},[value]);return null;}', 'import {useEffect} from "react"; export function C({value}){useEffect(()=>{console.log(value)},[]);return null;}'),
 'react-hooks/rules-of-hooks': ('useHookAtTopLevel', 'import {useState} from "react"; export function C({flag}){const [n]=useState(0);return <div>{n}</div>}', 'import {useState} from "react"; export function C({flag}){if(flag){useState(0)}return null;}'),
 'react/display-name': (None, 'import React from "react"; const C=React.memo(function C(){return <div/>});', 'import React from "react"; const C=React.memo(()=> <div/>);'),
 'react/jsx-key': ('useJsxKeyInIterable', 'export function C(){return [1,2].map(n=><span key={n}>{n}</span>)}', 'export function C(){return [1,2].map(n=><span>{n}</span>)}'),
 'react/jsx-no-comment-textnodes': ('noCommentText', '<div>{/* okay */}</div>', '<div>// bad comment</div>'),
 'react/jsx-no-duplicate-props': ('noDuplicateJsxProps', '<div id="a"/>', '<div id="a" id="b"/>'),
 'react/jsx-no-undef': ('noUndeclaredVariables', 'function C(){return <div/>}', 'function C(){return <UndefinedComponent/>}'),
 'react/jsx-uses-react': (None, 'import React from "react"; export function C(){return <div/>}', 'import React from "react"; export function C(){return <div/>}'),
 'react/jsx-uses-vars': (None, 'function Child(){return <div/>} export function C(){return <Child/>}', 'function Child(){return <div/>} export function C(){return <Child/>}'),
 'react/no-children-prop': ('noChildrenProp', '<div>ok</div>', '<div children="bad"/>'),
 'react/no-danger-with-children': ('noDangerouslySetInnerHtmlWithChildren', '<div dangerouslySetInnerHTML={{__html:"ok"}}/>', '<div dangerouslySetInnerHTML={{__html:"bad"}}>child</div>'),
 'react/no-deprecated': ('noDeprecatedImports', 'import React from "react"; class C extends React.Component{componentDidMount(){} render(){return <div/>}}', 'import React from "react"; class C extends React.Component{componentWillMount(){} render(){return <div/>}}'),
 'react/no-direct-mutation-state': (None, 'import React from "react"; class C extends React.Component{update(){this.setState({n:1})} render(){return <div/>}}', 'import React from "react"; class C extends React.Component{update(){this.state.n=1} render(){return <div/>}}'),
 'react/no-find-dom-node': (None, 'import ReactDOM from "react-dom"; const n=document.getElementById("x");', 'import ReactDOM from "react-dom"; const n=ReactDOM.findDOMNode(this);'),
 'react/no-is-mounted': (None, 'import React from "react"; class C extends React.Component{check(){return true} render(){return <div/>}}', 'import React from "react"; class C extends React.Component{check(){return this.isMounted()} render(){return <div/>}}'),
 'react/no-render-return-value': ('noRenderReturnValue', 'import ReactDOM from "react-dom"; ReactDOM.render(<div/>,document.body);', 'import ReactDOM from "react-dom"; const result=ReactDOM.render(<div/>,document.body);'),
 'react/no-string-refs': ('noReactStringRefs', '<div/>', '<div ref="legacy"/>'),
 'react/no-unescaped-entities': (None, '<div>don&apos;t</div>', "<div>don't</div>"),
 'react/require-render-return': (None, 'import React from "react"; class C extends React.Component{render(){return <div/>}}', 'import React from "react"; class C extends React.Component{render(){<div/>}}'),
}
data = {('@next/next/'+k if '/' not in k else k):v for k,v in data.items()}
assert set(data) == set(rules), (set(data)^set(rules))
schema_path=ROOT/'audit-results/tailwind4-biome-feasibility/raw/biome-2.5.15-schema.json'
if not schema_path.exists():
    schema_path.parent.mkdir(parents=True,exist_ok=True)
    schema_path.write_bytes(urllib.request.urlopen('https://biomejs.dev/schemas/2.5.15/schema.json',timeout=30).read())
expected=json.loads((OUT/'pinned-schema-proof.json').read_text())['sha256']
assert hashlib.sha256(schema_path.read_bytes()).hexdigest()==expected,'Pinned schema changed: stop rather than silently use new options'
schema=json.loads(schema_path.read_text())
defs=schema.get('$defs',schema.get('definitions'))
groups=['A11y','Complexity','Correctness','Nursery','Performance','Security','Style','Suspicious']
native_groups={rule:g[0].lower()+g[1:] for g in groups for rule in defs[g]['properties'] if rule!='preset'}
config=json.loads((APP/'biome.json').read_text())
(OUT/'configuration-before-probe.json').write_text(json.dumps(config,indent=2)+'\n')
candidate_rules={'preset':'none'}
for old, info in data.items():
    native=info[0]
    if native:
        assert native in native_groups,native
        severity=rules[old][0]
        candidate_rules.setdefault(native_groups[native],{})[native]='error' if severity in (2,'error') else 'warn'
config['linter']['rules']=candidate_rules
config['formatter']={'enabled':False}
config['assist']={'enabled':False}
config['vcs']={'enabled':False}
(APP/'biome.json').write_text(json.dumps(config,indent=2)+'\n')
(OUT/'native-candidate-biome.json').write_text(json.dumps(config,indent=2)+'\n')

cases=[]
for i,(rule,info) in enumerate(data.items()):
    native,good,bad,*filepath=info
    virtual=filepath[0] if filepath else 'src/app/parity-probe.tsx'
    for kind,source in [('positive',good),('negative',bad)]:
        cases.append({'id':f'{i:02d}-{kind}','rule':rule,'native':native,'kind':kind,'source':source,'virtualPath':virtual})
# Cross-extension parsing/scope and an important custom Next Image option.
for ext in ['ts','tsx','js','cjs','mjs']:
    source='const {useState}=require("react"); function C({flag}){if(flag){useState(0)}return null;} module.exports=C;' if ext=='cjs' else 'import {useState} from "react"; export function C({flag}){if(flag){useState(0)}return null;}'
    cases.append({'id':'extension-'+ext,'rule':'react-hooks/rules-of-hooks','native':'useHookAtTopLevel','kind':'negative','source':source,'virtualPath':'src/utils/parity-probe.'+ext})
cases.append({'id':'custom-image-negative','rule':'jsx-a11y/alt-text','native':'useAltText','kind':'negative','source':'import Image from "next/image"; export function C(){return <Image src="/a.png" width={10} height={10}/>}','virtualPath':'src/app/parity-probe.tsx'})
cases.append({'id':'effect-extra-dependency-positive','rule':'react-hooks/exhaustive-deps','native':'useExhaustiveDependencies','kind':'positive','source':'import {useEffect} from "react"; export function C({value}){useEffect(()=>{console.log("mounted")},[value]);return null;}','virtualPath':'src/app/parity-probe.tsx'})
(OUT/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n')
for case in cases:
    fixture=OUT/'cases'/case['id']/case['virtualPath']
    fixture.parent.mkdir(parents=True,exist_ok=True)
    fixture.write_text(case['source']+'\n',encoding='utf-8')

def run(case):
    path=str(OUT/'cases'/case['id']/case['virtualPath'])
    commands={
        'eslint':['node',str(ESLINT),'--config',str(APP/'.eslintrc.json'),'--stdin','--stdin-filename',path,'--format','json'],
        'biome':['node',str(BIOME),'lint','--config-path',str(APP/'biome.json'),path,'--reporter=json'],
    }
    results={}
    for tool,args in commands.items():
        start=time.monotonic()
        r=subprocess.run(args,cwd=APP,input=case['source'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
        try: payload=json.loads(r.stdout)
        except json.JSONDecodeError: payload=None
        if tool=='eslint':
            diagnostics=payload[0]['messages'] if payload else []
            matched=[d for d in diagnostics if d.get('ruleId')==case['rule']]
        else:
            diagnostics=payload.get('diagnostics',[]) if isinstance(payload,dict) else []
            matched=[d for d in diagnostics if case['native'] and d.get('category','').endswith('/'+case['native'])]
        results[tool]={'exitCode':r.returncode,'durationSeconds':round(time.monotonic()-start,3),'targetDiagnostics':matched,'allDiagnostics':diagnostics,'stderr':r.stderr,'rawStdout':r.stdout if payload is None else None}
    return {**case,'results':results}

if __name__=='__main__':
    outputs=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures={executor.submit(run,c):c for c in cases}
        for future in concurrent.futures.as_completed(futures):
            result=future.result();outputs.append(result)
            if len(outputs)%16==0: print(f'{len(outputs)}/{len(cases)} paired cases completed',flush=True)
    outputs.sort(key=lambda x:x['id'])
    (OUT/'diagnostics.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2)+'\n')
    print('complete',len(outputs),flush=True)
