"""Light-aware tone analysis.
1) Surface normals from the 3D MediaPipe landmarks (Delaunay mesh, per-vertex normals, interpolated per pixel).
2) Robust fit of a first-order lighting model per channel on skin pixels: I = k0 + k . n  (ambient + one directional
   light). Lesions/spots are outliers, so a robust (IRLS/Huber) fit keeps them from steering the light estimate.
3) Expected shading S(x) is divided out only to the extent the model explains it -> corrected skin.
4) Per pixel: deviation from the person's own skin after correction. A dark deviation that keeps the skin's
   chromaticity and lies on the side facing away from the light = shadow residue; a deviation that changes chromaticity
   (browner / redder) = pigment. Clipped / near-black pixels are unusable.
"""
import numpy as np, cv2
from scipy.spatial import Delaunay
from scipy.interpolate import LinearNDInterpolator

SKIN = {'forehead': [54,103,67,109,10,338,297,332,284,293,334,296,336,9,107,66,105,63],
        'nose': [168,193,245,188,174,236,198,209,49,48,64,98,97,2,326,327,294,278,279,429,420,456,399,412,465,417],
        'cheek_imgL': [116,117,118,119,100,142,203,206,216,212,214,192,213,147,123],
        'cheek_imgR': [345,346,347,348,329,371,423,426,436,432,434,416,433,376,352],
        'chin': [43,106,182,83,18,313,406,335,273,422,430,394,395,369,396,175,171,140,170,169,210,202]}

def normals_map(P3, shape):
    """P3: (N,3) landmarks in pixels (z scaled like x). Returns (H,W,3) unit normals facing the camera (+z) and a mask."""
    tri = Delaunay(P3[:, :2]); F = tri.simplices
    v0, v1, v2 = P3[F[:, 0]], P3[F[:, 1]], P3[F[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0); fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-9
    fn[fn[:, 2] < 0] *= -1                                    # orient toward the camera
    vn = np.zeros_like(P3)
    for k in range(3): np.add.at(vn, F[:, k], fn)
    vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-9
    H, W = shape; ys, xs = np.mgrid[0:H, 0:W]
    interp = LinearNDInterpolator(P3[:, :2], vn)
    N = interp(np.stack([xs.ravel(), ys.ravel()], 1)).reshape(H, W, 3)
    valid = np.isfinite(N[..., 0]); N[~valid] = 0
    N /= np.linalg.norm(N, axis=-1, keepdims=True) + 1e-9
    return N, valid

def skin_mask(P2, shape, keys=SKIN):
    m = np.zeros(shape, np.uint8)
    for v in keys.values(): cv2.fillPoly(m, [P2[v].astype(np.int32)], 1)
    return m > 0

def robust_fit(A, y, iters=8, c=1.5):
    w = np.ones(len(y))
    for _ in range(iters):
        sw = np.sqrt(w); k, *_ = np.linalg.lstsq(A * sw[:, None], y * sw, rcond=None)
        r = y - A @ k; s = 1.4826 * np.median(np.abs(r - np.median(r))) + 1e-6
        u = np.abs(r) / (c * s); w = np.where(u <= 1, 1.0, 1.0 / u)      # Huber weights
    return k

def analyze(img_bgr, lms, scale_to=400):
    """lms: MediaPipe landmarks (normalized x,y,z). Returns dict with corrected image, light direction, maps."""
    h, w = img_bgr.shape[:2]
    P = np.array([[q.x * w, q.y * h, q.z * w] for q in lms[:468]])
    fw = P[:, 0].max() - P[:, 0].min(); sc = scale_to / fw
    x0, y0 = P[:, 0].min() - 0.15 * fw, P[:, 1].min() - 0.15 * fw
    P[:, 0] -= x0; P[:, 1] -= y0; P *= sc
    W = int(P[:, 0].max() + 0.15 * scale_to); H = int(P[:, 1].max() + 0.15 * scale_to)
    M = np.float32([[sc, 0, -x0 * sc], [0, sc, -y0 * sc]])
    im = cv2.warpAffine(img_bgr, M, (W, H), flags=cv2.INTER_AREA).astype(np.float32) / 255
    lin = np.where(im <= 0.04045, im / 12.92, ((im + 0.055) / 1.055) ** 2.4)      # linear light
    N, nvalid = normals_map(P, (H, W))
    skin = skin_mask(P[:, :2], (H, W)) & nvalid
    return fit(lin, N, skin, P)

def fit(lin, N, skin, P):
    H, W = skin.shape; im = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(np.clip(lin, 0, 1), 1 / 2.4) - 0.055)
    lum = lin.mean(-1)
    usable = skin & (im.max(-1) < 0.97) & (lum > 0.01)                              # clipped / black excluded
    A = np.concatenate([np.ones((H, W, 1)), N], -1)[usable]
    S = np.zeros_like(lin); K = []
    for ch in range(3):
        k = robust_fit(A, lin[..., ch][usable]); K.append(k)
        S[..., ch] = np.concatenate([np.ones((H, W, 1)), N], -1) @ k
    S = np.clip(S, 1e-3, None)
    ref = np.median(S[usable], 0)                                                    # light the face as if evenly lit
    corr = np.clip(lin / S * ref, 0, 1)
    Ks = np.array(K); light = Ks[:, 1:].mean(0); light /= np.linalg.norm(light) + 1e-9
    return dict(img=im, lin=lin, corr=corr, S=S, N=N, skin=skin, usable=usable, light=light, P=P, ambient=Ks[:, 0].mean(),
                directional=float(np.linalg.norm(Ks[:, 1:].mean(0))))

def lab(rgb_lin):
    srgb = np.where(rgb_lin <= 0.0031308, rgb_lin * 12.92, 1.055 * np.power(np.clip(rgb_lin, 0, 1), 1 / 2.4) - 0.055)
    L = cv2.cvtColor((np.clip(srgb, 0, 1) * 255).astype(np.uint8)[..., ::-1], cv2.COLOR_BGR2LAB).astype(np.float32)
    return L[..., 0] * 100 / 255, L[..., 1] - 128, L[..., 2] - 128

def tone_maps(R, dl=6.0, dchroma=3.0):
    """Pigment / shadow / unusable masks after light correction (person-relative thresholds)."""
    L, a, b = lab(R['corr'][..., ::-1])
    u = R['usable']
    Lm, am, bm = np.median(L[u]), np.median(a[u]), np.median(b[u])
    # local context: compare each pixel with its neighbourhood (removes any residual slow gradient)
    Lloc = cv2.GaussianBlur(np.where(u, L, Lm), (0, 0), 12)
    dev = L - Lloc
    chroma_shift = np.hypot(a - am, b - bm)
    dark = (dev < -dl) & u
    pigment = dark & ((chroma_shift > dchroma) | (b - bm > 1.5) | (a - am > 2.0))
    shadow = dark & ~pigment
    return dict(L=L, a=a, b=b, dev=dev, pigment=pigment, shadow=shadow)

def region_masks(R):
    P2 = R['P'][:, :2]; H, W = R['skin'].shape; out = {}
    for k, v in SKIN.items():
        m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [P2[v].astype(np.int32)], 1); out[k] = (m > 0) & R['usable']
    return out
