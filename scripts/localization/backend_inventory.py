"""Inventory translated backend presentation sources without importing providers."""
import ast
import hashlib
import json
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[2]
FILES = ('main.py','mental_provider.py','care_provider.py','conversation_control.py')

def inventory():
    rows = {}
    for path in (ROOT/'services/core-api').glob('*.py'):
        relative = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text('utf-8'))
        selected = list(ast.walk(tree)) if path.name in FILES else []
        explicit_display = set()
        # Cover health-module response fields and explicit API/user errors too.
        fields = {'nameTr','label','title','description','note','reason','message','detail','recommendation','hint','warning','warnings','baselineDiffNote','limitation','displayMessage','summaryText','sourceBadge','providerLabel','emergencyContact','clinicalDisclaimer','specialty','locationLabel','suggestedAction','disclaimer','handoffNote'}
        for candidate in ast.walk(tree):
            if isinstance(candidate,ast.Dict):
                for key,value in zip(candidate.keys,candidate.values):
                    if isinstance(key,ast.Constant) and key.value in fields:
                        nodes=list(ast.walk(value));explicit_display.update(map(id,nodes));selected.extend(nodes)
        if path.name not in FILES:
            for candidate in ast.walk(tree):
                outputs=[]
                if isinstance(candidate,ast.Dict):
                    outputs=[v for k,v in zip(candidate.keys,candidate.values) if isinstance(k,ast.Constant) and k.value in fields]
                if isinstance(candidate,ast.Call) and isinstance(candidate.func,ast.Name) and candidate.func.id in ('HTTPException','ValueError'):
                    outputs+=candidate.args+[kw.value for kw in candidate.keywords if kw.arg=='detail']
                for output in outputs:selected.extend(ast.walk(output))
        for node in selected:
            source = None
            if isinstance(node,ast.Constant) and isinstance(node.value,str):
                source = node.value
            elif isinstance(node,ast.JoinedStr):
                fields = iter(range(100))
                source = ''.join(part.value if isinstance(part,ast.Constant) else '{'+str(next(fields))+'}' for part in node.values)
            if not source or not (re.search('[çğıöşüÇĞİÖŞÜ]',source) or id(node) in explicit_display and re.search(r'[A-Za-z]',source)):
                continue
            source = ' '.join(source.split())
            key = hashlib.sha256(source.encode()).hexdigest()[:16]
            row = rows.setdefault(key,{'id':key,'tr':source,'references':[]})
            row['references'].append({'file':relative,'line':node.lineno,'kind':type(node).__name__})
    return list(rows.values())

if __name__ == '__main__':
    print(json.dumps(inventory(),ensure_ascii=False,indent=2))
