#!/usr/bin/env python3
"""QA-01. Asks the running API for a reply and a summary in each language and checks the language of the text.

Uses the real provider with cloud consent, as the application does. The check is deliberately simple: it looks for
letters and common words of the other languages. A person still has to read the saved output, which is written in full.
Usage: mental_language_probe.py --port <api port> --out <file>
"""
import argparse
import json
from pathlib import Path
import re
import urllib.request

CASES = {
    'tr': ['Bu hafta işte çok gerginim ve uykum düzensiz.', 'Akşamları yürüyüş yapınca biraz rahatlıyorum.'],
    'en': ['I have been very tense at work this week and my sleep is irregular.', 'Walking in the evening helps me relax a little.'],
    'de': ['Ich bin diese Woche bei der Arbeit sehr angespannt und schlafe unregelmäßig.', 'Abends spazieren zu gehen entspannt mich ein wenig.'],
}
# Words that should not appear in the other languages' text. "Gergin" is the reported fault.
FOREIGN = {
    'tr': r'\b(the|and|you|feeling|und|nicht|sich|ich)\b',
    'en': r'[çğıİşŞĞ]|\b(gergin|yorgun|rahat|nötr|und|nicht|sich|ich|bir|için|ve)\b',
    'de': r'[çğıİşŞĞ]|\b(gergin|yorgun|rahat|nötr|the|you|feeling|bir|için|ve)\b',
}


def post(port, path, language, body):
    request = urllib.request.Request('http://127.0.0.1:{}{}?language={}'.format(port, path, language), data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    report = {'boundary': 'Real provider, API level, short scripted conversation. Not a full language review.', 'languages': {}}
    for language, said in CASES.items():
        messages, replies = [], []
        for text in said:
            reply = post(args.port, '/api/mental/converse', language, {'userMessage': text, 'history': messages, 'cloudConsent': True})
            messages += [{'role': 'user', 'content': text}, {'role': 'assistant', 'content': reply['reply']}]
            replies.append(reply['reply'])
        analysis = post(args.port, '/api/mental/analyze-session', language, {'messages': messages, 'cloudConsent': True})
        visible = {key: analysis.get(key) for key in ('summaryText', 'professionalSupportReason', 'spokenSummary', 'moodTrend', 'recommendations') if key in analysis}
        checked = ' '.join(replies + [str(visible.get('summaryText') or ''), str(visible.get('professionalSupportReason') or ''), str(visible.get('spokenSummary') or '')])
        # Lower-cased first: ignoring case in the pattern would treat the Turkish dotless i as an i.
        foreign = sorted(set(m.group(0) for m in re.finditer(FOREIGN[language], checked.lower())))
        words = [len(r.split()) for r in replies]
        report['languages'][language] = {'said': said, 'replies': replies, 'replyWords': words, 'analysis': visible, 'foreignMatches': foreign, 'passed': not foreign and all(w <= 25 for w in words)}
        print(language, 'PASS' if report['languages'][language]['passed'] else 'CHECK', 'words', words, 'foreign', foreign, flush=True)
    report['status'] = 'PASS' if all(v['passed'] for v in report['languages'].values()) else 'CHECK'
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1, ensure_ascii=False), 'utf8')
    print(report['status'])


if __name__ == '__main__':
    main()
