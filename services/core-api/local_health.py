"""Bounded local analysis; hosted skin type requires separate per-frame consent.
Personal frames are never logged or stored by this API.
"""
import asyncio
import json
import math
from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from appearance_analysis import analyze_skin
from experimental_acne_v5 import configuration as acne_preview_configuration,PreviewUnavailable,PreviewRejected

router = APIRouter(prefix='/api/local-health')
_busy = asyncio.Lock()
parked = lambda: False


@router.get('/skin/acne-v5-config')
async def acne_v5_config():
    return acne_preview_configuration()


@router.post('/skin/capture-check')
async def skin_capture_check(request: Request):
    # Reuses local consent/park/disconnect boundaries. No frame storage/logging.
    value=await payload(request)
    from skin_eyewear import classify_roi,VERSION
    from appearance_analysis import decode_photo
    try:
        token=value.get('frameToken')
        if not isinstance(token,str) or len(token)>64 or not token or value.get('policy')!=VERSION:raise ValueError()
        photo=value.get('eyePhoto')
        if not isinstance(photo,str) or len(photo)>100000:raise ValueError()
        import base64
        raw=base64.b64decode(photo.split(',',1)[1],validate=True)
        if raw[:8]!=b'\x89PNG\r\n\x1a\n' or len(raw)<24 or int.from_bytes(raw[16:20],'big')!=112 or int.from_bytes(raw[20:24],'big')!=112:raise ValueError()
        image,_=decode_photo(photo)
        if image.shape!=(112,112,3):raise ValueError()
        import cv2
        if _busy.locked():raise HTTPException(429,'LOCAL_ANALYSIS_BUSY')
        async with _busy:result=await run_in_threadpool(classify_roi,cv2.cvtColor(image,cv2.COLOR_BGR2RGB))
        if not parked() or await request.is_disconnected():raise HTTPException(409,'CANCELLED')
        return {**result,'frameToken':token}
    except (KeyError,ValueError,TypeError,IndexError):raise HTTPException(422,'INVALID_SKIN_CAPTURE_CHECK')
    except (OSError,RuntimeError):raise HTTPException(503,'SKIN_CAPTURE_CHECK_UNAVAILABLE')


def skin_capture_preflight(value):
    from skin_eyewear import classify_source
    from appearance_analysis import decode_photo
    image,identity=decode_photo(value.get('photo'))
    if identity!=value.get('photoId'):raise ValueError('SOURCE_MISMATCH')
    result=classify_source(image,value['landmarks'])
    if result['status']=='EYEWEAR_PRESENT':raise HTTPException(409,'SKIN_EYEWEAR_PRESENT')
    if result['status']!='CLEAR':raise HTTPException(422,'SKIN_EYEWEAR_CHECK_UNCERTAIN')
    return result


async def payload(request):
    if not parked():
        raise HTTPException(409, 'PARK_REQUIRED')
    if _busy.locked():
        raise HTTPException(429, 'LOCAL_ANALYSIS_BUSY')
    if request.headers.get('content-type','').split(';')[0] != 'application/json':
        raise HTTPException(415, 'JSON_REQUIRED')
    body = bytearray()
    async for chunk in request.stream():
        if len(body)+len(chunk) > 35_000_000:
            raise HTTPException(413, 'PHOTO_LIMIT')
        body.extend(chunk)
    try:
        value = json.loads(body)
        if not isinstance(value, dict) or value.get('processingConsent') is not True:
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(422, 'INVALID_LOCAL_REQUEST')
    if not parked() or await request.is_disconnected():
        raise HTTPException(409, 'CANCELLED')
    return value


def landmarks(points):
    if not isinstance(points,list) or len(points) not in (468,478):raise ValueError()
    for point in points:
        if not isinstance(point,dict) or not all(k in point for k in ('x','y')):raise ValueError()
        for key in ('x','y','z'):
            number=point.get(key,0)
            if isinstance(number,bool) or not isinstance(number,(int,float)) or not math.isfinite(number) or abs(number)>5:raise ValueError()


