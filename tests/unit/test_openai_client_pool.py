"""Connection pooling must preserve zero retries and close stale configurations."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import threading
import pytest

spec=importlib.util.spec_from_file_location('pool_under_test',Path('services/core-api/openai_client.py'))
pool=importlib.util.module_from_spec(spec);spec.loader.exec_module(pool)

@pytest.fixture
def sdk(monkeypatch):
 import openai
 created=[]
 class Client:
  def __init__(self,**options): self.options=options; self.closed=False;created.append(self)
  def is_closed(self):return self.closed
  def close(self):self.closed=True
 monkeypatch.setattr(openai,'OpenAI',Client)
 pool.close_openai_client()
 yield created
 pool.close_openai_client()

def test_repeated_chat_tts_summary_share_zero_retry_pool(sdk):
 clients=[pool.get_openai_client('nonsecret-fixture') for _ in range(7)]
 assert len(sdk)==1 and all(c is clients[0] for c in clients)
 assert sdk[0].options=={'api_key':'nonsecret-fixture','base_url':None,'timeout':25,'max_retries':0}

def test_configuration_change_closes_old_pool(sdk):
 old=pool.get_openai_client('first-nonsecret-fixture')
 new=pool.get_openai_client('second-nonsecret-fixture')
 assert old.closed and new is not old and not new.closed
 alternate=pool.get_openai_client('second-nonsecret-fixture','http://127.0.0.1:9999/v1')
 assert new.closed and alternate is not new

def test_failed_initialization_is_not_cached(sdk,monkeypatch):
 import openai
 original=openai.OpenAI;attempts=[]
 def fail_once(**options):
  attempts.append(True)
  if len(attempts)==1:raise RuntimeError('nonsecret synthetic initialization fault')
  return original(**options)
 monkeypatch.setattr(openai,'OpenAI',fail_once)
 with pytest.raises(RuntimeError):pool.get_openai_client('nonsecret-fixture')
 assert pool._client is None and pool._configuration is None
 assert pool.get_openai_client('nonsecret-fixture') is sdk[0] and len(attempts)==2

def test_concurrent_initialization_creates_one_client(sdk):
 barrier=threading.Barrier(8);results=[]
 def get():barrier.wait();results.append(pool.get_openai_client('nonsecret-fixture'))
 threads=[threading.Thread(target=get) for _ in range(8)]
 for thread in threads:thread.start()
 for thread in threads:thread.join(timeout=5);assert not thread.is_alive()
 assert len(sdk)==1 and len(results)==8 and all(c is sdk[0] for c in results)

def test_shutdown_and_already_closed_client_can_reinitialize(sdk):
 old=pool.get_openai_client('nonsecret-fixture');old.close()
 new=pool.get_openai_client('nonsecret-fixture');assert new is not old
 pool.close_openai_client();pool.close_openai_client()
 assert new.closed and pool._configuration is None and pool._client is None
