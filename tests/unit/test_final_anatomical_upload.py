"""Fail closed before model execution when an upload has no anatomical anchor."""
import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
from dental_upload import upload_roi, UploadError

@pytest.mark.parametrize('colour',[(210,190,170),(30,30,40),(255,255,255)])
def test_no_landmarks_cannot_create_a_mouth_from_colour(colour):
    image=np.full((200,400,3),colour,dtype=np.uint8)
    image[70:130,50:350]=(100,110,200)
    image[85:115,80:320]=(210,220,225)
    with pytest.raises(UploadError,match='MOUTH_ANATOMY_UNVERIFIED'):
        upload_roi(image,None)