def skin_geometry(value):
    if not isinstance(value.get('hostedProcessingConsent',False),bool):raise ValueError()
    landmarks(value.get('landmarks'))
    from skin_expression import validate
    validate(value.get('expressionObservation'),value.get('photoId'))
    meshes=value.get('meshes')
    if not isinstance(meshes,dict) or not 1<=len(meshes)<=6:raise ValueError()
    if not isinstance(value.get('exclusions',[]),list) or not isinstance(value.get('temporal',[]),list):raise ValueError()
    if len(value.get('exclusions',[]))>40 or len(value.get('temporal',[]))>8:raise ValueError()
    for box in value.get('exclusions',[]):
        if not isinstance(box,dict) or not all(isinstance(box.get(k),(int,float)) and math.isfinite(box[k]) and abs(box[k])<=8192 for k in ('x','y','w','h')) or box['w']<0 or box['h']<0:raise ValueError()
    if not isinstance(value.get('conditions'),dict):raise ValueError()
    for number in value['conditions'].values():
        if isinstance(number,bool) or not isinstance(number,(int,float)) or not math.isfinite(number) or abs(number)>1e9:raise ValueError()
    for sample in value.get('temporal',[]):landmarks(sample.get('points',sample) if isinstance(sample,dict) else sample)
    for region,mesh in meshes.items():
        if region not in ('forehead','rightCheek','leftCheek','nose','chin','periorbital') or not isinstance(mesh,dict):raise ValueError()
        if not isinstance(mesh.get('points'),list) or not isinstance(mesh.get('edges'),list):raise ValueError()
        if not 3<=len(mesh.get('points',[]))<=200 or len(mesh.get('edges',[]))>1000:raise ValueError()
        for point in mesh['points']:
            if not isinstance(point,dict) or not all(isinstance(point.get(k),(int,float)) and math.isfinite(point[k]) and abs(point[k])<=4096 for k in ('x','y')):raise ValueError()
        for edge in mesh['edges']:
            if not isinstance(edge,list) or len(edge)!=2 or not all(isinstance(i,int) and not isinstance(i,bool) and 0<=i<len(mesh['points']) for i in edge):raise ValueError()


@router.post('/skin')
async def skin(request: Request):
    value = await payload(request)
    if _busy.locked():
        raise HTTPException(429, 'LOCAL_ANALYSIS_BUSY')
    try:
        skin_geometry(value)
        async with _busy:
            from native_material_budget import NativeRequestBudget,NativeRequestStopped
            from camera_color import CameraProfileUnavailable
            from product_dryness import analyze_product,DrynessModelUnavailable
            scope=NativeRequestBudget()
            def work():
                # camera-correct pixels: raw YUV frame converted with the vehicle camera profile (+ colour correction)
                from camera_color import load_profile,prepare,restore
                source,color,client_id,analyzed_id=prepare(value,load_profile())
                scope.check();eyewear=skin_capture_preflight(source);scope.check()
                result=analyze_product(source,analyze_skin,scope.check)
                if source.get('experimentalAcneV5', True) is not False:
                    from acne_v5_product import replace_acne
                    result=replace_acne(result,source,scope.check)
                from local_skin_type import finalize_product_type
                result=finalize_product_type(result)
                from regional_attach import attach as attach_regional_map
                result=attach_regional_map(result,source,scope.check)
                return eyewear,restore(result,color,client_id,analyzed_id)
            worker=asyncio.create_task(run_in_threadpool(work))
            try:
                while not worker.done():
                    if not parked() or await request.is_disconnected():scope.cancel()
                    await asyncio.wait({worker},timeout=.05)
                eyewear,result=await worker
            except asyncio.CancelledError:
                scope.cancel()
                try:await asyncio.shield(worker)
                except (NativeRequestStopped,DrynessModelUnavailable):pass
                raise
            except NativeRequestStopped as error:
                raise HTTPException(504 if str(error)=='LOCAL_ANALYSIS_TIMEOUT' else 409,str(error)) from None
            except PreviewUnavailable as error:
                raise HTTPException(503,str(error)) from None
            except PreviewRejected as error:
                raise HTTPException(422,str(error)) from None
            except DrynessModelUnavailable:
                raise HTTPException(503,'LOCAL_MODEL_OR_RESOURCE_UNAVAILABLE') from None
            except CameraProfileUnavailable:
                raise HTTPException(503,'CAMERA_PROFILE_UNAVAILABLE') from None
        result['captureScopeVersion']=eyewear['version']
        for rows in [*result.get('measurements',{}).values(),result.get('general',{}).get('measurements',[])]:
            for row in rows:
                row.setdefault('captureConditions',{})['skinCapturePolicy']=eyewear['version']
                row['captureConditions']['skinEyewearModelHash']=eyewear['modelHash']
        if not parked() or await request.is_disconnected():
            raise HTTPException(409, 'CANCELLED')
        return result
    except (KeyError, ValueError, TypeError, IndexError, OverflowError):
        raise HTTPException(422, 'INVALID_LOCAL_GEOMETRY_OR_PHOTO')


