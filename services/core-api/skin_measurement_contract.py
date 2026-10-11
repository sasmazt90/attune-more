"""Explicit availability/coverage receipt without changing approved score scales."""

def attach_measurement_receipt(measurement):
 valid=measurement.get('quality')=='valid' and measurement.get('value') is not None
 measurement['status']='measured' if valid else 'unavailable'
 measurement['reason']=None if valid else measurement.get('limitationCode','INSUFFICIENT_EVIDENCE')
 measurement['calibrationVersion']=measurement.get('normalizationVersion')
 area=measurement.get('evaluatedArea',{})
 visible=area.get('sourcePixels');expected=area.get('anatomicalSourcePixels')
 measurement['coverage']=(max(0.,min(1.,visible/expected)) if isinstance(visible,(int,float)) and isinstance(expected,(int,float)) and expected>0 else None)
 measurement['localConfidence']=None  # Analytic intensity/global grades are not probabilities.
 return measurement

def attach_result_receipts(result):
 for values in result.get('measurements',{}).values():
  for row in values:attach_measurement_receipt(row)
 for row in result.get('general',{}).get('measurements',[]):attach_measurement_receipt(row)
 skin_type=result.get('general',{}).get('skinType')
 if skin_type:
  skin_type['status']='measured' if skin_type.get('quality')=='valid' and skin_type.get('value') is not None else 'unavailable'
  skin_type['reason']=None if skin_type['status']=='measured' else skin_type.get('limitationCode','MODEL_NOT_ACCEPTED')
  skin_type['modelVersion']=skin_type.get('methodVersion') if skin_type.get('modelHash') else None
  skin_type['calibrationVersion']=None;skin_type['coverage']=None
 # The map and its owning score share an explicit calibration receipt. A
 # missing score never leaves a selectable stale layer in this response.
 owners={(region,row['id']):row for region,rows in result.get('measurements',{}).items() for row in rows}
 owners.update({('overview',row['id']):row for row in result.get('general',{}).get('measurements',[])})
 for key,layer in list(result.get('maps',{}).items()):
  owner=owners.get((layer.get('region'),layer.get('criterion')))
  if not owner or owner['status']!='measured':
   result['maps'].pop(key)
   if owner:owner['localMap']=None
   continue
  layer['calibrationVersion']=owner['calibrationVersion']
  layer['scoreMethodVersion']=owner['methodVersion']
  layer['modelHash']=owner.get('modelHash')
 # Actual methods used in this result, including unavailable model boundaries.
 # Rejected research candidates cannot become active through a file presence.
 methods={}
 for (region,criterion),owner in owners.items():
  methods.setdefault(criterion,{})[region]={k:owner.get(k) for k in ['methodVersion','modelVersion','modelHash','calibrationVersion','status','reason']}
 if skin_type:methods['type']={'overview':{k:skin_type.get(k) for k in ['methodVersion','modelVersion','modelHash','calibrationVersion','status','reason']}}
 result['activeCriterionMethods']=dict(version='actual-result-method-receipt-v1',criteria=methods)
 return result
