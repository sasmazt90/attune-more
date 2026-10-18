"""Simulator identity must never be presented as a user's real name."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
from mental_provider import LocalFallbackMentalProvider
@pytest.mark.parametrize('text,driving',[('Bugün yeni bir kitap okudum.',False),('İş stresi',False),('Yorgunum',False),('İş stresi',True),('Bugün yeni bir film izledim.',True)])
def test_demo_reply_does_not_invent_simulator_identity(text,driving):
    reply=LocalFallbackMentalProvider().generate_reply(text,driving,[],driver_name='Ahmet Yılmaz')['reply']
    assert 'Ahmet' not in reply and 'Yılmaz' not in reply