@router.post('/skin/camera-calibration')
async def skin_camera_calibration(request: Request):
    """Service mode only (ATTUNE_CAMERA_CALIBRATION=1): one photo of the printed Attune chart from the cabin camera ->
    vehicle camera profile (YUV matrix/range + colour correction) written to ATTUNE_CAMERA_PROFILE when the quality
    gates pass. Body: {processingConsent, profileId, yuv:{matrix, fullRange}, photo (PNG data URL) | rawFrame}."""
    import os
    if os.environ.get('ATTUNE_CAMERA_CALIBRATION')!='1' or not os.environ.get('ATTUNE_CAMERA_PROFILE'):
        raise HTTPException(403,'CAMERA_CALIBRATION_DISABLED')
    value=await payload(request)
    try:
        import hashlib
        from camera_color import raw_frame_bgr
        from camera_calibration import measure_chart,fit_profile,write_profile
        from appearance_analysis import decode_photo
        yuv=value.get('yuv');profile_id=value.get('profileId')
        if not isinstance(profile_id,str) or not 3<=len(profile_id)<=80 or not isinstance(yuv,dict):raise ValueError()
        if value.get('rawFrame') is not None:bgr,_=raw_frame_bgr(value['rawFrame'],{'yuv':{'matrix':yuv.get('matrix'),'fullRange':yuv.get('fullRange')}} if yuv.get('matrix') else None)
        else:bgr,_=decode_photo(value.get('photo'))
        source=hashlib.sha256(bgr.tobytes()).hexdigest()
        async with _busy:measured=await run_in_threadpool(measure_chart,bgr)
        profile,report=fit_profile([measured],profile_id,yuv={'matrix':yuv.get('matrix'),'fullRange':yuv.get('fullRange')},sources=[source])
    except (KeyError,ValueError,TypeError,IndexError):
        raise HTTPException(422,'INVALID_CALIBRATION_REQUEST')
    if profile is None:return {'status':'REJECTED','report':report}
    digest=write_profile(profile,os.environ['ATTUNE_CAMERA_PROFILE'])
    return {'status':'ACCEPTED','profileId':profile_id,'profileSHA256':digest,'report':report}


@router.post('/skin/regional-fuse')
async def skin_regional_fuse(request: Request):
    """Three-angle regional skin map + findings from the per-photo regionalSkinMap objects returned by /skin.
    Only numbers travel here (no photo); the decision models run on the server, never in the client."""
    value = await payload(request)
    from regional_attach import fuse_regional
    try:
        maps = value.get('maps')
        if not isinstance(maps, dict):
            raise ValueError('MAPS_REQUIRED')
        out = await run_in_threadpool(fuse_regional, maps)
        if not parked() or await request.is_disconnected():
            raise HTTPException(409, 'CANCELLED')
        return out
    except (KeyError, ValueError, TypeError):
        raise HTTPException(422, 'INVALID_REGIONAL_FUSE_PAYLOAD') from None


