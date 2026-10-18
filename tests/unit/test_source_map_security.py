"""Validate the installed shared source-map boundary and legitimate CSS maps."""
import subprocess
from pathlib import Path


def test_indexed_source_maps_reject_amplifying_offsets_and_preserve_valid_maps():
    root = Path(__file__).resolve().parents[2]
    script = r"""
const assert=require('assert'),path=require('path');
const entry=require.resolve('source-map-js');
const postcssEntries=[require.resolve('postcss'),require.resolve('postcss',{paths:[path.dirname(require.resolve('next/package.json'))]})];
// Next's production PostCSS and the ordinary PostCSS caller must resolve
// the same patched implementation, rather than leaving a nested old copy.
for(const module of postcssEntries){
 const consumer=require.resolve('source-map-js',{paths:[path.dirname(module)]});
 assert.equal(consumer,entry);
}
assert.equal(require('source-map-js/package.json').version,'1.2.2');
const {SourceMapConsumer,SourceMapGenerator,SourceNode}=require('source-map-js');
const flat={version:3,sources:['a.js'],names:[],mappings:'AAAA',sourcesContent:['x']};
const indexed=(line,column=0,map=flat)=>({version:3,sections:[{offset:{line,column},map}]});
for(const bad of [1000000000,10000001,Infinity,NaN,-1,.5,'2',null]){
 assert.throws(()=>new SourceMapConsumer(indexed(bad)),/offset/);
}
for(const bad of [Infinity,NaN,-1,.5,'2',null]){
 assert.throws(()=>new SourceMapConsumer(indexed(0,bad)),/offset/);
}
// Each nested section is individually in range, but their total amplifies.
assert.throws(()=>new SourceMapConsumer(indexed(6000000,0,indexed(6000000))),/nested sections/);
assert.throws(()=>new SourceMapConsumer(JSON.stringify(indexed(1000000000))),/offset/);
const valid=new SourceMapConsumer(indexed(2));
assert.deepEqual(valid.originalPositionFor({line:3,column:1}),{source:'a.js',line:1,column:0,name:null});
assert.equal(SourceMapGenerator.fromSourceMap(new SourceMapConsumer(flat)).toJSON().mappings,'AAAA');
assert.equal(SourceNode.fromStringWithSourceMap('\n\nx',valid).toString(),'\n\nx');
// No generated code remains before an otherwise legal distant mapping.
// This must stay bounded rather than walking thousands of empty lines.
assert.equal(SourceNode.fromStringWithSourceMap('x',new SourceMapConsumer(indexed(10000000))).toString(),'x');
for(const module of postcssEntries){
 const postcss=require(module);
 const css='a { color: red; }';
 const result=postcss([]).process(css,{from:'a.css',to:'out.css',map:{inline:false}});
 assert(result.css.startsWith(css));
 const map=new SourceMapConsumer(result.map.toJSON());
 assert.equal(map.originalPositionFor({line:1,column:0}).source,'a.css');
 const reused=postcss([]).process(result.css,{from:'out.css',to:'again.css',map:{prev:result.map.toJSON(),inline:false}});
 assert(reused.css.startsWith(css));
 assert.equal(new SourceMapConsumer(reused.map.toJSON()).originalPositionFor({line:1,column:0}).source,'a.css');
}
console.log('PASS: shared patched boundary, malformed/nested/string maps, SourceNode and both PostCSS paths');
"""
    subprocess.run(["node", "-e", script], cwd=root, check=True, timeout=15)
