#!/usr/bin/env python3
"""Realistic Vision journey: reads the drawn letter, speaks an answer, checks the scoring.

Each trial reads the letter and orientation from the rendered optotype, chooses a planned
answer (correct, wrong letter, wrong orientation, or the one allowed "I can't see it") and
plays the matching speech clip into the real microphone path, so recognition is real ASR.
It then recomputes per-eye and per-size scores from what was said and compares them with
what the application stored and displayed.

Controlled input, not physical acceptance: an automated reader and synthesized speech stand
in for a person, and reference photos stand in for a camera. Run on the host, as attune.
"""
import argparse
import base64
import datetime as dt
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

ROTATION_WORDS = {0: 'upright', 90: 'rotated right', 180: 'upside down', 270: 'rotated left'}
WRONG_LETTER = {'E': 'F', 'F': 'E', 'P': 'R', 'R': 'P', 'B': 'R', 'A': 'R'}
LETTERS = ['A', 'B', 'E', 'F', 'P', 'R']
# The app tells users they may say a code word. ASR on the Android microphone path heard
# "B" as "D" on every attempt, so a second attempt uses the code word as a person would.
CODE_WORDS = {'A': 'Alpha', 'B': 'Bravo', 'E': 'Echo', 'F': 'Foxtrot', 'P': 'Papa', 'R': 'Romeo'}
MAX_ATTEMPTS = 6
ROTATIONS = [0, 90, 180, 270]
# 24 trials, 12 per eye. Sizes follow the product rule: two correct shrink, two wrong grow.
FULL_PLAN = ['correct', 'correct', 'wrong-letter', 'correct', 'correct', 'not-visible', 'correct', 'correct', 'wrong-orientation', 'correct', 'correct', 'correct',
             'correct', 'correct', 'correct', 'wrong-orientation', 'correct', 'correct', 'wrong-letter', 'wrong-letter', 'correct', 'correct', 'correct', 'correct']
# The second "I can't see it" must stop the assessment without scoring that letter.
STOP_PLAN = ['correct', 'not-visible', 'correct', 'not-visible']
READ_LETTER = """()=>{const svg=document.querySelector('[data-letter-optotype]');if(!svg)return null;
 const path=svg.querySelector('path'),group=svg.querySelector('g'),transform=group?group.getAttribute('transform')||'':'';
 const size=svg.getBoundingClientRect();
 return {d:path?path.getAttribute('d'):null,rotation:Number((transform.match(/rotate\\((\\d+)\\)/)||[])[1]||0),mirrored:/scale\\(-1/.test(transform),widthPx:size.width};}"""
STATE = """()=>{const e=document.querySelector('[data-vision-stage]');if(!e)return null;
 const bar=document.querySelector('[role=progressbar]');
 return {stage:e.dataset.visionStage,trial:e.dataset.visionTrial,voice:(e.querySelector('[data-vision-voice]')||{getAttribute(){return null}}).getAttribute('data-vision-voice'),
  done:bar?Number(bar.getAttribute('aria-valuenow')||0):0,eye:(e.innerText.match(/(Right|Left) eye\\s*[·•]/)||[])[1]||null};}"""


def letter_paths(root):
    source = (root / 'apps/vehicle-app/src/utils/spokenVision.ts').read_text('utf8')
    return {letter: path for letter, path in re.findall(r"\b([ABEFPR]):'(M[^']+)'", source)}


def clip_name(letter, rotation, mirrored, code_word=False):
    return '{}-{}{}{}.wav'.format(letter, rotation, '-mirrored' if mirrored else '', '-code' if code_word else '')


def phrase_for(letter, rotation, mirrored, code_word=False):
    return '{}, {}{}.'.format(CODE_WORDS[letter] if code_word else letter, ROTATION_WORDS[rotation], ', mirrored' if mirrored else '')


