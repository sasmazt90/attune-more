"""Private, persistent local inference process. Frames exist only in pipe/memory."""
import contextlib
import json
import struct
import sys

MAX_MESSAGE=128*1024*1024

def skin_analysis(value, check=lambda:None):
    from camera_color import load_profile,prepare,restore
    from local_health import skin_capture_preflight
    from appearance_analysis import analyze_skin
    from product_dryness import analyze_product
    source,color,client_id,analyzed_id=prepare(value,load_profile())
    check();eyewear=skin_capture_preflight(source);check()
    result=analyze_product(source,analyze_skin,check)
    if source.get('experimentalAcneV5',True) is not False:
        from acne_v5_product import replace_acne
        result=replace_acne(result,source,check)
    from local_skin_type import finalize_product_type
    from regional_attach import attach
    result=attach(finalize_product_type(result),source,check)
    return eyewear,restore(result,color,client_id,analyzed_id)

def execute(operation,value):
    if operation=='skin':return skin_analysis(value)
    if operation=='skin-fuse':
        from regional_attach import fuse_regional
        return fuse_regional(value)
    if operation=='dental':
        from dental_analysis import analyze_dental
        return analyze_dental(value)
    if operation=='dental-upload':
        from dental_upload import analyze_upload
        return analyze_upload(value)
    if operation=='warm-skin':
        from regional_skin_v3 import load_runtime,model_manifest
        from product_dryness import runtime
        from local_skin_type import load
        load_runtime();runtime(lambda:None);load()
        return {'ready':True,'models':model_manifest()}
    raise ValueError('INVALID_OPERATION')

def main():
    # Native libraries may print; stdout belongs exclusively to the framed IPC.
    output=sys.stdout.buffer
    while True:
        header=sys.stdin.buffer.read(4)
        if not header:return
        size=struct.unpack('!I',header)[0]
        if not 0<size<=MAX_MESSAGE:return
        raw=sys.stdin.buffer.read(size)
        if len(raw)!=size:return
        try:
            request=json.loads(raw)
            with contextlib.redirect_stdout(sys.stderr):
                result=execute(request['operation'],request['value'])
            response={'result':result}
        except Exception as error:
            import logging
            logging.getLogger(__name__).exception('Native analysis operation failed (%s)',type(error).__name__)
            from fastapi import HTTPException
            from dental_analysis import DentalModelError
            from dental_upload import UploadError
            from product_dryness import DrynessModelUnavailable
            from camera_color import CameraProfileUnavailable
            from experimental_acne_v5 import PreviewRejected,PreviewUnavailable
            if isinstance(error,HTTPException):status,code=error.status_code,error.detail
            elif isinstance(error,UploadError):status,code=422,str(error)
            elif isinstance(error,(PreviewRejected,)):status,code=422,str(error)
            elif isinstance(error,DentalModelError):status,code=503,'LOCAL_MODEL_FAILURE'
            elif isinstance(error,CameraProfileUnavailable):status,code=503,'CAMERA_PROFILE_UNAVAILABLE'
            elif isinstance(error,(PreviewUnavailable,DrynessModelUnavailable,OSError)):status,code=503,'LOCAL_MODEL_OR_RESOURCE_UNAVAILABLE'
            elif isinstance(error,(KeyError,ValueError,TypeError,IndexError,OverflowError)):status,code=422,'INVALID_LOCAL_GEOMETRY_OR_PHOTO'
            else:status,code=503,'LOCAL_ANALYSIS_WORKER_FAILED'
            response={'status':status,'code':code}
        encoded=json.dumps(response,allow_nan=False,separators=(',',':')).encode()
        if len(encoded)>MAX_MESSAGE:return
        output.write(struct.pack('!I',len(encoded)));output.write(encoded);output.flush()
        # Only model caches survive a request, never its pixels or result maps.
        raw=request=response=encoded=None
        result=None

if __name__=='__main__':main()
