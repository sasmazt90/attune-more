"""Test-only admission at the HTTP egress boundary; never replaces provider output."""
from threading import RLock

TEXTS = ('Bugün yeni bir kitap okudum.', 'Bugün yeni bir film izledim.', 'Bugün yeni bir şarkı dinledim.')

class AdmissionRejected(RuntimeError):
    pass

class LiveAdmission:
    def __init__(self, source_verified=False, spoken_reply=None):
        self.source_verified = source_verified
        self.spoken_reply = spoken_reply or (lambda value: value)
        self.counts = {'conversation': 0, 'tts': 0, 'summary': 0}
        self.messages = []
        self.pending = None
        self.blocked = []
        self.failed = False
        self.lock = RLock()

    def reject(self, reason):
        self.failed = True
        self.blocked.append(reason)  # Never include rejected content or headers.
        raise AdmissionRejected(reason)

    def admit(self, endpoint, data):
        with self.lock:
            if self.failed or not self.source_verified:
                self.reject('SOURCE_NOT_VERIFIED_OR_CLOSED')
            if self.pending:
                self.reject('CONCURRENT_OR_RETRY_REQUEST')
            if endpoint == '/v1/audio/speech':
                kind = 'tts'
                if self.counts[kind] >= 3 or self.counts['conversation'] != self.counts[kind] + 1:
                    self.reject('TTS_BUDGET_OR_ORDER')
                if not self.messages or data.get('input') != self.spoken_reply(self.messages[-1]['content']):
                    self.reject('TTS_NOT_CURRENT_VERIFIED_REPLY')
                if not isinstance(data.get('input'), str) or len(data['input']) > 2000:
                    self.reject('TTS_INPUT_BUDGET')
                if data.get('voice') != 'coral' or data.get('response_format') != 'mp3':
                    self.reject('TTS_CONFIGURATION_CHANGED')
            elif endpoint == '/v1/chat/completions':
                if data.get('response_format') == {'type': 'json_object'}:
                    kind = 'summary'
                    if self.counts[kind] or self.counts['conversation'] != 3 or self.counts['tts'] != 3:
                        self.reject('SUMMARY_BUDGET_OR_ORDER')
                    expected = '\n'.join(f"{m['role']}: {m['content']}" for m in self.messages)
                    messages = data.get('messages', [])
                    if len(messages) != 1 or messages[0].get('role') != 'user':
                        self.reject('SUMMARY_SHAPE')
                    prefix, separator, history = messages[0].get('content', '').partition('Konuşma Geçmişi:\n')
                    if not separator or not prefix.startswith('Aşağıdaki kullanıcı-asistan araç içi konuşmasını analiz et') or history != expected:
                        self.reject('SUMMARY_HISTORY_NOT_CONTROLLED')
                else:
                    kind = 'conversation'
                    i = self.counts[kind]
                    if i >= 3 or self.counts['tts'] != i:
                        self.reject('CONVERSATION_BUDGET_OR_ORDER')
                    messages = data.get('messages', [])
                    expected = self.messages + [{'role': 'user', 'content': TEXTS[i]}]
                    if not messages or messages[0].get('role') != 'system' or messages[1:] != expected:
                        self.reject('USER_OR_HISTORY_NOT_CONTROLLED')
                    if not messages[0].get('content', '').startswith('Sen Togg araç içi Ruhsal İyi Oluş Asistanısın.'):
                        self.reject('SYSTEM_PROMPT_CHANGED')
            else:
                self.reject('UNEXPECTED_PROVIDER_ENDPOINT')
            if data.get('stream') or data.get('store') is True:
                self.reject('UNAPPROVED_STREAM_OR_STORAGE')
            self.counts[kind] += 1  # Consume before dispatch: failures never permit retry.
            self.pending = kind
            return kind

    def complete(self, kind, reply=None, success=True):
        with self.lock:
            if self.pending != kind:
                self.reject('UNMATCHED_RESPONSE')
            self.pending = None
            if not success:
                self.reject('PROVIDER_FAILED_NO_RETRY')
            if kind == 'conversation':
                if not isinstance(reply, str) or not reply.strip():
                    self.reject('EMPTY_PROVIDER_REPLY')
                self.messages += [{'role': 'user', 'content': TEXTS[len(self.messages)//2]}, {'role': 'assistant', 'content': reply.strip()}]

    def proof(self):
        return {'sourceVerified': self.source_verified, 'counts': self.counts.copy(), 'blockedReasons': self.blocked.copy(), 'closed': self.failed, 'completedPairs': len(self.messages)//2}

def forward_admitted_response(route, gate, kind, record, expected_provider='LIVE_OPENAI'):
    """Verify the actual backend response BEFORE releasing it to the browser.

    An on-response callback can reenter while response.json() pumps Playwright,
    allowing the browser's next request to arrive before the prior gate completes.
    fetch/verify/fulfill removes that race without fabricating provider output.
    """
    response = route.fetch(max_redirects=0, max_retries=0, timeout=35000)
    data = response.json() if kind in ['conversation', 'summary'] else None
    success = response.ok and (data is None or data.get('providerType') == expected_provider)
    try:
        gate.complete(kind, data.get('reply') if data else None, success)
    except AdmissionRejected:
        # An admitted request's honest fallback/error remains visible, while
        # the closed gate blocks every subsequent provider-bound request.
        success = False
    record(kind, data, response)
    route.fulfill(response=response)
    return success


def live_run_output(root, run_id=None):
    """Distinct authorization ledger; reject traversal and preserve previous run."""
    from pathlib import Path
    import re
    if run_id is not None and not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,63}', run_id):
        raise ValueError('Invalid live run identity')
    return Path(root)/'audit-results'/'live-provider'/(run_id or 'controlled-text')


def claim_live_run(output, run_id=None):
    """Exclusive one-shot marker before real HTTP dispatch; never reset/retry."""
    import json
    output.mkdir(parents=True,exist_ok=True)
    with (output/'run-consumed.json').open('x',encoding='utf-8') as marker:
        json.dump({'runId':run_id or 'controlled-text','authorization':'one user-approved synthetic written three-turn run','automaticRetryAllowed':False,'maxProviderRequests':{'conversation':3,'tts':3,'summary':1},'approvedSyntheticTexts':list(TEXTS),'maxBudgetUSD':1.0,'maxTTSInputCharactersPerRequest':2000,'providerAccountSpendingLimitCreated':False},marker)
