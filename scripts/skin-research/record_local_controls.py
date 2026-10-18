"""Actually viewed native source control boards; pixel and photo claims differ."""
import json
from expanded_sources import OUT,sha,write
DRY_NEGATIVE={1,2,8,9,11,17,19,20,21,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,43,44,113,119,122,127}

def main():
 folder=OUT/'local-control-review';path=folder/'dry-negative-index.json';rows=json.loads(path.read_text('utf8'));result=[]
 for r in rows:
  i=r['reviewIndex'];result.append(dict(reviewIndex=i,sha256=r['sha256'],source=r['source'],group=r['group'],split=r['split'],photoAppearance='negative-visible-flaking' if i in DRY_NEGATIVE else 'cosmetic-peel-confounder' if i==128 else 'provenance-unresolved',eligibleForVisibleFlakeNegative=i in DRY_NEGATIVE,rightsEligible=i!=6,rightsReason='VISIBLE_SUPPLIEDCONRAGH_KATHLEEN_NOTICE' if i==6 else None,explicitPixelNegativeNeedsPreparedVisibleSkinScope=True,physicalMoistureTruth=False,sourceImageWidth=r['width'],sourceImageHeight=r['height']))
 write('local-control-review/decisions.json',dict(rows=result,indexSHA256=sha(path),viewedBoards={f'dry-negative-{i}.jpg':sha(folder/f'dry-negative-{i}.jpg') for i in range(6)},engineeringLabels=True,expertLabels=False,predictionsUsed=False,independentFinal=False,cosmeticPeelIsNotNaturalFlaking=True));print('33 visible-flaking negative photos, one rights notice, one cosmetic-peel confounder')

if __name__=='__main__':main()