@router.post('/skin/fuse-multi-angle')
async def skin_fuse_multi_angle(request: Request):
    value = await payload(request)
    from local_skin_type import fuse_multi_angle_skin
    try:
        front_res = value.get('front')
        left_res = value.get('left')
        right_res = value.get('right')
        if not isinstance(front_res, dict):
            raise ValueError('FRONT_REQUIRED')
        fused = await run_in_threadpool(fuse_multi_angle_skin, front_res, left_res, right_res)
        from regional_attach import fuse as fuse_regional_map
        fused = await run_in_threadpool(fuse_regional_map, fused, front_res, left_res, right_res)
        if not parked() or await request.is_disconnected():
            raise HTTPException(409, 'CANCELLED')
        return fused
    except (KeyError, ValueError, TypeError):
        raise HTTPException(422, 'INVALID_MULTI_ANGLE_PAYLOAD') from None


async def dental_work(request,work,value):
    """Own one worker until it drains; never return a late successful result."""
    from native_material_budget import NativeRequestBudget,NativeRequestStopped
    scope=NativeRequestBudget(30.)
    async with _busy:
        worker=asyncio.create_task(run_in_threadpool(work,value,scope.check))
        try:
            while not worker.done():
                if not parked() or await request.is_disconnected():scope.cancel()
                try:scope.check()
                except NativeRequestStopped:pass
                await asyncio.wait({worker},timeout=.05)
            result=await worker
            scope.check()
            return result
        except asyncio.CancelledError:
            scope.cancel()
            try:await asyncio.shield(worker)
            except Exception:pass
            raise
        except NativeRequestStopped:
            raise HTTPException(408 if scope.reason=='LOCAL_ANALYSIS_TIMEOUT' else 409,scope.reason or 'CANCELLED') from None


@router.post('/dental')
async def dental(request: Request):
    value = await payload(request)
    if _busy.locked():
        raise HTTPException(429, 'LOCAL_ANALYSIS_BUSY')
    from dental_analysis import analyze_dental,DentalModelError
    try:
        # BITE may be skipped by the user (e.g. contact cannot be shown); it is
        # then reported as a missing view, never as a measured/healthy bite.
        if not isinstance(value.get('captures'),list) or [c.get('pose') for c in value['captures']] not in (['FRONT','RIGHT','LEFT','BITE'],['FRONT','RIGHT','LEFT']):raise ValueError()
        for capture in value['captures']:
            landmarks(capture.get('landmarks'))
            if capture.get('pose') not in ('FRONT','RIGHT','LEFT','BITE'):raise ValueError()
        result = await dental_work(request,analyze_dental,value)
        if not parked() or await request.is_disconnected():
            raise HTTPException(409, 'CANCELLED')
        return result
    except DentalModelError:
        raise HTTPException(503, 'LOCAL_MODEL_FAILURE') from None
    except (KeyError, ValueError, TypeError, IndexError, OverflowError):
        raise HTTPException(422, 'INVALID_LOCAL_GEOMETRY_OR_PHOTO')


@router.post('/dental-upload')
async def dental_upload(request: Request):
    value = await payload(request)
    from dental_upload import analyze_upload,UploadError
    from dental_analysis import DentalModelError
    try:
        if value.get('photoLandmarks') is not None:landmarks(value['photoLandmarks'])
        result = await dental_work(request,analyze_upload,value)
        if not parked() or await request.is_disconnected():
            raise HTTPException(409, 'CANCELLED')
        return result
    except UploadError as error:
        raise HTTPException(422, str(error)) from None
    except DentalModelError:
        raise HTTPException(503, 'LOCAL_MODEL_FAILURE') from None
    except (KeyError, ValueError, TypeError, IndexError, OverflowError):
        raise HTTPException(422, 'INVALID_UPLOAD') from None
