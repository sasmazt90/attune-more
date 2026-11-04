#!/usr/bin/env python3
"""Creates the Vision answer clips with OpenAI speech. Test fixtures only.

Natural speech is needed because real ASR hears robotic letters as other words:
espeak-ng "E upright" came back as "Yeah, right". Run once on the WEB host, which holds
the provider key. The key is read from its root-only file and never printed.
Cost is about 2,500 characters of speech.
"""
import argparse
import itertools
import json
from pathlib import Path
import re
import subprocess
import tarfile
import urllib.request

from vision_realistic import LETTERS, ROTATIONS, clip_name, phrase_for


def provider_settings(path='/etc/attune/provider.env'):
    values = {}
    for line in Path(path).read_text().splitlines():
        match = re.fullmatch(r'\s*([A-Z_]+)=(.*)', line)
        if match:
            values[match[1]] = match[2].strip().strip('"\'')
    return values['OPENAI_API_KEY'], values.get('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')


def speak(key, base, text, voice):
    request = urllib.request.Request(base + '/audio/speech', data=json.dumps({'model': 'gpt-4o-mini-tts', 'voice': voice, 'input': text, 'response_format': 'wav', 'speed': 0.95}).encode(),
                                     headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--voice', default='alloy')
    parser.add_argument('--archive', type=Path, help='Also write a small opus archive for the AAOS host')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    key, base = provider_settings()
    clips = {clip_name(l, r, m, c): phrase_for(l, r, m, c) for l, r, m, c in itertools.product(LETTERS, ROTATIONS, (False, True), (False, True))}
    clips['cannot-see.wav'] = "I can't see it."
    raw = args.out / 'raw.wav'
    for name, text in clips.items():
        target = args.out / name
        if target.exists():
            continue
        raw.write_bytes(speak(key, base, text, args.voice))
        # Leading silence lets the recognizer open; trailing silence ends the utterance.
        subprocess.check_call(['ffmpeg', '-loglevel', 'error', '-y', '-i', str(raw), '-af', 'adelay=250,apad=pad_dur=0.6', '-ar', '48000', '-ac', '1', str(target)])
    raw.unlink(missing_ok=True)
    manifest = {name: text for name, text in clips.items()}
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=1))
    if args.archive:
        with tarfile.open(args.archive, 'w:gz') as tar:
            for name in clips:
                opus = args.out / (name[:-4] + '.opus')
                subprocess.check_call(['ffmpeg', '-loglevel', 'error', '-y', '-i', str(args.out / name), '-c:a', 'libopus', '-b:a', '24k', str(opus)])
                tar.add(opus, arcname=opus.name)
                opus.unlink()
            tar.add(args.out / 'manifest.json', arcname='manifest.json')
    print(json.dumps({'clips': len(clips), 'characters': sum(map(len, clips.values())), 'archiveBytes': args.archive.stat().st_size if args.archive else None}))


if __name__ == '__main__':
    main()
