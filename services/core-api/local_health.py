"""Bounded local analysis; hosted skin type requires separate per-frame consent.
Personal frames are never logged or stored by this API.
"""
import asyncio
import json
import math
from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from appearance_analysis import analyze_skin

router = APIRouter(prefix='/api/local-health')
_busy = asyncio.Lock()
parked = lambda: False


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
            result = await run_in_threadpool(analyze_skin, value)
        if not parked() or await request.is_disconnected():
            raise HTTPException(409, 'CANCELLED')
        return result
    except (KeyError, ValueError, TypeError, IndexError, OverflowError):
        raise HTTPException(422, 'INVALID_LOCAL_GEOMETRY_OR_PHOTO')


@router.post('/dental')
async def dental(request: Request):
    value = await payload(request)
    if _busy.locked():
        raise HTTPException(429, 'LOCAL_ANALYSIS_BUSY')
    from dental_analysis import analyze_dental,DentalModelError
    try:
        if not isinstance(value.get('captures'),list) or not 1<=len(value['captures'])<=4:raise ValueError()
        for capture in value['captures']:
            landmarks(capture.get('landmarks'))
            if capture.get('pose') not in ('FRONT','RIGHT','LEFT','BITE'):raise ValueError()
        async with _busy:
            result = await run_in_threadpool(analyze_dental, value)
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
        async with _busy:
            result = await run_in_threadpool(analyze_upload, value)
        if not parked() or await request.is_disconnected():
            raise HTTPException(409, 'CANCELLED')
        return result
    except UploadError as error:
        raise HTTPException(422, str(error)) from None
    except DentalModelError:
        raise HTTPException(503, 'LOCAL_MODEL_FAILURE') from None
    except (KeyError, ValueError, TypeError, IndexError, OverflowError):
        raise HTTPException(422, 'INVALID_UPLOAD') from None
