import { marked, type Token, type Tokens } from 'marked';
/** Parse Markdown, walk its AST, emit text only. Never render or execute HTML.
 * Regex below only normalizes whitespace/entities AFTER structural parsing.
 */
export function spokenText(input: string): string {
  const walk=(tokens:Token[]):string=>tokens.map(token=>{
    if(token.type==='html' || token.type==='def' || token.type==='hr')return '';
    if(token.type==='space' || token.type==='br')return '\n';
    if(token.type==='list'){const list=token as Tokens.List;return list.items.map((item,i)=>`${list.ordered?`${Number(list.start)+i}. `:''}${walk(item.tokens)}`).join('\n')+'\n';}
    if(token.type==='table'){const table=token as Tokens.Table;return [table.header,...table.rows].map(row=>row.map(cell=>walk(cell.tokens)).join(' · ')).join('\n')+'\n';}
    if('tokens' in token && token.tokens) return walk(token.tokens)+(token.type==='paragraph'||token.type==='heading'||token.type==='blockquote'?'\n':'');
    return 'text' in token?token.text:'';
  }).join('');
  return walk(marked.lexer(input,{gfm:true})).replace(/&#(x[0-9a-f]+|[0-9]+);/gi,(_,code)=>{
    const value=code[0].toLowerCase()==='x'?parseInt(code.slice(1),16):parseInt(code,10);
    return value>0&&value<=0x10ffff&&!(value>=0xd800&&value<=0xdfff)?String.fromCodePoint(value):'';
  }).replace(/&(amp|lt|gt|quot|apos|nbsp);/g,(_,name:string)=>(({amp:'&',lt:'<',gt:'>',quot:'"',apos:"'",nbsp:' '} as Record<string,string>)[name]||'')).replace(/[ \t]+/g,' ').replace(/\n{2,}/g,'\n').trim();
}
