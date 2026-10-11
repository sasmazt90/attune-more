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
 return result
