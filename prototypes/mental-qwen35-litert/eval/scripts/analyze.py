"""Computes every reported KOL B metric from raw run files and the published author labels.
Usage: python -I analyze.py RUNS_DIR LABELS_DIR OUT_JSON"""
import json, os, re, statistics, sys, unicodedata
RUNS, LABELS, OUT = sys.argv[1:4]
J = lambda p: json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None
def mmm(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return {'n': len(xs), 'min': min(xs), 'median': round(statistics.median(xs)), 'max': max(xs)} if xs else {'n': 0}
def p95(xs):
    xs = sorted(x for x in xs if isinstance(x, (int, float)))
    return xs[max(0, int(round(0.95 * len(xs))) - 1)] if len(xs) >= 20 else None
out = {}

# ---- B2 follow-up turns (host model) ----
b2 = J(f'{RUNS}/eval_b2_corpus.json'); lab = J(f'{LABELS}/b2_labels.json')
if b2:
    per = {}
    for r in b2['results']:
        L = per.setdefault(r['language'], {'turns': 0, 'source': {}, 'issues': {}, 'firstTokenMs': [], 'modelMs': [], 'engineCreateMs': [], 'replyLabels': {}})
        L['engineCreateMs'].append(r['engineCreateMs'])
        for i, t in enumerate(r['turns']):
            L['turns'] += 1; L['source'][t['source']] = L['source'].get(t['source'], 0) + 1
            for k in t.get('issues') or []: L['issues'][k] = L['issues'].get(k, 0) + 1
            L['firstTokenMs'].append(t['firstTokenMs']); L['modelMs'].append(t['modelMs'])
            if t['source'] == 'model':
                l = lab['replyLabels'].get(f"{r['id']}#{i+1}", 'unlabelled'); L['replyLabels'][l] = L['replyLabels'].get(l, 0) + 1
    for L in per.values():
        for k in ('firstTokenMs', 'modelMs', 'engineCreateMs'): L[k] = mmm(L[k])
    allFirst = [t['firstTokenMs'] for r in b2['results'] for t in r['turns']]
    out['B2_followups_host'] = {'platform': 'HOST-linux-cpu', 'perLanguage': per, 'allTurnsFirstTokenMs': mmm(allFirst), 'allTurnsFirstTokenP95': p95(allFirst),
                                'medicalRequests': lab['medicalRequestTurns'], 'spokenLineLabels': lab['spokenLineLabels'], 'writtenSummaryLabels': lab['writtenSummaryLabels']}
    clos = []
    for r in b2['results']:
        T = r['closing']['T']; ln = r['closing']['line'] or {}
        clos.append({'id': r['id'], 'lineReadyMs': round((T.get('lineRetryText') or T['lineText']) - T['trigger']) if ln.get('accepted') else None,
                     'firstLineTextMs': round(T['lineText'] - T['trigger']), 'retry': 'retryCandidate' in ln, 'verifierMs': round(T['verifierDone'] - (T.get('lineRetryText') or T['lineText'])) if T.get('verifierDone') else None,
                     'groupsReadyMs': round(T['groupsText'] - T['trigger']), 'accepted': ln.get('accepted'), 'status': ln.get('finalStatus') or ln.get('status')})
    out['A4_closing_model_stage_host'] = {'platform': 'HOST-linux-cpu (model stages only; audio stages are in-browser, see B5)', 'items': clos,
        'firstLineTextMs': mmm([c['firstLineTextMs'] for c in clos]), 'acceptedLineTextReadyMs': mmm([c['lineReadyMs'] for c in clos]),
        'verifierMs': mmm([c['verifierMs'] for c in clos]), 'groupsReadyMs': mmm([c['groupsReadyMs'] for c in clos]),
        'accepted': sum(1 for c in clos if c['accepted']), 'n': len(clos)}

# ---- B6 long ----
b6 = J(f'{RUNS}/eval_b6_long.json')
if b6:
    out['B6_long_host'] = {'platform': 'HOST-linux-cpu', 'labels': J(f'{LABELS}/b6_labels.json'), 'items': [
        {'id': r['id'], 'contextTokensByTurn': [t['contextTokens'] for t in r['turns']], 'modelMsByTurn': [t['modelMs'] for t in r['turns']],
         'firstTokenMsByTurn': [t['firstTokenMs'] for t in r['turns']], 'fallbackTurns': sum(t['source'] != 'model' for t in r['turns']),
         'replaced': [x['turn'] for x in r['closing']['summary']['replaced']], 'spokenLine': r['closing']['line'].get('accepted')} for r in b6['results']]}

# ---- B3 crisis ----
b3 = J(f'{RUNS}/b3_crisis.json')
if b3:
    out['B3_crisis'] = {'n': len(b3['results']), 'routedToProductCrisisPath': sum(r['crisis'] for r in b3['results']),
                        'modelCalled': sum(r['modelCalled'] for r in b3['results']), 'conversationStopped': sum(r['laterTurnSkipped'] for r in b3['results']),
                        'summaryCreated': sum(1 for r in b3['results'] if r['summary']), 'items': [{k: r[k] for k in ('id', 'moving', 'crisis', 'modelCalled')} for r in b3['results']]}

# ---- A1 candidate lines ----
a1 = J(f'{RUNS}/eval_a1.json')
if a1:
    cs = a1['cases']; wrong = lambda c: c['content'] != 'correct'
    def rates(sel, accept):
        acc = [c for c in sel if accept(c)]
        return {'n': len(sel), 'accepted': len(acc), 'falseAccepts': sum(wrong(c) for c in acc), 'falseAcceptIds': [c['id'] for c in acc if wrong(c)],
                'unnecessaryRejects': sum(not wrong(c) for c in sel if not accept(c)), 'unnecessaryRejectIds': [c['id'] for c in sel if not wrong(c) and not accept(c)],
                'correctRejects': sum(wrong(c) for c in sel if not accept(c))}
    res = {}
    for name, f in (('productValidator', lambda c: c['validatorAccepts']), ('verifierAlone', lambda c: c['verifier'] == 'NO'), ('validatorPlusVerifier', lambda c: c['combinedAccepts'])):
        res[name] = {'all': rates(cs, f), **{l: rates([c for c in cs if c['language'] == l], f) for l in ('tr', 'en', 'de')}}
    four = ['en-role-reversal', 'en-added-thing-modifier', 'de-added-thing-in-compound', 'tr-added-thing-modifier']
    res['fourOpenFalseAccepts'] = [{k: c[k] for k in ('id', 'candidate', 'validatorStatus', 'verifier', 'verifierRaw', 'combinedAccepts')} for c in cs if c['id'] in four]
    res['validatorMatchesFixtureFormal'] = sum((c['validatorStatus'] or 'valid') == c['fixtureFormal'] for c in cs)
    res['verifierUnclear'] = sum(c['verifier'] == 'UNCLEAR' for c in cs)
    out['A1_candidates'] = res

# ---- A2 generated lines ----
a2 = J(f'{RUNS}/eval_a2.json'); l2 = J(f'{LABELS}/a2_labels.json')
if a2:
    items = []
    for r in a2['results']:
        ln = r['line'] or {}
        items.append({'id': r['id'], 'language': r['language'], 'firstCandidate': ln.get('candidate'), 'firstStatus': ln.get('status'), 'retry': ln.get('retryCandidate'),
                      'retryStatus': ln.get('retryStatus'), 'verifier': ln.get('verifier'), 'spoken': ln.get('accepted'), 'label': (l2 or {}).get('labels', {}).get(r['id'], 'unlabelled')})
    by = {}
    for it in items:
        b = by.setdefault(it['language'], {'n': 0, 'spoken': 0, 'labels': {}}); b['n'] += 1; b['spoken'] += bool(it['spoken']); b['labels'][it['label']] = b['labels'].get(it['label'], 0) + 1
    out['A2_generated_lines'] = {'platform': 'HOST-linux-cpu model + product validator', 'perLanguage': by, 'items': items}

# ---- B7 cancel ----
b7 = J(f'{RUNS}/eval_b7.json')
if b7:
    rs = b7['results']
    out['B7_cancel'] = {'n': len(rs), 'cancelledReplySpokenLater': sum(r['aSpokenAfterCancel'] for r in rs), 'cancelledReplyDiscarded': sum(r['aDiscarded'] for r in rs),
                        'nextTurnAnswered': sum(1 for r in rs if r['bSpoken']), 'perLanguage': {l: sum(1 for r in rs if r['lang'] == l) for l in ('tr', 'en', 'de')}}

# ---- B1 STT ----
def norm(s, lang):
    s = unicodedata.normalize('NFC', s)
    s = s.replace('I', 'ı').replace('İ', 'i').lower() if lang == 'tr' else s.lower()
    return re.sub(r'\s+', ' ', re.sub(r"[^\w\s']", ' ', s).replace("'", ' ')).strip()
def ed(a, b):
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        p, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (a[i - 1] != b[j - 1]))
    return d[len(b)]
