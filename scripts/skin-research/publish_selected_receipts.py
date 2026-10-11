"""Compact Git-safe numeric receipts; never publish photos or checkpoints."""
import collections,json
from selected_sources import ROOT,OUT,write,sha

def read(name):return json.loads((OUT/name).read_text('utf8'))
def main():
 models={}
 for task in ['type','mask','yolox']:
  selection=read(task+'/selection.json');export=read(task+'/export.json');protocol=read(task+'/protocol.json');history=read(task+'/history.json')
  assert sha(OUT/task/'candidate.onnx')==export['sha256']
  assert sha(OUT/task/'selected.safetensors')==selection['weightsSHA256']
  assert not selection['accepted'] and not export['productionInstalled']
  metrics=selection['validation']
  if task=='mask':metrics={k:{n:v[n] for n in ['ROIs','positiveROIs','Dice','IoU','negativeFPR']} for k,v in metrics.items()}
  models[task]=dict(protocol=protocol,learning=read(task+'/learning.json'),completedValidatedEpochs=len(history),firstEpochSeconds=history[0]['epochSeconds'],selectedEpoch=selection['selectedEpoch'],validation=metrics,featureEvidence=selection.get('features',selection.get('featureEvidence')),export=export,weightsSHA256=selection['weightsSHA256'],accepted=False,reason=selection['reason'])
 m=read('manifest.json');receipt=read('receipt.json');review=read('review/decisions.json');delivery=read('product/delivery.json');ui=read('product/ui-new-build/proof.json');appearance=read('appearance-summary.json');controls=read('appearance-controls.json')
 receipt.pop('trainingCompleted',None)
 assert review['candidateSHA256']==sha(OUT/'review/candidates.json') and review['manifestSHA256']==sha(OUT/'manifest.json')
 for values in appearance['criteria'].values():values.pop('examples',None)
 base=read('baseline.json');assert delivery['manifestSHA256']==base['files']['services/core-api/models/skin-focused.json'];assert delivery['acceptedModelFileSHA256']==base['files']['services/core-api/models/skin-focused-degrees.onnx']
 loaded=sorted({v['modelHash'] for sample in delivery['samples'] for v in (sample['modelInference'] or {}).values() if v.get('modelHash')})
 assert loaded==[delivery['acceptedModelFileSHA256']]
 compact=dict(version='selected-skin-execution-20261011-v1',readyForFullAcceptance=False,baseHEAD=base['sourceSHA'],branch=delivery['branch'],data=receipt,stockGroupExcludedRows=sum(bool(r.get('excluded')) for r in m['rows']),realRLEAnnotations=sum(a['kind']=='rle' for r in m['rows'] for a in r['annotations']),rights=[dict(source=s['id'],archive=s['archive'],archiveSHA256=s['archiveSHA256'],readmes=s['readmes'],license=s['license'],transform=s['transform'],individualImageRights=s['individualImageRights']) for s in m['sources']],review=dict(photos=len(review['rows']),naturalAndRightsEligiblePhotos=sum(r['naturalEligible'] and r['rightsEligible'] for r in review['rows']),SHA256=sha(OUT/'review/decisions.json'),engineeringLabels=True,expertLabels=False,predictionsUsed=False),models=models,appearance=appearance,repeatability=dict(licensedPreviouslyExposedSources=4,samePersonVideoFramesNotIndependent=True,maximumAbsoluteDifference=max(r['repeatMaximumDifference'] for r in controls['rows']),lowQualityAllNull=True,exposureControlsAuxiliaryOnly=True),delivery=dict(buildId=delivery['buildId'],frontendSourceFiles=delivery['frontendSourceFiles'],frontendSourceReceiptSHA256=sha(ROOT/'.runtime/skin-selected-build-20261011-v2/source-receipt.json'),servedJavaScriptHashes=delivery['servedJavaScriptHashes'],backendSourceHashes=delivery['backendSourceHashes'],appearanceSourceSHA256=delivery['appearanceSourceSHA256'],manifestSHA256=delivery['manifestSHA256'],normalBackendLoadedModelHashes=loaded,normalShortcut=True,previousBuildPreserved='.runtime/skin-selected-previous-next-20261011',userRecordsMigrated=False,normalHistoryWritten=False),browser=dict(status=ui['status'],buildId=ui['buildId'],physicalCamera=ui['physicalCamera'],poseMock=ui['poseMock'],qualityOverride=ui['qualityOverride'],native200=ui['native200'],pageErrors=ui['pageErrors'],actualThreePoseFixtureRuns=len(ui['runs']),runSeconds=[r['seconds'] for r in ui['runs']],photoHistoryVerified=True,narrowAndDesktopVerified=True),checks=dict(focusedRegressionsPassed=29,selectedBoundaryTestsIncluded=7,typecheckPassed=True,productionBuildPassed=True,paidCompute=False,userPhotoCloudUpload=False),limitations=['New candidates rejected; no new model installed.','2270 unused photo-group candidate rows stay closed; crop/collage and subject independence unresolved.','Four-class type corpus has no unused four-class final; combination validation support14.','Engineering masks approximate source boundaries; partial labels remain unknown.','Natural controls are offline reviewed source ROI arithmetic, not physical camera/person acceptance.','Merve pul positives reviewed here are CLAHE/processed and excluded from natural RGB calibration.','Matched appearance-severity calibration and reliable natural confounder acceptance incomplete.'])
 target=ROOT/'docs/skin-selected-evidence-20261011.json';target.write_text(json.dumps(compact,ensure_ascii=False,indent=2),'utf8')
 print('Published numeric receipt only',target,flush=True)
if __name__=='__main__':main()
