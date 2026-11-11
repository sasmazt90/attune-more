#!/usr/bin/env python3
"""Acceptance of the normal closing's short spoken line with the real provider (WEB host, synthetic conversations).

Runs the branch's analyzer in process with the product API's environment (read in memory from the running
attune-api@web process, never written or printed) and the same prompt as /api/mental/analyze-session with
spokenSummary=true: one provider call per analysis. The provider's raw line is captured before server validation so
that rejected lines can be reviewed; the result keeps the validation status and the line the API would return.
Usage: /opt/attune-venv/bin/python spoken_summary_probe.py --source <checkout> --out <file.json> [--repeats 5]
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from closing_realpath_probe import CONVERSATIONS, product_api_environment  # noqa: E402

# Different topics per language, including a negation and a mixed statement; synthetic and non-personal.
DIVERSE = {
    'tr': [
        [('user', 'Annemle sık sık tartışıyoruz, bu beni üzüyor.'), ('assistant', 'Bu tartışmalar en çok ne zaman oluyor?'), ('user', 'Genelde akşam yemeğinde, ikimiz de yorgunken.')],
        [('user', 'Sınavlarım yaklaşıyor ve odaklanamıyorum.'), ('assistant', 'Odaklanmanı en çok ne zorluyor?'), ('user', 'Telefonum sürekli dikkatimi dağıtıyor.')],
        [('user', 'Uyku sorunum yok ama işte çok yoruluyorum.'), ('assistant', 'Yorgunluk günün hangi saatinde artıyor?'), ('user', 'Öğleden sonra toplantılardan sonra.')],
        [('user', 'Bu ay kiramı ödemekte zorlanıyorum.'), ('assistant', 'Bu durum seni nasıl etkiliyor?'), ('user', 'Geceleri hesap yapıp duruyorum.')],
        [('user', 'Babamın bakımını üstlendim ve kendime zaman kalmıyor.'), ('assistant', 'Kendin için ne yapabilmek isterdin?'), ('user', 'Haftada bir yürüyüşe çıkmak isterdim.')],
        [('user', 'Yeni işime alıştım, ekip arkadaşlarım iyi ama yol çok uzun.'), ('assistant', 'Yol seni nasıl etkiliyor?'), ('user', 'Eve geldiğimde enerjim kalmıyor.')],
    ],
    'en': [
        [('user', 'My brother and I argue a lot and it upsets me.'), ('assistant', 'When do the arguments usually happen?'), ('user', 'Mostly at family dinners.')],
        [('user', 'My exams are coming up and I cannot focus.'), ('assistant', 'What makes focusing hardest?'), ('user', 'My phone keeps distracting me.')],
        [('user', 'I am not worried about my health, only about my job.'), ('assistant', 'What about the job worries you?'), ('user', 'There are rumours about layoffs.')],
        [('user', 'I feel lonely since I moved to a new city.'), ('assistant', 'What do you miss most?'), ('user', 'Weekend breakfasts with my friends.')],
        [('user', 'Caring for my father takes all my energy.'), ('assistant', 'What would you like to do for yourself?'), ('user', 'Go swimming once a week.')],
        [('user', 'My new job is fine and the team is kind, but the commute is long.'), ('assistant', 'How does the commute affect you?'), ('user', 'I arrive home exhausted.')],
    ],
    'de': [
        [('user', 'Ich streite oft mit meiner Schwester und das macht mich traurig.'), ('assistant', 'Wann kommt es meistens zum Streit?'), ('user', 'Meistens bei Familienfeiern.')],
        [('user', 'Meine Prüfungen stehen bevor und ich kann mich nicht konzentrieren.'), ('assistant', 'Was erschwert die Konzentration am meisten?'), ('user', 'Mein Handy lenkt mich ständig ab.')],
        [('user', 'Ich habe keine Angst vor der Prüfung, nur vor dem Ergebnis.'), ('assistant', 'Was genau beschäftigt Sie am Ergebnis?'), ('user', 'Dass ich das Stipendium verlieren könnte.')],
        [('user', 'Seit dem Umzug fühle ich mich einsam.'), ('assistant', 'Was vermissen Sie am meisten?'), ('user', 'Die Abende mit meinen Freunden.')],
        [('user', 'Die Pflege meines Vaters kostet mich viel Kraft.'), ('assistant', 'Was würden Sie gern für sich tun?'), ('user', 'Einmal pro Woche schwimmen gehen.')],
        [('user', 'Die neue Arbeit gefällt mir, das Team ist nett, aber der Weg ist sehr lang.'), ('assistant', 'Wie wirkt sich der Weg auf Sie aus?'), ('user', 'Ich komme erschöpft nach Hause.')],
    ],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--corpus', choices=('closing', 'diverse'), default='closing')
    args = parser.parse_args()
    env, _ = product_api_environment(8000)
    os.environ.update(env)
    sys.path.insert(0, str(Path(args.source) / 'services/core-api'))
    import mental_analysis
    from mental_provider import get_active_session_analyzer
    from localization import request_language
    raw = []
    original = mental_analysis.validate_spoken_summary

    def capture(value, language, messages):
        raw.append(value)
        return original(value, language, messages)
    mental_analysis.validate_spoken_summary = capture
    rows = []
    for language, conversations in (DIVERSE if args.corpus == 'diverse' else CONVERSATIONS).items():
        for n, turns in enumerate(conversations, 1):
            messages = [{'role': role, 'content': text} for role, text in turns]
            for repeat in range(args.repeats):
                analyzer = get_active_session_analyzer()
                analyzer.spoken_summary = True
                token = request_language.set(language)
                started = time.perf_counter()
                try:
                    result = analyzer.analyze_session(messages)
                    error = None
                except Exception as exc:  # provider failure is a result, not a crash
                    result, error = {}, type(exc).__name__ + ':' + str(getattr(exc, 'detail', ''))[:80]
                finally:
                    request_language.reset(token)
                line = raw[-1] if raw else None
                rows.append({'language': language, 'conversation': f'{language}-{"d" if args.corpus == "diverse" else "c"}{n}', 'repeat': repeat, 'seconds': round(time.perf_counter() - started, 3),
                             'providerLine': line, 'providerWords': len(line.split()) if isinstance(line, str) else None,
                             'status': result.get('spokenSummaryStatus'), 'spokenSummary': result.get('spokenSummary'),
                             'summaryWords': len((result.get('summaryText') or '').split()), 'error': error})
                raw.clear()
                Path(args.out).write_text(json.dumps({'schema': 'attune-mental-spoken-summary-acceptance-v1', 'corpus': args.corpus,
                                                      'conversations': {f'{l}-{"d" if args.corpus == "diverse" else "c"}{i}': [t for r, t in turns if r == 'user']
                                                                        for l, convs in (DIVERSE if args.corpus == 'diverse' else CONVERSATIONS).items() for i, turns in enumerate(convs, 1)},
                                                      'model': analyzer.model if hasattr(analyzer, 'model') else None,
                                                      'rows': rows}, ensure_ascii=False, indent=1) + '\n', 'utf-8')
    total = {}
    for row in rows:
        total.setdefault(row['language'], {}).setdefault(row['status'] or row['error'], 0)
        total[row['language']][row['status'] or row['error']] += 1
    print(json.dumps(total, ensure_ascii=False))


if __name__ == '__main__':
    main()
