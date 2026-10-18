"""Audition the frozen 0..9 bank without synthesis or changing product files."""
import hashlib,json
from pathlib import Path
import numpy as np
from scipy.io import wavfile

ROOT=Path(__file__).resolve().parents[1]
BANK=ROOT/'apps/vehicle-app/public/audio/hearing-bank'
OUT=ROOT/'audit-results/combined-health-20261008/audio-render'


def main():
    manifest=json.loads((BANK/'manifest.json').read_text('utf8'))
    assert manifest['voice']=='tr-TR-AhmetNeural' and manifest['rate']=='-10%' and manifest['pitch']=='-10Hz'
    sources=[];pieces=[];rate=None
    for digit in range(10):
        entry=next(row for row in manifest['digits'] if row['digit']==digit)
        path=BANK/Path(entry['url']).name
        assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256']
        hz,pcm=wavfile.read(path)
        assert pcm.ndim==1 and np.issubdtype(pcm.dtype,np.floating) and np.isfinite(pcm).all()
        if rate is None:rate=hz
        assert hz==rate and len(pcm)>0
        pieces.extend([pcm.astype(np.float64),np.zeros(round(rate*.65))])
        sources.append(dict(digit=digit,text=entry['text'],sha256=entry['sha256']))
    joined=np.concatenate(pieces)
    # A single common attenuation; no pitch, rate, content or per-digit change.
    gain=min(1.,.08/max(float(np.abs(joined).max()),1e-9));joined*=gain
    assert np.isfinite(joined).all() and float(np.abs(joined).max())<=.080000001
    OUT.mkdir(parents=True,exist_ok=True);path=OUT/'fixed-bank-0-to-9.wav'
    wavfile.write(path,rate,np.rint(joined*32767).astype(np.int16))
    proof=dict(bankVersion=manifest['version'],sources=sources,sampleRate=rate,
        commonGain=gain,peak=float(np.abs(joined).max()),durationSeconds=len(joined)/rate,
        previewSHA256=hashlib.sha256(path.read_bytes()).hexdigest(),
        synthesisCalls=0,auditoryAcceptance=False,clinicalValidation=False,
        meaning='Ordered audition of the actual frozen bank; listening acceptance remains open.')
    (OUT/'fixed-bank-preview.json').write_text(json.dumps(proof,indent=2),'utf8')
    print(json.dumps(proof))


if __name__=='__main__':main()
