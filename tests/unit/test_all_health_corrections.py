"""Concrete all-module audit regressions; no physical/clinical acceptance claim."""
import sys
from pathlib import Path
import cv2
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
from appearance_analysis import local_color_signals, elongated_dark_mask
from conversation_control import conversation_control

def test_relative_redness_local_patch_not_uniform_cast_or_darkness():
    base=np.full((100,120,3),(120,145,180),np.uint8)
    valid=np.ones(base.shape[:2],bool)
    tone,red,_=local_color_signals(base,valid)
    assert tone.max()==0 and red.max()==0
    for color in [(100,125,165),(95,150,205),(70,85,110)]:
        uniform=np.full_like(base,color)
        assert local_color_signals(uniform,valid)[1].max()==0
    patch=base.copy();patch[25:75,40:80]=(105,115,205)
    tone,red,meta=local_color_signals(patch,valid)
    assert red[30:70,45:75].mean()>10 and red[:20].max()==0
    assert tone[30:70,45:75].mean()>0
    assert meta['redScale']==2 and meta['redDeadbandA']==2
    assert np.array_equal(base,np.full_like(base,(120,145,180)))

def test_hair_excludes_filament_preserves_round_dark_focus():
    gray=np.full((100,120),170,np.uint8)
    cv2.circle(gray,(25,50),2,40,-1)
    cv2.line(gray,(70,25),(75,75),30,1)
    mask=elongated_dark_mask(gray)
    assert not mask[50,25] and mask[50,73]

@pytest.mark.parametrize('text',['Görüşmeyi bitir.','Hoşça kal','Şimdilik bu kadar','Lütfen konuşmayı sonlandır'])
def test_explicit_departure_has_finish_action(text):
    result=conversation_control(text)
    assert result['sessionAction']=='finish' and result['providerType']=='CONVERSATION_CONTROL'

@pytest.mark.parametrize('text',['Bugün iyi bir kitap okudum.','İşim bitince dışarı çıktım.','Arkadaşıma hoşça kal dedim.','Görüşürüz demek istemiyorum.'])
def test_normal_context_is_not_an_exit_command(text):
    assert conversation_control(text) is None

def test_omitted_mental_measurements_are_not_invented():
    from main import CreateSessionPayload
    value=CreateSessionPayload(summaryText='Kişisel olmayan kontrol',recurringThemes=[])
    assert value.durationSeconds is None and value.moodBefore is None and value.moodAfter is None
