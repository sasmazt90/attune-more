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
        if isinstance(result.get('general'), dict):
            result['general']['findings'] = findings_unavailable('MODEL_BUNDLE_UNAVAILABLE')
        return result
    result['regionalSkinMap'] = m
    if pose == 'FRONT' and isinstance(result.get('general'), dict):
        result['general']['regionalSkinMap'] = m
        # one photo alone never satisfies the validated capture set: findings say so instead of "nothing seen"
        import skin_findings_v1 as SF
        result['general']['findings'] = SF.findings_from_maps({'FRONT': m})
    result['regionalSkinMapStatus'] = 'OK'
    return result


def findings_unavailable(reason: str) -> dict:
    import skin_findings_v1 as SF
    return dict(version=SF.VERSION, status='unavailable', reason=reason, poses=[], findings=[],
                unavailable=[dict(id=f, reason=reason) for f in (*SF.DETECTOR_FINDINGS, *SF.UNAVAILABLE)])


def fuse_regional(maps: dict) -> dict:
    """Server-side three-angle fusion of the per-photo regional maps + findings (used by /skin/regional-fuse)."""
    maps = {p: m for p, m in (maps or {}).items() if p in ('FRONT', 'LEFT', 'RIGHT') and isinstance(m, dict)}
    if 'FRONT' not in maps:
        raise ValueError('FRONT_REQUIRED')
    import regional_skin_v3 as R, skin_findings_v1 as SF
    # findings use only the per-photo detector evidence; a failed skin-type fusion does not remove them
    findings = SF.findings_from_maps(maps)
    try:
        fused_map = R.fuse_maps(maps) if len(maps) > 1 else maps['FRONT']
    except Exception as error:  # noqa: BLE001
        if _stopped(error):
            raise
        log.warning('regional fusion unavailable: %s', type(error).__name__)
        return dict(regionalSkinMap=None, regionalSkinMapStatus='REGIONAL_FUSION_UNAVAILABLE', findings=findings)
    return dict(regionalSkinMap=fused_map, regionalSkinMapStatus='OK', findings=findings)


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
        import skin_findings_v1 as SF
        fused['general']['findings'] = SF.findings_from_maps(maps)
    return fused
