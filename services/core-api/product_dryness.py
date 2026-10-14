"""Admitted local dryness runtime. No AG paths, fitting or photo feature cache."""
import hashlib,json,threading,time
from pathlib import Path

BASE=Path(__file__).resolve().parent/'models/dryness-calibrated-v3'
HEAD_SHA='7f13c7cb4eb65a3fb44abf062563ee3aff605a6ef9ff3271c5e32e206fedb8e1'
ORT_SHA='a93e5445326c8071cd4d013b6fde494d9054dd4842dacf97028ceaefc9eb1987'
METHOD='appearance-native-dry-2'
NORMALIZATION='native-calibrated-material-source-area-v8'
SAMPLING='native-source-closed-cells-max-union-v5'
_runtime=None
_lock=threading.Lock()

class DrynessModelUnavailable(RuntimeError):pass

def runtime(check):
    global _runtime
    with _lock:
        check()
        if _runtime is None:
            import material_component_features as M
            try:
                config=json.loads((BASE/'config.json').read_text('utf8'))
                if not config['enabled'] or config['headSHA256']!=HEAD_SHA or config['encoderSHA256']!=ORT_SHA or config['sourceEncoderSHA256']!=M.ENCODER_SHA:raise ValueError('CONFIG_IDENTITY')
                assets={}
                for key in ['head','encoder','parity']:
                    name=config[key]
                    if Path(name).name!=name:raise ValueError('ASSET_PATH')
                    path=BASE/name
                    if hashlib.sha256(path.read_bytes()).hexdigest()!=config[key+'SHA256']:raise ValueError('ASSET_HASH')
                    assets[key]=path
                head=json.loads(assets['head'].read_text('utf8'))
                if head['threshold']!=.5 or head['trainRows']!=64 or head['lossVersion']!=config['lossVersion'] or head['regularizationC']!=.15 or head['scaling']!={'vis_scale':3.,'geo_scale':.4,'pos_weight_mult':3.} or head['encoderSHA256']!=M.ENCODER_SHA:raise ValueError('HEAD_CONTRACT')
                encoder=M.OnnxMaterialEncoder(assets['encoder'],assets['parity'],intra_op_threads=4,batch_limit=4,cpu_mem_arena=False)
                inp=encoder.session.get_inputs();out=encoder.session.get_outputs()
                if len(inp)!=1 or inp[0].name!='crops' or inp[0].shape[1:]!=[3,224,224] or out[0].name!='features' or out[0].shape[-1]!=1280:raise ValueError('ENCODER_GRAPH')
                _runtime=(head,encoder)
            except (OSError,ValueError,KeyError,RuntimeError) as error:raise DrynessModelUnavailable('DRYNESS_MODEL_UNAVAILABLE') from error
        check();return _runtime

def replace_dryness(result,native,identity):
    """Atomic caller-local replacement: never mix old scores with new maps."""
    from skin_measurement_contract import attach_result_receipts
    if (result['photoId'],result['sourceWidth'],result['sourceHeight'])!=(native['photoId'],native['sourceWidth'],native['sourceHeight']):raise ValueError('DRYNESS_SOURCE_MISMATCH')
    if isinstance(result.get('general'),dict)!=(native.get('general') is not None):raise ValueError('DRYNESS_OVERVIEW_SCOPE_MISMATCH')
    def stamp(row):
        row.update(methodVersion=METHOD,normalizationVersion=NORMALIZATION,modelVersion='calibrated-material-v3-c04-clean',modelHash=identity)
        row['components'].update(samplingSupportVersion=SAMPLING,headSHA256=HEAD_SHA,encoderSHA256=ORT_SHA)
        return row
    replacements={region:stamp(row) for region,row in native['measurements'].items()}
    overview=stamp(native['general']) if native['general'] is not None else None
    # Build every replacement before mutating the result.
    measurements={region:[replacements[region] if row['id']=='dry' else row for row in rows] for region,rows in result['measurements'].items()}
    maps={key:layer for key,layer in result['maps'].items() if not key.endswith(':dry')}
    for key,layer in native['maps'].items():
        maps[key]={**layer,'method':METHOD,'normalizationVersion':NORMALIZATION,'modelHash':identity,'samplingSupportVersion':SAMPLING}
    result['measurements']=measurements;result['maps']=maps
    if 'general' in result and overview is not None:
        result['general']['measurements']=[overview if row['id']=='dry' else row for row in result['general']['measurements']]
    result['drynessRuntime']={**native['nativeMetadata'],'normalProductEnabled':True,'headSHA256':HEAD_SHA,'encoderSHA256':ORT_SHA,'sourceEncoderSHA256':__import__('material_component_features').ENCODER_SHA,'persistentPhotoCache':False}
    return attach_result_receipts(result)

def analyze_product(value,base_analyzer,check):
    import psutil
    import material_component_features as M
    from native_dry_path import analyze_native_dry
    started=time.monotonic()
    def guard():
        check()
        if psutil.virtual_memory().available<400*2**20:raise DrynessModelUnavailable('LOCAL_MEMORY_RESERVE')
    guard();result=base_analyzer(value);guard();head,encoder=runtime(guard);profile={}
    def material_filter(image,field,metric):return M.filter_material_support_streamed(image,field,metric,encoder,head,check=guard)
    native=analyze_native_dry(value,material_filter=material_filter,check=guard,profile=profile)
    guard();identity=hashlib.sha256((HEAD_SHA+ORT_SHA+M.ENCODER_SHA).encode()).hexdigest()
    result=replace_dryness(result,native,identity)
    result['drynessRuntime'].update(profile=profile,fullAnalysisSeconds=time.monotonic()-started)
    guard();return result
