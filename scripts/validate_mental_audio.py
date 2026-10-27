#!/usr/bin/env python3
"""Offline PCM/integrity/join checks and independent pronunciation screening.

ASR agreement is a screening signal, never proof of natural prosody or native
pronunciation. Models/caches stay outside the repository; no network inference.
"""
import argparse
from array import array
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import socket
import sys
import time
import unicodedata
import wave

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'apps/vehicle-app/public'
MANIFEST=PUBLIC/'audio/mental/v1/female-calm-v1-manifest.json'


def fingerprint(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def normalize(text,language):
    text=unicodedata.normalize('NFC',text)
    if language=='tr':text=text.replace('I','ı').replace('İ','i')
    text=text.casefold().replace('i\u0307','i').replace('’',"'")
    if language=='en':
        for a,b in [("what's",'what is'),("you're",'you are'),("don't",'do not'),("can't",'cannot')]:text=text.replace(a,b)
    tokens=re.findall(r'\w+',text)
    return ['okay' if language=='en' and t=='ok' else t for t in tokens]


def distance(left,right):
    previous=list(range(len(right)+1))
    for i,a in enumerate(left,1):
        current=[i]
        for j,b in enumerate(right,1):current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(a!=b)))
        previous=current
    return previous[-1]


def pronunciation(expected,recognized,language):
    a,b=normalize(expected,language),normalize(recognized,language)
    wer=distance(a,b)/max(1,len(a));x,y=' '.join(a),' '.join(b);cer=distance(x,y)/max(1,len(x))
    formal={'de':{'sie','ihnen','ihr','ihre','ihren','ihrer'},'tr':{'siz','sizi','size','sizin','sizden','sizde'}}.get(language,set())
    required={t for t in a if t in formal or (language=='tr' and re.search(r'(?:s[ıiuü]n[ıiuü]z|[td][ıiuü]n[ıiuü]z)$',t))}
    formal_missing=bool(required-set(b))
    critical={'en':{'not','no','never','today','yesterday'},'de':{'nicht','nie','heute','gestern'},'tr':{'bugün','dün'}}.get(language,set())
    critical_missing=bool((set(a)&critical)-set(b))
    status='match' if a==b else 'near-match' if cer<=.08 and wer<=.2 and not formal_missing and not critical_missing else 'review-required'
    return {'transcript':recognized.strip(),'wordErrorRate':round(wer,4),'characterErrorRate':round(cer,4),
            'status':status,'formalAddressMissing':formal_missing,'criticalTokenMissing':critical_missing}


def inspect_wave(path):
    with wave.open(str(path),'rb') as w:
        if (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getcomptype())!=(1,2,24000,'NONE'):raise ValueError('INVALID_PCM_FORMAT')
        count=w.getnframes();raw=w.readframes(count)
    if not 0<count<=24000*60 or len(raw)!=count*2:raise ValueError('INVALID_OR_TRUNCATED_PCM')
    samples=array('h',raw)
    if sys.byteorder!='little':samples.byteswap()
    window=480
    active=[sum(s*s for s in samples[i:i+window])/len(samples[i:i+window])>196**2 for i in range(0,len(samples),window)]
    voiced=[i for i,a in enumerate(active) if a]
    metrics={'durationMs':round(count/24),'sampleRate':24000,'bytes':Path(path).stat().st_size,
        'peak':max(abs(s) for s in samples)/32768,'rms':(sum(s*s for s in samples)/len(samples))**.5/32768,
        'clippedSamples':sum(abs(s)>=32760 for s in samples),'leadingSilenceMs':voiced[0]*20 if voiced else round(count/24),
        'trailingSilenceMs':max(0,len(active)-1-voiced[-1])*20 if voiced else round(count/24)}
    issues=[]
    if metrics['clippedSamples']:issues.append('clipped-samples')
    if not voiced or metrics['rms']<.004:issues.append('silent-or-too-quiet')
    if metrics['leadingSilenceMs']>1000 or metrics['trailingSilenceMs']>1200:issues.append('excessive-edge-silence')
    return metrics,issues


class Recognizer:
    def __init__(self,root,provenance='provenance.json',threads=1):
        self.root=Path(root);self.provenance=json.loads((self.root/provenance).read_text());self.threads=threads
        self.model=(self.root/self.provenance['modelDirectory']).resolve()
        if not self.model.is_relative_to(self.root.resolve()):raise ValueError('ASR_MODEL_OUTSIDE_ROOT')
        for name,sha in self.provenance['files'].items():
            if fingerprint(self.model/name)!=sha:raise ValueError('ASR_MODEL_HASH_MISMATCH')
        def offline(*a,**kw):raise OSError('VALIDATION_NETWORK_DISABLED')
        socket.socket.connect=socket.socket.connect_ex=socket.socket.sendto=offline
        import sherpa_onnx
        if sherpa_onnx.__version__!=self.provenance['recognizerVersion']:raise ValueError('ASR_VERSION_MISMATCH')
        self.sherpa=sherpa_onnx;self.language=None;self.recognizer=None
    def transcribe(self,path,language):
        import soundfile as sf
        import soxr
        if self.language!=language:
            self.recognizer=None
            self.recognizer=self.sherpa.OfflineRecognizer.from_whisper(
                encoder=str(self.model/self.provenance.get('encoderFile','small-encoder.int8.onnx')),decoder=str(self.model/self.provenance.get('decoderFile','small-decoder.int8.onnx')),
                tokens=str(self.model/self.provenance.get('tokensFile','small-tokens.txt')),language=language,num_threads=self.threads)
            self.language=language
        samples,rate=sf.read(path,dtype='float32')
        if rate!=16000:samples=soxr.resample(samples,rate,16000,quality='HQ')
        stream=self.recognizer.create_stream();stream.accept_waveform(16000,samples)
        self.recognizer.decode_stream(stream)
        return stream.result.text


