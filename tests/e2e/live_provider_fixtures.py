"""Preparation only: SDK HTTP transport fixtures, never a LIVE acceptance proof."""
import json
from pathlib import Path
import ipaddress
import socket

NONSECRET = 'attune-keyless-fixture-not-a-credential'

def deny_nonloopback_connections():
    """Independent preparation egress boundary, including future SDK drift."""
    blocked=[]
    original=socket.socket.connect
    def connect(self,address):
        try:allowed=isinstance(address,tuple) and (address[0]=='localhost' or ipaddress.ip_address(address[0]).is_loopback)
        except ValueError:allowed=False
        if not allowed:
            blocked.append('NON_LOOPBACK_CONNECT_BLOCKED')
            raise PermissionError('Keyless preparation forbids external sockets')
        return original(self,address)
    socket.socket.connect=connect
    return blocked

def install_fixture(mode, output, gate, httpx):
    """Replace transport selection, retaining the actual Client.send/SDK pipeline."""
    fixture_calls = []
    def respond(request):
        marker = json.loads((output/'run-consumed.json').read_text())
        assert marker['runId'] == output.name  # Marker exists before transport.
        assert gate.pending is not None
        data = json.loads(request.content)
        kind = gate.pending
        fixture_calls.append(kind)
        if mode == 'failure':
            return httpx.Response(503, json={'error': {'message': 'Preparation failure', 'type': 'server_error'}})
        if kind == 'tts':
            return httpx.Response(200, stream=httpx.ByteStream((Path(__file__).parent/'fixtures/preparation-tone.mp3').read_bytes()), headers={'content-type': 'audio/mpeg'})
        content = (f"Anahtarsız hazırlık yanıtı {gate.counts['conversation']}." if kind == 'conversation' else json.dumps({
            'summaryText':'Anahtarsız hazırlık oturumu.', 'themes':['hazırlık'], 'moodTrend':'NEUTRAL',
            'professionalSupportSuggested':False, 'professionalSupportReason':None}))
        return httpx.Response(200, json={'id':'preparation-only','object':'chat.completion','created':0,'model':data['model'],
            'choices':[{'index':0,'message':{'role':'assistant','content':content},'finish_reason':'stop'}]})
    transport = httpx.MockTransport(respond)
    httpx.Client._transport_for_url = lambda self, url: transport
    return fixture_calls
