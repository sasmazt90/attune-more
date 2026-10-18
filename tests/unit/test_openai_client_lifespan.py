"""Actual FastAPI lifespan releases the SDK pool, including exceptional exit."""
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path('services/core-api').resolve()))
import main

@pytest.mark.parametrize('exceptional_exit',[False,True])
def test_app_lifespan_closes_pool_once(monkeypatch,exceptional_exit):
 closed=[]
 monkeypatch.setattr(main,'close_openai_client',lambda:closed.append(True))
 try:
  with TestClient(main.app) as client:
   assert client.get('/api/health').status_code==200
   assert closed==[]
   if exceptional_exit:raise RuntimeError('Controlled test exit')
 except RuntimeError:
  assert exceptional_exit
 assert closed==[True]
