"""Attaches the regional skin map (regional_skin_v3) to /skin results without touching the existing analysis.

* Per photo: result['regionalSkinMap'] (and general.regionalSkinMap on the front photo).
* Three-angle fusion: the per-photo maps are averaged per region (each cheek only from the poses that show it).
If the regional bundle is missing or fails, the original result is returned unchanged with a status code;
the paint then simply does not appear (never a guessed colour)."""
from __future__ import annotations
import logging

log = logging.getLogger('regional_attach')


def _stopped(error: Exception) -> bool:
    return type(error).__name__ in ('NativeRequestStopped', 'CancelledError')


def attach(result: dict, value: dict, check=lambda: None) -> dict:
    try:
        import regional_skin_v3 as R
        from appearance_analysis import decode_photo
        bgr, _ = decode_photo(value['photo'])
        pose = value.get('pose') or 'FRONT'
        m = R.analyze_photo(bgr, value['landmarks'], check, pose=pose)
    except Exception as error:  # noqa: BLE001 - optional layer, never breaks /skin
        if _stopped(error):
            raise
        log.warning('regional map unavailable: %s', type(error).__name__)
        result['regionalSkinMapStatus'] = 'REGIONAL_MAP_UNAVAILABLE'
        return result
    result['regionalSkinMap'] = m
    if pose == 'FRONT' and isinstance(result.get('general'), dict):
        result['general']['regionalSkinMap'] = m
    result['regionalSkinMapStatus'] = 'OK'
    return result


def fuse(fused: dict, front: dict | None, left: dict | None, right: dict | None) -> dict:
    maps = {pose: r.get('regionalSkinMap') for pose, r in (('FRONT', front), ('LEFT', left), ('RIGHT', right))
            if isinstance(r, dict) and isinstance(r.get('regionalSkinMap'), dict)}
    if 'FRONT' not in maps:
        return fused
    try:
        import regional_skin_v3 as R
        m = R.fuse_maps(maps)
    except Exception as error:  # noqa: BLE001
        log.warning('regional fusion unavailable: %s', type(error).__name__)
        m = maps['FRONT']
    if m is None:
        return fused
    fused['regionalSkinMap'] = m
    if isinstance(fused.get('general'), dict):
        fused['general']['regionalSkinMap'] = m
    return fused
