"""Record explicitly viewed blind-sheet decisions; never auto-label unseen items."""
import argparse
from verifier_v4_round import OUT,read,sha,atomic,status,CATEGORIES

def record(page,codes):
 manifest=read(OUT/'review-list.json');items=manifest['items'][(page-1)*32:page*32];codes=codes.split()
 assert len(codes)==len(items),(len(codes),len(items));assert all(c in CATEGORIES for c in codes)
 path=OUT/'review-decisions.json';data=read(path) if path.exists() else dict(reviewer='Codex AI visual engineering review; not expert/dermatologist',blind=True,categories=CATEGORIES,decisions={},pages={})
 assert str(page) not in data['pages'],'PAGE_ALREADY_REVIEWED'
 image=OUT/'blind-sheets'/f'page-{page:03}.jpg'
 for item,c in zip(items,codes):
  assert item['rid'] not in data['decisions']
  data['decisions'][item['rid']]=dict(cat=c,reason=CATEGORIES[c],page=page,reviewLevel='AI engineering',evidence='tight/native detail, wider context and full source in blind sheet')
 data['pages'][str(page)]=dict(sheetSHA256=sha(image),count=len(items));atomic('review-decisions.json',data);status('blind visual review',len(data['decisions']),manifest['n'],pagesReviewed=len(data['pages']));print('REVIEWED',len(data['decisions']))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('page',type=int);p.add_argument('codes');a=p.parse_args();record(a.page,a.codes)