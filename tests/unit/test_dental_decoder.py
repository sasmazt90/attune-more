"""Decoder limits exercise only small generated geometry controls, not diagnosis."""
import base64,io,struct,sys,zlib
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
from dental_upload import decode_upload,UploadError

def uri(raw):return 'data:image/png;base64,'+base64.b64encode(raw).decode()
def encoded(im,fmt='PNG',**kw):
 b=io.BytesIO();im.save(b,format=fmt,**kw);return uri(b.getvalue())

@pytest.mark.parametrize('raw,reason',[(b'not-an-image','UNSUPPORTED_FORMAT'),(b'\xff\xd8\xffbroken','DECODE_FAILED'),(b'\x89PNG\r\n\x1a\nbroken','DECODE_FAILED')])
def test_bad_signature_and_broken_decoder(raw,reason):
 with pytest.raises(UploadError,match=reason):decode_upload(uri(raw))

def test_file_and_pixel_limits_before_large_allocation():
 from dental_upload import LIMITS
 with pytest.raises(UploadError,match='FILE_LIMIT'):decode_upload('x'*(int(LIMITS['maxFileBytes']*4/3)+300))
 def chunk(name,data):return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data)&0xffffffff)
 raw=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',8193,128,8,2,0,0,0))+chunk(b'IDAT',b'')+chunk(b'IEND',b'')
 with pytest.raises(UploadError,match='PIXEL_LIMIT'):decode_upload(uri(raw))

def test_alpha_and_animation_are_not_still_opaque_photos():
 with pytest.raises(UploadError,match='TRANSPARENT_PHOTO'):decode_upload(encoded(Image.new('RGBA',(128,128),(255,255,255,100))))
 frames=[Image.new('RGB',(128,128),c) for c in ['red','blue']]
 with pytest.raises(UploadError,match='PIXEL_LIMIT'):decode_upload(encoded(frames[0],save_all=True,append_images=frames[1:],duration=100))

@pytest.mark.parametrize('fmt',['PNG','JPEG','WEBP'])
def test_supported_formats_keep_oriented_dimensions_and_rgba_hash(fmt):
 import hashlib
 im=Image.new('RGB',(150,128),(50,100,200))
 photo,digest,normalized,source=decode_upload(encoded(im,fmt))
 assert photo.shape==(128,150,3) and source['originalFormat']==fmt and normalized.startswith('data:image/png;base64,')
 rgba=np.concatenate([photo[:,:,::-1],np.full((128,150,1),255,np.uint8)],axis=2)
 assert digest==hashlib.sha256(rgba.tobytes()).hexdigest()

def test_exif_rotation_is_applied_once():
 im=Image.new('RGB',(150,128),(50,100,200));exif=Image.Exif();exif[274]=6
 photo,digest,normalized,source=decode_upload(encoded(im,'JPEG',exif=exif))
 assert photo.shape==(150,128,3) and (source['sourceWidth'],source['sourceHeight'])==(128,150)
 again,second,_,_=decode_upload(normalized)
 assert second==digest and np.array_equal(photo,again)