def planned_answer(kind, shown, code_word=False):
    """Returns the clip name, the phrase and what that answer means. Never reads a score."""
    if kind == 'not-visible':
        return 'cannot-see.wav', "I can't see it.", {'notVisible': True}
    letter, rotation, mirrored = shown['letter'], shown['rotation'], shown['mirrored']
    if kind == 'wrong-letter':
        letter = WRONG_LETTER[letter]
    elif kind == 'wrong-orientation':
        rotation = (rotation + 90) % 360
    return clip_name(letter, rotation, mirrored, code_word), phrase_for(letter, rotation, mirrored, code_word), {'letter': letter, 'rotation': rotation, 'mirrored': mirrored}


def expected_correctness(kind):
    return {'correct': (True, True), 'wrong-letter': (False, True), 'wrong-orientation': (True, False), 'not-visible': (False, False)}[kind]


def percent(values):
    return round(100 * sum(values) / len(values)) if values else None


def score_summary(rows):
    """Per-eye and per-size scores recomputed from the stored answers, as the result screen should show them."""
    output = {}
    for eye in ('RIGHT', 'LEFT'):
        chosen = [t for t in rows if t['eye'] == eye and t['valid']]
        sizes = {}
        for trial in chosen:
            geometry = trial.get('renderedGeometry') or {}
            key = '{:.1f}'.format(geometry.get('viewportWidthCssPx', 0))
            sizes.setdefault(key, []).append(trial)
        output[eye] = {
            'valid': len(chosen), 'notVisible': sum(bool(t.get('notVisible')) for t in chosen),
            'letterPercent': percent([bool(t['letterCorrect']) for t in chosen]),
            'orientationPercent': percent([bool(t['orientationCorrect']) for t in chosen]),
            'bySize': {key: {'trials': len(group), 'letterPercent': percent([bool(t['letterCorrect']) for t in group]),
                             'orientationPercent': percent([bool(t['orientationCorrect']) for t in group])} for key, group in sizes.items()},
        }
    return output


