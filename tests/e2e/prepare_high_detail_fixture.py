"""Public-domain NASA portrait, native-pixel crop only; no user photo or enhancement.

This front-pose fixture cannot stand for three different poses. MediaPipe and
the production quality/pose gates must admit it, without injected landmarks.
"""
import sys
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request
from PIL import Image

SOURCE = 'https://upload.wikimedia.org/wikipedia/commons/f/f2/Eileen_Collins%2C_early_NASA_portrait.jpg'
PAGE = 'https://commons.wikimedia.org/wiki/File:Eileen_Collins,_early_NASA_portrait.jpg'
SHA256 = '788e97c3a72c1a3e06a21a24841a6e4b71b38df7b37c0699658b091043b45207'
DIGITAL='--digital-source' in sys.argv
if DIGITAL:
    SOURCE='https://upload.wikimedia.org/wikipedia/commons/6/65/Robert_L._Behnken_in_2018.jpg'
    PAGE='https://commons.wikimedia.org/wiki/File:Robert_L._Behnken_in_2018.jpg'
    SHA256='d99b03d2c2b681b4d09a7c11b4b0b8344fa0c8c32c6b214e30a7244d66ff9766'
NAME='digital-detail' if DIGITAL else 'high-detail'
SIZE=(4500,6000) if DIGITAL else (2250,2848)
CROP=(1450,450,1920,2160) if DIGITAL else (400,150,1280,960)
FIX = Path('audit-fixtures'); FIX.mkdir(exist_ok=True)
OUT = Path('audit-results/user-followup-20261005') / NAME; OUT.mkdir(parents=True, exist_ok=True)
photo = FIX / (NAME+'-nasa.jpg')
if not photo.exists():
    request = urllib.request.Request(SOURCE, headers={'User-Agent': 'AttuneFixtureVerification/1.0'})
    with urllib.request.urlopen(request, timeout=30) as response:
        photo.write_bytes(response.read())
assert hashlib.sha256(photo.read_bytes()).hexdigest() == SHA256
with Image.open(photo) as original:
    assert original.size == SIZE
    # Native crop excludes branding and preserves every original face pixel.
    x,y,w,h=CROP
    original.crop((x,y,x+w,y+h)).save(FIX / (NAME+'-native-crop.png'))
ffmpeg = shutil.which('ffmpeg')
if not ffmpeg:
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-loop', '1',
                '-i', str(FIX / (NAME+'-native-crop.png')), '-t', '3', '-r', '15',
                '-pix_fmt', 'yuv420p', str(FIX / (NAME+'.y4m'))], check=True)
(OUT / 'source-provenance.json').write_text(json.dumps({
    'source': SOURCE, 'page': PAGE, 'author': 'NASA / Robert Markowitz' if DIGITAL else 'NASA',
    'rights': 'Public domain in the United States, solely NASA-created image',
    'policy': 'https://www.nasa.gov/nasa-brand-center/images-and-media/',
    'sourceSha256': SHA256, 'originalPixels': SIZE,
    'nativeCrop': CROP, 'resizing': False,
    'conversion': 'JPEG decode to lossless PNG crop, then uncompressed YUV420 video; chroma subsampling only',
    'enhancements': [], 'qualityThresholdChanged': False,
    'controlledFixture': True, 'userPhotoAcceptance': False,
    'oneFrontPoseOnly': True, 'endorsement': False
}, indent=2), encoding='utf-8')
print(f'Prepared native {CROP[2]}x{CROP[3]} {NAME} front-only controlled fixture')
