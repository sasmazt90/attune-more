import re, json
md=open('docs/oneriler.md').read()
IDS={'Göz altı torbası':'eyeBags','Göz altı morluğu':'darkCircles','Göz kapağı düşüklüğü':'hoodedEyelids','Göz kuyruğu düşüklüğü':'downturnedCorners',
 'Kaz ayakları':'crowsFeet','Alın çizgileri':'foreheadLines','Sivilce':'acne','Akne izi':'acneMarks','Melazma':'melasma','Ben':'mole',
 'Türü belirlenemeyen leke':'spots','Kızarıklık':'redness','Rozasea benzeri kızarıklık':'rosacea','Dudakta uçuk':'coldSore'}
out={}; notes={}
for sec in re.split(r'\n### ',md)[1:]:
    title=sec.split('\n',1)[0].strip(); fid=IDS[title]
    body=sec.split('\n## ')[0]
    pre=[l for l in body.split('\n')[1:] if l.strip() and not l.startswith('|')]
    if pre: notes[fid]=pre[0].strip()
    rows=[[c.strip() for c in l.strip().strip('|').split('|')] for l in body.split('\n') if l.startswith('|')][2:]
    bands=[]
    for r in rows:
        if fid=='mole': bands.append(dict(label=r[0],habit=r[1])); continue
        if fid=='coldSore': bands.append(dict(label='',ingredients=r[0],usage=r[1],habit=r[2])); continue
        bands.append(dict(label=r[0],ingredients=r[1],morning=r[2],evening=r[3],habit=r[4]))
    out[fid]=bands
json.dump(dict(bands=out,notes=notes),open('recs.json','w'),ensure_ascii=False,indent=1)
print({k:len(v) for k,v in out.items()}); print(notes)
