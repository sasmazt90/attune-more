"""Reuse the SDK connection pool. Configuration changes close the previous client.
No request, reply or credential is written to logs or storage.
"""
from threading import RLock

_lock = RLock()
_client = None
_configuration = None


def get_openai_client(api_key: str, base_url=None):
    global _client, _configuration
    from openai import OpenAI
    configuration = (api_key, base_url)
    with _lock:
        if _client is not None and _configuration == configuration and not _client.is_closed():
            return _client
        if _client is not None:
            _client.close()
        _client = None
        _configuration = None
        candidate = OpenAI(api_key=api_key, base_url=base_url, timeout=25, max_retries=0)
        _client = candidate
        _configuration = configuration
        return candidate


def close_openai_client():
    global _client, _configuration
    with _lock:
        if _client is not None:
            _client.close()
        _client = None
        _configuration = None
