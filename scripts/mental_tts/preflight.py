"""Offline readiness only. Never downloads/loads models, synthesizes or touches user data."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import sys
import wave
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
from mental_neural_tts import load_configuration,SOURCE_REVISION,MODEL_FILE,verify_runtime_source

parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args()
report={'sourceRevision':SOURCE_REVISION,'modelFile':MODEL_FILE,'modelInference':'NOT_EXECUTED','playback':'NOT_EXECUTED','checks':[]}
for name,version in [('chatterbox-tts',None),('torch','2.6.0'),('torchaudio','2.6.0'),('transformers','5.2.0'),('safetensors','0.5.3')]:
    try:
        actual=importlib.metadata.version(name)
        if version and actual.split('+')[0]!=version:raise ValueError('INCOMPATIBLE_VERSION')
        if name=='chatterbox-tts':
            verify_runtime_source()
        report['checks'].append({'name':name,'status':'PASS','version':actual})
    except (importlib.metadata.PackageNotFoundError,ValueError,OSError,KeyError,TypeError):report['checks'].append({'name':name,'status':'BLOCKED','reason':'Missing or incompatible isolated runtime dependency'})
for language in ['tr','en','de']:
    try:
        if not args.config:raise ValueError('MODEL_BUNDLE_CONFIG_REQUIRED')
        _,_,_,profile=load_configuration(args.config,language,verify_models=language=='tr')
        report['checks'].append({'language':language,'status':'PASS','profile':profile['id'],'meaning':'official V3 bundle and default conditioning hashes verified; no inference/playback acceptance'})
    except (OSError,ValueError,KeyError,TypeError,wave.Error,EOFError):report['checks'].append({'language':language,'status':'BLOCKED','reason':'Verified official V3 model/license/default-conditioning bundle unavailable or invalid'})
report['status']='PASS' if all(x['status']=='PASS' for x in report['checks']) else 'BLOCKED'
text=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
if args.output:args.output.write_text(text)
print(text,end='');sys.exit(0 if report['status']=='PASS' else 69)