def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temporary.replace(path)


def scan(cache,recognizer,secondary=False):
    manifest=json.loads(MANIFEST.read_text());rows=json.loads((ROOT/'shared/mental/v1/content.json').read_text())['rows']
    expected={r['audioAssetId']:r for r in rows}
    if len(expected)!=414 or {e['assetId'] for e in manifest['entries']}!=set(expected):raise ValueError('CATALOG_INCOMPLETE')
    for language in ('tr','en','de'):
        for entry in (e for e in manifest['entries'] if e['language']==language and e.get('sha256')):
            row=expected[entry['assetId']]
            if row['exactText']!=entry['exactScript'] or entry['speakerProfile']!='female-calm-v1':raise ValueError('SCRIPT_OR_PROFILE_MISMATCH')
            path=PUBLIC/entry['audioPath'].lstrip('/')
            if not path.resolve().is_relative_to((PUBLIC/'audio/mental/v1').resolve()) or fingerprint(path)!=entry['sha256']:raise ValueError('AUDIO_HASH_MISMATCH')
            script_sha=hashlib.sha256(entry['exactScript'].encode()).hexdigest()
            old=cache['assets'].get(entry['assetId'],{})
            if secondary:
                if not old or old['pronunciationScreen']['status']=='match' or old.get('secondaryPronunciationScreen'):continue
                if old.get('sha256')!=entry['sha256']:raise ValueError('PRIMARY_SCREEN_HASH_CHANGED')
                screen=pronunciation(entry['exactScript'],recognizer.transcribe(path,language),language)
                old['secondaryPronunciationScreen']=screen
                if screen['status']!='review-required':
                    old['issues']=[issue for issue in old['issues'] if issue!='pronunciation-screen-review']
                    old['resolution']='secondary-independent-ASR-screen'
                yield entry['assetId']
                continue
            if old.get('sha256')==entry['sha256'] and old.get('scriptSHA256')==script_sha:continue
            metrics,issues=inspect_wave(path)
            recognized=recognizer.transcribe(path,language)
            screen=pronunciation(entry['exactScript'],recognized,language)
            if screen['status']=='review-required':issues.append('pronunciation-screen-review')
            cache['assets'][entry['assetId']]={'sha256':entry['sha256'],'scriptSHA256':script_sha,'language':language,
                'metrics':metrics,'pronunciationScreen':screen,'issues':issues,
                'approvalKind':'owner-listened-representative' if entry.get('ownerApprovedAt') else 'authorized-production-awaiting-validation'}
            yield entry['assetId']


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--asr-root',type=Path,required=True)
    parser.add_argument('--cache',type=Path,required=True);parser.add_argument('--watch',action='store_true')
    parser.add_argument('--provenance',default='provenance.json');parser.add_argument('--threads',type=int,choices=(1,2,4),default=1)
    parser.add_argument('--secondary',action='store_true',help='Recheck only uncertain primary readings; run after the primary watcher finishes.')
    args=parser.parse_args()
    if args.secondary:
        prior=json.loads(args.cache.read_text())
        current=json.loads(MANIFEST.read_text())['entries']
        if len(current)!=414 or any(not e.get('sha256') or prior['assets'].get(e['assetId'],{}).get('sha256')!=e['sha256'] for e in current):
            raise ValueError('PRIMARY_SCREENING_MUST_FINISH_BEFORE_SECONDARY')
    recognizer=Recognizer(args.asr_root,args.provenance,args.threads)
    cache=json.loads(args.cache.read_text()) if args.cache.exists() else {'schema':'mental-audio-screen-v1','assets':{},'verifier':recognizer.provenance,
        'limitations':['Independent ASR screening does not certify native pronunciation or natural prosody.','Near matches remain distinguishable from exact recognition.','Owner approval of the nine representative clips is preserved.']}
    if args.secondary:
        cache['secondaryVerifier']=recognizer.provenance
        # Preserve recognized text while applying the current formal-address
        # and negation/temporal policy to earlier primary screenings.
        entries={e['assetId']:e for e in json.loads(MANIFEST.read_text())['entries']}
        for key,row in cache['assets'].items():
            entry=entries[key];row['pronunciationScreen']=pronunciation(entry['exactScript'],row['pronunciationScreen']['transcript'],entry['language'])
            if row['pronunciationScreen']['status']=='review-required' and 'pronunciation-screen-review' not in row['issues']:row['issues'].append('pronunciation-screen-review')
    while True:
        for asset in scan(cache,recognizer,args.secondary):
            atomic_json(args.cache,cache)
            if len(cache['assets'])%5==0:print(json.dumps({'screened':len(cache['assets']),'reviewRequired':sum(bool(a['issues']) for a in cache['assets'].values()),'lastAsset':asset}),flush=True)
        entries=json.loads(MANIFEST.read_text())['entries']
        complete=len(entries)==414 and all(e.get('sha256') and cache['assets'].get(e['assetId'],{}).get('sha256')==e['sha256'] for e in entries)
        if complete or not args.watch:break
        time.sleep(15)
    print(json.dumps({'screened':len(cache['assets']),'statuses':dict(Counter(a['pronunciationScreen']['status'] for a in cache['assets'].values()))}),flush=True)


if __name__=='__main__':main()