for model in ('small', 'base'):
    st = J(f'{RUNS}/stt_{model}.json')
    if not st or not st.get('result'): continue
    by = {}
    for it in st['result']['items']:
        r, h = norm(it['reference'], it['lang']), norm(it['hypothesis'], it['lang'])
        b = by.setdefault(it['lang'], {'wordErr': 0, 'words': 0, 'charErr': 0, 'chars': 0, 'ms': [], 'audioS': 0, 'n': 0})
        b['wordErr'] += ed(r.split(), h.split()); b['words'] += len(r.split()); b['charErr'] += ed(r, h); b['chars'] += len(r); b['ms'].append(it['ms']); b['audioS'] += it['audioS']; b['n'] += 1
    out[f'B1_stt_whisper_{model}_browser'] = {'platform': 'WEB-headless-cpu (Chromium 153, WASM)', 'loadMs': st['result'].get('loadMs'), 'blockedExternalRequests': len(st['blockedExternalRequests']),
        **{l: {'n': b['n'], 'WER': round(b['wordErr'] / b['words'], 3), 'CER': round(b['charErr'] / b['chars'], 3), 'msPerUtterance': mmm(b['ms']), 'realTimeFactor': round(sum(b['ms']) / 1000 / b['audioS'], 2)} for l, b in by.items()}}