class Journey:
    def __init__(self, args):
        self.args = args
        self.out = Path(args.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.plan = STOP_PLAN if args.scenario == 'stop' else FULL_PLAN
        self.root = Path(args.root)
        self.paths = letter_paths(self.root)
        self.report = {'scenario': args.scenario, 'platform': args.platform, 'startedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
                       'boundary': 'Controlled input through the real application and real OpenAI ASR. Not physical, human or clinical acceptance.',
                       'plan': self.plan, 'trials': [], 'transcripts': [], 'checks': [], 'errors': []}
        self.audio = None
        self.recorder = None
        self.adapter = None

    def save(self):
        (self.out / 'report.json').write_text(json.dumps(self.report, indent=1, ensure_ascii=False))

    def check(self, what, passed, detail=None):
        self.report['checks'].append({'check': what, 'passed': bool(passed), 'detail': detail})
        print(('PASS ' if passed else 'FAIL ') + what + (' ' + json.dumps(detail, ensure_ascii=False)[:300] if detail is not None else ''), flush=True)
        self.save()

    def play(self, clip):
        path = Path(self.args.clips) / clip
        if not path.exists():
            raise RuntimeError('Missing speech clip ' + clip)
        self.audio = subprocess.Popen(['paplay', '--device=' + self.args.mic_sink, str(path)])

    def start_recording(self):
        if not self.args.record:
            return
        command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'x11grab', '-framerate', '12', '-video_size', self.args.video_size, '-i', self.args.display,
                   '-f', 'pulse', '-i', self.args.speaker_monitor, '-f', 'pulse', '-i', self.args.mic_sink + '.monitor',
                   '-filter_complex', '[1:a][2:a]amix=inputs=2:normalize=0[a]', '-map', '0:v', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24',
                   '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', str(self.out / 'video.mp4')]
        self.recorder = subprocess.Popen(command, stderr=(self.out / 'recorder.log').open('w'))
        time.sleep(1.5)

    def stop_recording(self):
        if self.recorder:
            self.recorder.send_signal(signal.SIGINT)
            self.recorder.wait(timeout=30)

    def read_shown(self, page):
        value = page.evaluate(READ_LETTER)
        if not value or not value.get('d'):
            return None
        letter = next((k for k, d in self.paths.items() if d == value['d']), None)
        return {'letter': letter, 'rotation': value['rotation'], 'mirrored': value['mirrored'], 'widthPx': round(value['widthPx'], 1)} if letter else None

    def assessment(self, page, start_pairing):
        self.adapter.set_pose(page, 'FRONT')
        page.get_by_role('button', name='Start', exact=True).click()
        if start_pairing:
            start_pairing(page)
        deadline = time.time() + self.args.timeout
        pose = 'FRONT'
        last_trial = ''
        last_progress = time.time()
        spoken_trial = ''
        spoken_at = 0
        attempts = 0
        while time.time() < deadline:
            state = page.evaluate(STATE)
            if not state:
                page.wait_for_timeout(500)
                continue
            if state['stage'] == 'result':
                return True
            if state['stage'] == 'error':
                raise RuntimeError('Application error stage: ' + page.locator('[data-vision-stage]').inner_text()[:300])
            target = {'Right': 'RIGHT', 'Left': 'LEFT'}.get(state['eye'], 'FRONT') if state['stage'] not in ('idle', 'preparing') else 'FRONT'
            if target != pose:
                self.adapter.set_pose(page, target)
                pose = target
            if state['trial'] and state['trial'] != last_trial:
                last_trial = state['trial']
                last_progress = time.time()
            ready = state['voice'] == 'listening' and state['trial'] and (state['trial'] != spoken_trial or time.time() - spoken_at > 12)
            if ready and (self.audio is None or self.audio.poll() is not None):
                shown = self.read_shown(page)
                if shown:
                    done = state['done']
                    kind = self.plan[done] if done < len(self.plan) else 'correct'
                    repeated = state['trial'] == spoken_trial
                    attempts = attempts + 1 if repeated else 1
                    if attempts > MAX_ATTEMPTS:
                        raise RuntimeError('{} attempts without an accepted answer on trial {}'.format(MAX_ATTEMPTS, done + 1))
                    clip, phrase, meaning = planned_answer(kind, shown, code_word=attempts > 1)
                    page.wait_for_timeout(500)
                    self.play(clip)
                    spoken_trial = state['trial']
                    spoken_at = time.time()
                    self.report['trials'].append({'presentationId': state['trial'], 'done': done, 'eye': state['eye'], 'kind': kind, 'shown': shown,
                                                  'said': phrase, 'meaning': meaning, 'attempt': attempts, 'at': round(spoken_at, 1)})
                    self.save()
                    print('trial', done + 1, state['eye'], shown['letter'], shown['rotation'], 'mirrored' if shown['mirrored'] else '', '->', kind, repr(phrase), flush=True)
            if time.time() - last_progress > 150:
                raise RuntimeError('No new letter for 150 seconds')
            page.wait_for_timeout(600)
        raise RuntimeError('Assessment deadline reached')

    def expand_sizes(self, page, scope, label):
        tables = {}
        for eye in ('RIGHT', 'LEFT'):
            card = scope.locator('[data-eye-result=' + eye + ']')
            card.scroll_into_view_if_needed()
            page.wait_for_timeout(1200)
            detail = card.locator('details')
            if detail.count():
                detail.locator('summary').click()
                page.wait_for_timeout(1200)
                detail.scroll_into_view_if_needed()
                page.screenshot(path=str(self.out / '{}-{}-sizes.png'.format(label, eye)))
            tables[eye] = card.inner_text()
            for name in ('Next cards',):
                button = scope.get_by_role('button', name=name, exact=True)
                if button.count() and button.is_enabled():
                    button.click()
                    page.wait_for_timeout(800)
        return tables

    def verify_full(self, page, record):
        trials = record['trials']
        valid = [t for t in trials if t['valid']]
        # The last attempt on a presentation is the answer that was accepted.
        said = {}
        for entry in self.report['trials']:
            said[entry['presentationId']] = entry
        self.report['attemptsPerTrial'] = {str(k): v['attempt'] for k, v in said.items()}
        self.check('24 valid trials, 12 per eye', len(valid) == 24 and all(sum(t['eye'] == e for t in valid) == 12 for e in ('RIGHT', 'LEFT')), {'valid': len(valid)})
        self.check("Exactly one 'can't see it' across both eyes", sum(bool(t.get('notVisible')) for t in valid) == 1)
        self.check('Not every answer was can\'t-see', sum(not t.get('notVisible') for t in valid) >= 20)
        mismatches = []
        asr_differences = []
        for trial in valid:
            entry = said.get(trial['presentationId'])
            if not entry:
                mismatches.append({'presentation': trial['presentationId'], 'problem': 'no spoken answer recorded'})
                continue
            # What the harness read on screen must be what the application says it showed.
            transform = trial.get('transform') or {}
            if entry['shown']['letter'] != trial['letter'] or entry['shown']['rotation'] != transform.get('rotation') or entry['shown']['mirrored'] != transform.get('mirrored'):
                mismatches.append({'presentation': trial['presentationId'], 'problem': 'stimulus differs', 'shown': entry['shown'], 'stored': [trial['letter'], transform]})
            letter_ok, orientation_ok = expected_correctness(entry['kind'])
            actual = (bool(trial['letterCorrect']), bool(trial['orientationCorrect']))
            if (letter_ok, orientation_ok) != actual:
                row = {'trial': entry['done'] + 1, 'kind': entry['kind'], 'said': entry['said'], 'parsed': trial.get('answer'), 'expected': [letter_ok, orientation_ok], 'stored': list(actual)}
                asr_differences.append(row)
        self.check('Stored stimulus matches the drawn letter on every trial', not mismatches, mismatches[:5])
        self.report['scoreDifferencesFromPlan'] = asr_differences
        # A wrong plan answer scored as correct, or the reverse, is only acceptable if ASR changed what was heard.
        self.check('Scores match the spoken answers on every trial', not asr_differences, asr_differences[:6])
        correct = [t for t in valid if t['letterCorrect'] and t['orientationCorrect']]
        wrong = [t for t in valid if not t['notVisible'] and not (t['letterCorrect'] and t['orientationCorrect'])]
        self.check('Correct and incorrect answers are told apart', len(correct) >= 12 and len(wrong) >= 3, {'correct': len(correct), 'wrong': len(wrong)})
        sizes = sorted({round((t.get('renderedGeometry') or {}).get('viewportWidthCssPx', 0), 1) for t in valid})
        self.check('Letter size changes with the answers', len(sizes) > 1, sizes)
        summary = score_summary(valid)
        self.report['recomputedScores'] = summary
        return summary

    def verify_display(self, tables, summary, label):
        for eye in ('RIGHT', 'LEFT'):
            text = tables.get(eye, '')
            found = [int(n) for n in re.findall(r'(\d+)\s*%|%\s*(\d+)', text) for n in n if n]
            expect = summary[eye]
            self.check('{} {} shows recomputed letter and orientation scores'.format(label, eye),
                       expect['letterPercent'] in found and expect['orientationPercent'] in found, {'expected': [expect['letterPercent'], expect['orientationPercent']], 'shown': found[:10]})

    def verify_stop(self, page, record):
        trials = record['trials']
        valid = [t for t in trials if t['valid']]
        stopped = [t for t in trials if t.get('invalidReason') == 'NOT_VISIBLE_LIMIT']
        self.check('Second can\'t-see stopped the assessment', record.get('completed') is False and record.get('stopReason') == 'NOT_VISIBLE_LIMIT', {'completed': record.get('completed'), 'stopReason': record.get('stopReason')})
        self.check('Second can\'t-see is stored unscored', len(stopped) == 1 and stopped[0]['valid'] is False and stopped[0]['letterCorrect'] is None and stopped[0]['answer'] is None)
        self.check('Only the first can\'t-see counts as an answer', sum(bool(t.get('notVisible')) for t in valid) == 1 and len(valid) == 3, {'valid': len(valid)})
        banner = page.locator('[data-letter-stopped]')
        self.check('Result screen says the result is incomplete', banner.count() == 1 and banner.is_visible())
        self.check('Unmeasured letters are shown per eye', page.locator('[data-eye-unmeasured]').count() >= 1)

    def referral(self, page, adapter):
        """Specialist options from the live result, through to the provider and back. Returns the page in use."""
        link = page.locator('[data-letter-result]').get_by_role('link', name='Specialist options', exact=True)
        self.check('Specialist options are offered on the result', link.count() == 1, link.count())
        link.scroll_into_view_if_needed()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(self.out / 'referral-offer.png'))
        link.click()
        page.wait_for_url('**/care**')
        filters = page.locator('[data-care-filters]')
        filters.wait_for()
        url = page.url
        self.report['referralUrl'] = url.split('/', 3)[-1]
        self.check('The referral says it came from Vision, for an eye specialist', 'from=vision' in url and 'specialty=' in url, self.report['referralUrl'])
        page.wait_for_timeout(1500)
        page.screenshot(path=str(self.out / 'referral-arrival.png'))
        region = page.locator('[data-care-region]')
        self.report['referralRegionOnArrival'] = region.input_value()
        self.check('No region is chosen for the person', region.input_value() == '', region.input_value())
        self.check('The page asks for a region first', page.locator('[data-care-region-required]').count() == 1)
        region.select_option('Berlin')
        slot = page.locator('[data-care-slot]').first
        slot.wait_for(timeout=20000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(self.out / 'referral-options.png'))
        count = page.locator('[data-care-slot]').count()
        text = page.locator('[data-care-results]').inner_text()
        self.report['referralOptions'] = count
        self.report['referralOptionsText'] = text[:600]
        self.check('Options are listed for the chosen region', count > 0, count)
        self.check('Options are for eye care, not another specialty', re.search(r'ophthalm|eye', text, re.I) is not None, text[:160])
        self.check('No technical labels on the page', not re.search(r'PUBLIC_|LIVE_|providerType|sourceId', text))
        slot.get_by_role('button', name='Review appointment', exact=True).click()
        dialog = page.get_by_role('dialog')
        dialog.wait_for()
        page.wait_for_timeout(1200)
        page.screenshot(path=str(self.out / 'referral-consent.png'))
        dialog.get_by_role('checkbox').check()
        dialog.get_by_role('button', name='Confirm and continue').click()
        page.wait_for_timeout(1200)
        page.screenshot(path=str(self.out / 'referral-handoff.png'))
        before = "JSON.parse(localStorage.getItem('attune.care.appointments.v1')||'[]').length"
        booked = page.evaluate(before)
        provider = page.locator('[data-care-open-provider]')
        self.report['referralProvider'] = provider.get_attribute('href')
        self.check('The provider link is a real web address', (self.report['referralProvider'] or '').startswith('https://'), self.report['referralProvider'])
        page = adapter.open_provider(page, provider, self)
        page.locator('[data-care-return]').wait_for()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(self.out / 'referral-return.png'))
        self.check('Back from the provider, the person is asked whether they booked', 'Did you book' in page.locator('[data-care-return]').inner_text())
        self.check('Opening the provider saved nothing', page.evaluate(before) == booked)
        page.locator('[data-care-return-no]').click()
        page.wait_for_timeout(800)
        self.check('Answering not yet saves nothing', page.evaluate(before) == booked)
        return page

    def history(self, page, record, label):
        page.get_by_role('link', name='My Health History', exact=True).click()
        row = page.locator('[data-record-id="' + record['id'] + '"]')
        row.wait_for()
        # The list re-renders once its records finish loading.
        page.wait_for_timeout(1500)
        row.scroll_into_view_if_needed()
        row.get_by_role('button', name='Open result', exact=True).click()
        dialog = page.get_by_role('dialog')
        dialog.wait_for()
        page.wait_for_timeout(1000)
        page.screenshot(path=str(self.out / (label + '-history.png')))
        scope = dialog.locator('[data-letter-result]')
        self.check('Saved result reopens from history', scope.count() == 1)
        return scope

    def run(self, adapter):
        self.adapter = adapter
        with sync_playwright() as playwright:
            page, close = adapter.open(playwright, self)
            page.set_default_timeout(25000)
            page.on('pageerror', lambda e: self.report['errors'].append(str(e)[:300]))

            def response(res):
                if res.url.split('?')[0].endswith('/api/speech/transcribe'):
                    try:
                        body = res.json()
                    except Exception:
                        body = {}
                    self.report['transcripts'].append({'status': res.status, 'text': body.get('text'), 'at': round(time.time(), 1)})
                    self.save()
            page.on('response', response)
            try:
                adapter.prepare(page, self)
                self.start_recording()
                adapter.enter(page, self)
                completed = self.assessment(page, adapter.pair)
                self.check('Assessment reached the result screen', completed)
                dialog = page.get_by_role('dialog')
                if dialog.count():
                    self.report['completionNotice'] = dialog.inner_text()
                    page.wait_for_timeout(1500)
                    dialog.get_by_role('button', name=re.compile('^(OK|Done)$', re.I)).click()
                page.locator('[data-letter-result]').wait_for()
                page.screenshot(path=str(self.out / 'result.png'))
                history = page.evaluate("JSON.parse(localStorage.getItem('togg_health_vision_history')||'[]')")
                generated = [r for r in history if r['id'] not in self.report.get('beforeIds', [])]
                self.check('One new saved record', len(generated) == 1, {'new': len(generated)})
                record = generated[0]
                self.report['record'] = {k: record.get(k) for k in ('id', 'date', 'protocolVersion', 'methodVersion', 'completed', 'stopReason')}
                self.report['storedTrials'] = [{k: t.get(k) for k in ('presentationId', 'eye', 'letter', 'transform', 'sizePx', 'answer', 'parsedAnswer', 'letterCorrect', 'orientationCorrect', 'combinedCorrect', 'notVisible', 'valid', 'invalidReason', 'renderedGeometry')} for t in record['trials']]
                if self.args.scenario == 'stop':
                    self.verify_stop(page, record)
                    self.history(page, record, 'stop')
                else:
                    summary = self.verify_full(page, record)
                    tables = self.expand_sizes(page, page.locator('[data-letter-result]'), 'live')
                    self.report['resultText'] = tables
                    self.verify_display(tables, summary, 'Result')
                    page = self.referral(page, adapter)
                    scope = self.history(page, record, 'saved')
                    saved = self.expand_sizes(page, scope, 'saved')
                    self.report['savedText'] = saved
                    self.verify_display(saved, summary, 'History')
                failed = [c for c in self.report['checks'] if not c['passed']]
                self.report['status'] = 'PASS' if not failed else 'FAIL'
            except Exception as error:
                self.report['status'] = 'ERROR'
                self.report['failure'] = str(error)[:800]
                print('ERROR', error, flush=True)
                try:
                    page.screenshot(path=str(self.out / 'failure.png'))
                except Exception:
                    pass
            finally:
                if self.audio and self.audio.poll() is None:
                    self.audio.terminate()
                self.stop_recording()
                self.report['finishedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
                self.save()
                adapter.finish(self)
                close()
        print(json.dumps({'status': self.report.get('status'), 'failed': [c['check'] for c in self.report['checks'] if not c['passed']], 'failure': self.report.get('failure')}, ensure_ascii=False))


class Aaos:
    """Native WebView on the emulator, reached through DevTools. Camera comes from the mTLS reference bridge."""
    ADB = '/opt/android-sdk/platform-tools/adb'

    def open(self, playwright, journey):
        device = [self.ADB, '-s', 'emulator-5554']
        unix = subprocess.check_output(device + ['shell', 'cat', '/proc/net/unix'], text=True, stdin=subprocess.DEVNULL)
        socket = re.findall(r'webview_devtools_remote_\d+', unix)[0]
        subprocess.check_call(device + ['forward', 'tcp:9222', 'localabstract:' + socket], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        self.playwright = playwright
        browser = self.browser = playwright.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = next(p for c in browser.contexts for p in c.pages if p.url.startswith('http://127.0.0.1:3000'))
        # The camera pairing code is a short-lived credential. It stays out of recordings.
        mask = """(()=>{const hide=()=>document.querySelectorAll('dialog textarea').forEach(e=>e.style.webkitTextSecurity='disc');new MutationObserver(hide).observe(document,{childList:true,subtree:true});})();"""
        page.add_init_script(mask)
        page.evaluate(mask)
        return page, lambda: self.browser.close()

    def open_provider(self, page, link, journey):
        # The native shell blocks this navigation and asks before leaving the app, so nothing will finish loading.
        link.click(no_wait_after=True)
        page.wait_for_timeout(1800)
        # The dialog is native, so only the device can capture it.
        shot = subprocess.check_output([self.ADB, '-s', 'emulator-5554', 'exec-out', 'screencap', '-p', '-d', '4619827259835644672'], stdin=subprocess.DEVNULL)
        (journey.out / 'referral-native-leave-dialog.png').write_bytes(shot)
        # Stay in the app.
        subprocess.run([self.ADB, '-s', 'emulator-5554', 'shell', 'input', 'keyevent', '4'], stdin=subprocess.DEVNULL, check=False)
        page.wait_for_timeout(600)
        # A navigation the WebView cancels stays pending in Playwright for good. A new connection starts clean.
        self.browser.close()
        self.browser = self.playwright.chromium.connect_over_cdp('http://127.0.0.1:9222')
        return next(p for c in self.browser.contexts for p in c.pages if p.url.startswith('http://127.0.0.1:3000'))

    def prepare(self, page, journey):
        page.goto('http://127.0.0.1:3000/', wait_until='networkidle')
        page.locator('#attune-language').select_option('en')
        journey.report['viewport'] = page.evaluate('[innerWidth,innerHeight]')
        journey.report['beforeIds'] = page.evaluate("JSON.parse(localStorage.getItem('togg_health_vision_history')||'[]').map(x=>x.id)")
        page.get_by_role('link', name='Privacy & Permissions', exact=True).click()
        box = page.get_by_role('checkbox', name='Store orientation-alignment results on this device', exact=True)
        if not box.is_checked():
            box.check()
        page.locator('nav a[href="/"]').first.click()

    def enter(self, page, journey):
        page.get_by_role('button', name='Health Center', exact=True).click()
        page.locator('#health-centre-links a[href="/vision"]').click()
        dialog = page.get_by_role('dialog')
        page.wait_for_timeout(800)
        if dialog.count():
            for box in dialog.get_by_role('checkbox').all():
                box.check()
            page.wait_for_timeout(500)
            dialog.get_by_role('button', name='Allow and continue', exact=True).click()
        page.locator('[data-health-start]').wait_for()
        page.wait_for_timeout(1500)

    def pair(self, page):
        code = page.locator('dialog textarea')
        code.wait_for()
        page.wait_for_timeout(400)
        args = self.journey_args
        key_file = Path(args.pair_file)
        key_file.write_text(json.dumps({'key': code.input_value()}))
        key_file.chmod(0o600)

    def set_pose(self, page, pose):
        path = self.journey_args.pose_file
        Path(path + '.next').write_text(pose)
        os.replace(path + '.next', path)

    def finish(self, journey):
        pass


class Web:
    """Real Chrome and real browser audio capture. Only the camera is replaced, by reference photos."""
    HOST = 'attunemore.sasmaz.digital'
    # Audio requests still reach the real device. Video requests get the current reference photo.
    CAMERA = """(()=>{const FRAMES=__FRAMES__,images={};for(const k of Object.keys(FRAMES)){const i=new Image();i.src=FRAMES[k];images[k]=i;}
 const canvas=document.createElement('canvas');canvas.width=640;canvas.height=480;const ctx=canvas.getContext('2d');
 let tick=0;setInterval(()=>{const i=images[window.__attunePose||'FRONT'];if(i&&i.complete){ctx.globalAlpha=1;ctx.drawImage(i,0,0,640,480);tick++;ctx.fillStyle='rgba(0,0,0,'+(tick%2?0.004:0.006)+')';ctx.fillRect(0,0,1,1);}},100);
 const stream=canvas.captureStream(10),real=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
 navigator.mediaDevices.getUserMedia=c=>c&&c.video?Promise.resolve(stream.clone()):real(c);
})();"""

    def open(self, playwright, journey):
        args = self.journey_args
        credentials = json.loads(Path(args.access_file).read_text())
        frames = {}
        for pose, name in (('FRONT', args.web_front), ('RIGHT', args.web_right), ('LEFT', args.web_left)):
            frames[pose] = 'data:image/jpeg;base64,' + base64.b64encode(Path(name).read_bytes()).decode()
        # Chrome does not offer monitor sources as microphones, so the run script adds a remapped source.
        environment = {**os.environ, 'PULSE_SOURCE': args.mic_source, 'PULSE_SINK': args.speaker_monitor.replace('.monitor', '')}
        environment['DISPLAY'] = args.display.split('+')[0]
        environment['TZ'] = args.timezone
        # The same kept profile and app window as the other journeys, so saved records carry between them.
        context = playwright.chromium.launch_persistent_context(
            args.profile, executable_path='/usr/bin/google-chrome', headless=False, env=environment, ignore_default_args=['--mute-audio', '--enable-automation'],
            args=['--no-sandbox', '--disable-dev-shm-usage', '--use-fake-ui-for-media-stream', '--autoplay-policy=no-user-gesture-required',
                  '--host-resolver-rules=MAP {} 127.0.0.1'.format(self.HOST), '--window-size=1280,800', '--window-position=0,0', '--app=https://' + self.HOST,
                  '--disable-features=Translate,TranslateUI', '--disable-infobars', '--lang=en-US', '--no-first-run'],
            http_credentials={'username': credentials['username'], 'password': credentials['password']},
            viewport={'width': args.web_width, 'height': args.web_height}, permissions=['camera', 'microphone'], timezone_id=args.timezone, locale='en-US')
        context.add_init_script(self.CAMERA.replace('__FRAMES__', json.dumps(frames)))
        return (context.pages[0] if context.pages else context.new_page()), context.close

    def prepare(self, page, journey):
        page.goto('https://' + self.HOST, wait_until='networkidle')
        page.locator('#attune-language').select_option('en')
        journey.report['viewport'] = page.evaluate('[innerWidth,innerHeight]')
        journey.report['beforeIds'] = page.evaluate("JSON.parse(localStorage.getItem('togg_health_vision_history')||'[]').map(x=>x.id)")
        page.get_by_role('link', name='Privacy & Permissions', exact=True).click()
        box = page.get_by_role('checkbox', name='Store orientation-alignment results on this device', exact=True)
        if not box.is_checked():
            box.check()
        page.locator('nav a[href="/"]').first.click()

    def enter(self, page, journey):
        Aaos.enter(self, page, journey)

    pair = None

    def open_provider(self, page, link, journey):
        with page.context.expect_page() as popup:
            link.click()
        popup.value.close()
        return page

    def set_pose(self, page, pose):
        page.evaluate('p=>{window.__attunePose=p}', pose)

    def finish(self, journey):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=['aaos', 'web'], default='aaos')
    parser.add_argument('--mic-source', default='attune_mic_source')
    parser.add_argument('--access-file', default='/var/lib/attune/qa/access.json')
    parser.add_argument('--web-front', default='/var/lib/attune/qa/web-vision-FRONT.jpg')
    parser.add_argument('--web-right', default='/var/lib/attune/qa/web-vision-RIGHT.jpg')
    parser.add_argument('--web-left', default='/var/lib/attune/qa/web-vision-LEFT.jpg')
    parser.add_argument('--web-width', type=int, default=1280)
    parser.add_argument('--web-height', type=int, default=800)
    parser.add_argument('--scenario', choices=['full', 'stop'], default='full')
    parser.add_argument('--root', default='/opt/attune')
    parser.add_argument('--clips', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--mic-sink', default='attune_mic')
    parser.add_argument('--speaker-monitor', default='attune_out.monitor')
    parser.add_argument('--display', default=':99')
    parser.add_argument('--video-size', default='1280x800')
    parser.add_argument('--pose-file', default='/var/lib/attune/qa/camera-pose.txt')
    parser.add_argument('--pair-file', default='/var/lib/attune/qa/camera-pair.json')
    parser.add_argument('--timeout', type=int, default=1200)
    parser.add_argument('--profile', default='/var/lib/attune/qa/profile-web')
    parser.add_argument('--timezone', default='Europe/Berlin')
    parser.add_argument('--record', action='store_true')
    args = parser.parse_args()
    adapter = Web() if args.platform == 'web' else Aaos()
    adapter.journey_args = args
    Journey(args).run(adapter)


if __name__ == '__main__':
    sys.exit(main())
