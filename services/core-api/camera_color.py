"""Camera colour source for /skin: raw YUV frame conversion and the vehicle camera colour profile.

Why: the browser converts the camera's YUV frame to RGB before the app can read it, and the conversion matrix it uses
depends on how the frame is tagged. With the software GPU, Chrome tagged a BT.601 camera stream as BT.709 and shifted
facial R/G by about +2.5/255, which moved finding scores across their thresholds. The app therefore also sends the raw
YUV planes of the same frame (WebCodecs VideoFrame.copyTo), and the server converts them with the matrix/range of the
vehicle camera profile (or, without a profile, the frame tag, else BT.601 limited range).

Vehicle camera profile (JSON, path in ATTUNE_CAMERA_PROFILE; schema `attune-camera-profile-v1`):
  yuv: {matrix: bt601|bt709|bt2020, fullRange: bool}       how the camera encodes YUV (from the camera datasheet/ISP)
  ccm: 3x3 matrix, offset: 3 (linear-light RGB)              colour correction fitted from a reference chart photo
The colour correction is applied to every analysed photo (raw or PNG). No profile: no correction (identity).

The capture identity (photoId) stays the client's; the analysed pixels' hash is reported in cameraColor.
"""
import base64, hashlib, json, os, threading
import cv2, numpy as np

SCHEMA = 'attune-camera-profile-v1'
MATRICES = {'bt601': (0.299, 0.114), 'bt709': (0.2126, 0.0722), 'bt2020': (0.2627, 0.0593)}
TAG_TO_MATRIX = {'smpte170m': 'bt601', 'bt470bg': 'bt601', 'bt601': 'bt601', 'bt709': 'bt709', 'bt2020-ncl': 'bt2020'}
FORMATS = ('I420', 'NV12')
_lock = threading.Lock(); _cache = {}


class CameraColorError(ValueError):
    pass


class CameraProfileUnavailable(RuntimeError):
    """A configured vehicle camera profile is missing or invalid (server configuration fault, not the request)."""


def _check_profile(p):
    if not isinstance(p, dict) or p.get('schema') != SCHEMA or not isinstance(p.get('profileId'), str):
        raise CameraColorError('CAMERA_PROFILE_SCHEMA')
    yuv = p.get('yuv')
    if yuv is not None and (not isinstance(yuv, dict) or yuv.get('matrix') not in MATRICES or not isinstance(yuv.get('fullRange'), bool)):
        raise CameraColorError('CAMERA_PROFILE_YUV')
    if p.get('ccm') is not None:
        m = np.asarray(p['ccm'], float); o = np.asarray(p.get('offset', [0, 0, 0]), float)
        if m.shape != (3, 3) or o.shape != (3,) or not np.isfinite(m).all() or not np.isfinite(o).all():
            raise CameraColorError('CAMERA_PROFILE_CCM')
        if np.linalg.cond(m) > 50 or np.abs(m).max() > 5 or np.abs(o).max() > 0.2:
            raise CameraColorError('CAMERA_PROFILE_CCM_IMPLAUSIBLE')
    return p


def load_profile(path=None):
    """The vehicle camera profile, or None. A configured but unreadable/invalid profile is an error (never silently ignored)."""
    path = path or os.environ.get('ATTUNE_CAMERA_PROFILE')
    if not path:
        return None
    try:
        st = os.stat(path)
        with _lock:
            hit = _cache.get(path)
            if hit and hit[0] == (st.st_mtime_ns, st.st_size):
                return hit[1]
            raw = open(path, 'rb').read()
            p = _check_profile(json.loads(raw)); p = {**p, 'sha256': hashlib.sha256(raw).hexdigest()}
            _cache[path] = ((st.st_mtime_ns, st.st_size), p)
            return p
    except (OSError, ValueError) as error:
        raise CameraProfileUnavailable(str(error) or type(error).__name__) from None