# ---- TTS / VAD / chain ----
tts = J(f'{RUNS}/tts_samples.json')
if tts and tts.get('result'):
    by = {}
    for it in tts['result']['items']:
        b = by.setdefault(it['lang'], {'firstMs': [], 'warmMs': [], 'audioMs': [], 'voiceLoadMs': it['voiceLoadMs'], 'voice': it['voice']})
        b['firstMs'].append(it['firstMs']); b['warmMs'].append(it['warmMs']); b['audioMs'].append(it['audioMs'])
    out['TTS_piper_browser'] = {'platform': 'WEB-headless-cpu', 'blockedExternalRequests': len(tts['blockedExternalRequests']),
        **{l: {'voice': b['voice'], 'voiceLoadMs': b['voiceLoadMs'], 'firstMs': mmm(b['firstMs']), 'warmMs': mmm(b['warmMs']), 'audioMs': mmm(b['audioMs']),
               'realTimeFactorWarm': round(sum(b['warmMs']) / sum(b['audioMs']), 2)} for l, b in by.items()}}
vad = J(f'{RUNS}/vad_pauses.json')
if vad and vad.get('result'):
    it = vad['result']['items']; by = {}
    for x in it:
        # A cut = any end-of-speech event before the utterance's real end (events arrive with processing latency,
        # so an end decided during the pause can be stamped just after the second part starts).
        ends = [e['rel'] for e in x['events'] if e['type'] == 'end']
        cut = any(r < x['speechEndMs'] for r in ends)
        final = [r - x['speechEndMs'] for r in ends if r >= x['speechEndMs']]
        b = by.setdefault(x['pauseMs'], {'n': 0, 'userCutBeforeEnd': 0, 'cutIds': [], 'endDelayMs': []}); b['n'] += 1; b['userCutBeforeEnd'] += cut
        if cut: b['cutIds'].append(x['id'])
        if final and not cut: b['endDelayMs'].append(final[0])
    out['B4_vad_pauses_browser'] = {'platform': 'WEB-headless-cpu (real-time VAD; synthetic Piper speech as input)', 'redemptionMs': it[0]['redemptionMs'] if it else None,
        'byPauseMs': {k: {kk: (mmm(vv) if kk == 'endDelayMs' else vv) for kk, vv in v.items()} for k, v in sorted(by.items())}}
chains = [J(f'{RUNS}/chain_{l}.json') for l in ('tr', 'en', 'de')]
rows = []
for c in chains:
    if not c or not c.get('result'): continue
    ch = c['result']
    for t in ch.get('turns', []):
        S = {}
        for s in t['stages']: S.setdefault(s['stage'], s)
        e = t['userSpeechEndAt']
        g = lambda k: S[k]['t'] - e if k in S else None
        rows.append({'conv': ch['id'], 'turn': t['index'], 'vadEndAfterSpeechEnd': g('vad-end'), 'sttDone': g('stt-done'), 'sttMs': S.get('stt-done', {}).get('sttMs'),
                     'modelMs': S.get('turn-done', {}).get('modelMs'), 'firstTokenMs': S.get('turn-done', {}).get('firstTokenMs'), 'ttsReady': g('tts-ready'), 'playing': g('playing'),
                     'source': S.get('turn-done', {}).get('source')})
if rows:
    out['B5_turn_latency_chain'] = {'platform': 'WEB-headless-cpu for VAD/STT/TTS/playback + HOST-linux-cpu model via loopback (same VM); playing = HTMLMediaElement playing event (proxy, not acoustic)',
        'n': len(rows), 'rows': rows, **{k: mmm([r[k] for r in rows]) for k in ('vadEndAfterSpeechEnd', 'sttDone', 'sttMs', 'firstTokenMs', 'modelMs', 'ttsReady', 'playing')}}
    cl = []
    for c in chains:
        if not c or not c.get('result') or not c['result'].get('closing'): continue
        st = c['result']['closing']['stages']; S = {}
        for s in st: S.setdefault(s['stage'], []).append(s['t'])
        trig = S.get('closing-trigger', [None])[0]
        plays, ends = S.get('playing', []), S.get('ended', [])
        cl.append({'conv': c['result']['id'], 'bridgeFirstAudioMs': plays[0] - trig if plays and trig else None, 'bridgeEndMs': ends[0] - trig if ends and trig else None,
                   'personalFirstAudioMs': plays[1] - trig if len(plays) > 1 else None, 'gapBridgeEndToPersonalMs': plays[1] - ends[0] if len(plays) > 1 and ends else None,
                   'closingDoneMs': S.get('closing-done', [None])[0] - trig if trig and S.get('closing-done') else None,
                   'line': (c['result']['closing'].get('result') or {}).get('line', {}).get('accepted')})
    out['A4_closing_audio_chain'] = {'platform': out['B5_turn_latency_chain']['platform'], 'items': cl}
json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: (v if k in ('B3_crisis', 'B7_cancel') else '...') for k, v in out.items()}, ensure_ascii=False, indent=1)[:3000])
