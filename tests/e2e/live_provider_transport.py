"""Identify the SDK's actual synchronous transport; unknown families fail shut."""
import importlib

def sdk_http_family(default_client):
    for name in ['httpx','httpx2']:
        try:
            family=importlib.import_module(name)
        except ModuleNotFoundError:
            continue
        if isinstance(default_client,type) and issubclass(default_client,family.Client):
            return family
    raise RuntimeError('Unsupported SDK transport; no provider server started')