def _planes(buf, fmt, layout, cw, ch, rect):
    x, y, w, h = rect
    if x % 2 or y % 2 or w % 2 or h % 2:
        raise CameraColorError('RAW_FRAME_ODD_RECT')
    def plane(i, pw, ph, bpp=1):
        off, stride = int(layout[i]['offset']), int(layout[i]['stride'])
        if off < 0 or stride < pw * bpp or off + stride * (ph - 1) + pw * bpp > len(buf):
            raise CameraColorError('RAW_FRAME_LAYOUT')
        return np.lib.stride_tricks.as_strided(buf[off:], (ph, pw * bpp), (stride, 1))
    if fmt == 'I420':
        if len(layout) != 3: raise CameraColorError('RAW_FRAME_LAYOUT')
        Y = plane(0, cw, ch); U = plane(1, cw // 2, ch // 2); V = plane(2, cw // 2, ch // 2)
    else:
        if len(layout) != 2: raise CameraColorError('RAW_FRAME_LAYOUT')
        Y = plane(0, cw, ch); uv = plane(1, cw // 2, ch // 2, 2).reshape(ch // 2, cw // 2, 2); U, V = uv[..., 0], uv[..., 1]
    return Y[y:y + h, x:x + w], U[y // 2:(y + h) // 2, x // 2:(x + w) // 2], V[y // 2:(y + h) // 2, x // 2:(x + w) // 2]


def yuv_to_bgr(Y, U, V, matrix, full_range):
    """Standard YUV->RGB. BT.601 limited range uses OpenCV's own I420 inverse (bit-identical to the research/ffmpeg-style
    decoding of the fixtures); other matrices use the generic formula with bilinear chroma upsampling."""
    h, w = Y.shape
    if matrix == 'bt601' and not full_range:
        i420 = np.concatenate([np.ascontiguousarray(Y).ravel(), np.ascontiguousarray(U).ravel(), np.ascontiguousarray(V).ravel()])
        return cv2.cvtColor(i420.reshape(h * 3 // 2, w), cv2.COLOR_YUV2BGR_I420)
    return generic_yuv_to_bgr(Y, U, V, matrix, full_range)


def generic_yuv_to_bgr(Y, U, V, matrix, full_range):
    h, w = Y.shape
    kr, kb = MATRICES[matrix]; kg = 1 - kr - kb
    Yf = Y.astype(np.float32); Uf = cv2.resize(np.ascontiguousarray(U), (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    Vf = cv2.resize(np.ascontiguousarray(V), (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    if full_range: y, u, v = Yf / 255, (Uf - 128) / 255, (Vf - 128) / 255
    else: y, u, v = (Yf - 16) / 219, (Uf - 128) / 224, (Vf - 128) / 224
    r = y + 2 * (1 - kr) * v; b = y + 2 * (1 - kb) * u; g = (y - kr * r - kb * b) / kg
    return np.clip(np.stack([b, g, r], -1) * 255 + .5, 0, 255).astype(np.uint8)


def srgb_to_linear(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def apply_ccm(bgr, profile):
    """Colour correction in linear light: rgb_lin' = ccm @ rgb_lin + offset. LUT-free but vectorised (~0.1 s at 1080p)."""
    m = np.asarray(profile['ccm'], np.float32); o = np.asarray(profile.get('offset', [0, 0, 0]), np.float32)
    lut = srgb_to_linear(np.arange(256) / 255.).astype(np.float32)
    lin = lut[bgr[..., ::-1]]
    out = lin.reshape(-1, 3) @ m.T + o
    srgb = linear_to_srgb(out).reshape(bgr.shape)
    return np.ascontiguousarray((srgb * 255 + .5).astype(np.uint8)[..., ::-1])


def raw_frame_bgr(raw, profile):
    """Validates a client rawFrame object and converts it. Returns (bgr, info)."""
    if not isinstance(raw, dict) or raw.get('format') not in FORMATS:
        raise CameraColorError('RAW_FRAME_FORMAT')
    cw, ch = int(raw['codedWidth']), int(raw['codedHeight'])
    r = raw.get('visibleRect') or {'x': 0, 'y': 0, 'width': cw, 'height': ch}
    rect = tuple(int(r[k]) for k in ('x', 'y', 'width', 'height'))
    if not (16 <= cw <= 4096 and 16 <= ch <= 4096) or cw % 2 or ch % 2 or rect[0] + rect[2] > cw or rect[1] + rect[3] > ch or min(rect) < 0:
        raise CameraColorError('RAW_FRAME_SIZE')
    data = raw.get('data')
    if not isinstance(data, str) or len(data) > 24_000_000:
        raise CameraColorError('RAW_FRAME_DATA')
    buf = np.frombuffer(base64.b64decode(data.split(',', 1)[-1], validate=True), np.uint8)
    layout = raw.get('layout')
    if not isinstance(layout, list) or not all(isinstance(p, dict) for p in layout):
        raise CameraColorError('RAW_FRAME_LAYOUT')
    Y, U, V = _planes(buf, raw['format'], layout, cw, ch, rect)
    cs = raw.get('colorSpace') if isinstance(raw.get('colorSpace'), dict) else {}
    if profile and profile.get('yuv'):
        matrix, full, source = profile['yuv']['matrix'], profile['yuv']['fullRange'], 'camera-profile'
    elif TAG_TO_MATRIX.get(cs.get('matrix')):
        matrix, full, source = TAG_TO_MATRIX[cs['matrix']], bool(cs.get('fullRange')), 'frame-tag'
    else:
        matrix, full, source = 'bt601', bool(cs.get('fullRange')), 'default-bt601'
    bgr = yuv_to_bgr(Y, U, V, matrix, full)
    return bgr, dict(format=raw['format'], frameTag={k: cs.get(k) for k in ('matrix', 'fullRange', 'primaries', 'transfer')},
                     matrix=matrix, fullRange=full, matrixSource=source)


def prepare(value, profile=None):
    """Swaps the analysed pixels of a /skin request to the camera-correct ones. Returns (value, info, client_id, new_id).
    The client PNG identity is verified first; geometry stays bound to the same frame (sizes must match)."""
    from appearance_analysis import decode_photo
    raw = value.get('rawFrame')
    if raw is None and not (profile and profile.get('ccm') is not None):
        return value, {'source': 'browser-rgb', 'profileId': profile['profileId'] if profile else None, 'colorCorrection': None}, None, None
    png_bgr, client_id = decode_photo(value.get('photo'))
    if client_id != value.get('photoId'):
        raise ValueError('SOURCE_MISMATCH')
    info = {'source': 'browser-rgb'}
    bgr = png_bgr
    if raw is not None:
        bgr, conv = raw_frame_bgr(raw, profile)
        if bgr.shape != png_bgr.shape:
            raise CameraColorError('RAW_FRAME_SIZE_MISMATCH')
        info = {'source': 'raw-yuv', **conv,
                'browserMeanAbsDiff': round(float(np.abs(bgr.astype(np.int16) - png_bgr).mean()), 3)}
    info['profileId'] = profile['profileId'] if profile else None
    info['profileSHA256'] = profile['sha256'] if profile else None
    if profile and profile.get('ccm') is not None:
        bgr = apply_ccm(bgr, profile); info['colorCorrection'] = 'ccm-linear'
    else:
        info['colorCorrection'] = None
    ok, enc = cv2.imencode('.png', bgr, [cv2.IMWRITE_PNG_COMPRESSION, 1])
    if not ok:
        raise CameraColorError('PNG_ENCODE')
    new_id = hashlib.sha256(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA).tobytes()).hexdigest()
    out = {k: v for k, v in value.items() if k != 'rawFrame'}
    out['photo'] = 'data:image/png;base64,' + base64.b64encode(enc.tobytes()).decode()
    out['photoId'] = new_id
    if isinstance(out.get('expressionObservation'), dict) and out['expressionObservation'].get('photoId') == client_id:
        out['expressionObservation'] = {**out['expressionObservation'], 'photoId': new_id}
    info['analyzedPhotoSHA256'] = new_id
    return out, info, client_id, new_id


def restore(result, info, client_id, new_id):
    """Result keeps the client's capture identity everywhere; the analysed-pixels hash is reported in cameraColor."""
    if client_id and new_id and client_id != new_id:
        from fastapi.encoders import jsonable_encoder
        result = json.loads(json.dumps(jsonable_encoder(result)).replace(new_id, client_id))
    result['cameraColor'] = info
    return result
