"""SDK transport drift cannot silently bypass keyless preparation admission."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import socket
import pytest

def load(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).parents[1]/'e2e'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

@pytest.mark.parametrize('selected',['httpx','httpx2'])
def test_selects_actual_sdk_client_family(monkeypatch,selected):
    module=load('live_provider_transport')
    families={name:SimpleNamespace(Client=type(name+'Client',(),{})) for name in ['httpx','httpx2']}
    monkeypatch.setattr(module.importlib,'import_module',lambda name:families[name])
    class Default(families[selected].Client):pass
    assert module.sdk_http_family(Default) is families[selected]

def test_unknown_sdk_transport_refuses_before_server_or_provider(monkeypatch):
    module=load('live_provider_transport')
    monkeypatch.setattr(module.importlib,'import_module',lambda name:SimpleNamespace(Client=type('Known',(),{})))
    with pytest.raises(RuntimeError):module.sdk_http_family(type('Unknown',(),{}))

@pytest.mark.parametrize('address,allowed',[(('203.0.113.1',443),False),(('127.0.0.1',8000),True)])
def test_preparation_socket_boundary_is_independent_of_sdk(monkeypatch,address,allowed):
    module=load('live_provider_fixtures');calls=[]
    monkeypatch.setattr(socket.socket,'connect',lambda self,target:calls.append(target))
    original=socket.socket.connect
    try:
        blocked=module.deny_nonloopback_connections()
        with socket.socket() as connection:
            if allowed:connection.connect(address)
            else:
                with pytest.raises(PermissionError):connection.connect(address)
        assert len(calls)==int(allowed) and len(blocked)==int(not allowed)
    finally:socket.socket.connect=original
