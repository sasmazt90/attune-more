"""HOST-linux-cpu LLM adapter for evaluation only (NOT on-device).

Loopback HTTP server wrapping LiteRT-LM Python 0.19.1 with the pinned Qwen3.5-2B file, so the prototype's JS core
(the same code the browser page runs) can be evaluated at host speed. One fresh Engine per session: the model card
and results/raw/leak_host.json show that a second Conversation on a used Engine keeps the previous state.
Also exposes the product's unchanged validate_spoken_summary (services/core-api/mental_analysis.py, imported
read-only from the repository checkout).

Usage: python -I llm_host_server.py MODEL_PATH REPO_ROOT [PORT]
"""
import json, os, sys, threading, time, uuid, resource
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL, REPO = sys.argv[1], sys.argv[2]
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 8790
sys.path.insert(0, os.path.join(REPO, 'services/core-api'))
import litert_lm  # noqa: E402
from mental_analysis import validate_spoken_summary  # noqa: E402

litert_lm.set_min_log_severity(litert_lm.LogSeverity.ERROR) if hasattr(litert_lm, 'LogSeverity') else None
LOCK = threading.Lock()          # one generation at a time (single engine, like a device)
SESSIONS = {}                    # id -> {engine, conv}


def text_of(message):
    if isinstance(message, dict):
        return ''.join(c.get('text', '') for c in message.get('content', []) if isinstance(c, dict))
    return str(message)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if self.path == '/info':
            return self.reply(200, {'platform': 'HOST-linux-cpu (not on-device)', 'runtime': 'litert-lm-api 0.19.1', 'model': MODEL,
                                    'peak_rss_mb': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
                                    'sessions': len(SESSIONS)})
        self.reply(404, {})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
        try:
            getattr(self, 'op_' + self.path.strip('/'))(req)
        except Exception as e:  # report, never hide
            self.reply(500, {'error': repr(e)})

    def op_session(self, req):
        with LOCK:
            for sid in list(SESSIONS):  # a device holds one engine; close the previous one first
                s = SESSIONS.pop(sid); s['conv'].close(); s['engine'].close()
            t0 = time.perf_counter()
            engine = litert_lm.Engine(MODEL, backend=litert_lm.Backend.CPU(thread_count=4), max_num_tokens=4096, enable_benchmark=True)
            t1 = time.perf_counter()
            conv = engine.create_conversation(system_message=req['systemPrompt'],
                                              sampler_config=litert_lm.SamplerConfig(top_k=1, temperature=0.0, seed=1))
            sid = uuid.uuid4().hex
            SESSIONS[sid] = {'engine': engine, 'conv': conv}
        self.reply(200, {'sessionId': sid, 'engineCreateMs': round((t1 - t0) * 1000)})

    def op_send(self, req):
        s = SESSIONS.get(req['sessionId'])
        if not s:
            return self.reply(410, {'error': 'session closed'})
        with LOCK:
            t0 = time.perf_counter(); first = None; out = []; cancelled = False
            try:
                for chunk in s['conv'].send_message_async(req['text'], max_output_tokens=req.get('maxTokens', 96)):
                    piece = text_of(chunk)
                    if piece and first is None:
                        first = time.perf_counter()
                    out.append(piece)
            except Exception as e:
                cancelled = 'cancel' in repr(e).lower()
                if not cancelled:
                    raise
            t1 = time.perf_counter()
            try:
                bi = s['conv'].get_benchmark_info()
                bench = {'prefillTokens': bi.last_prefill_token_count, 'prefillTps': round(bi.last_prefill_tokens_per_second, 1),
                         'decodeTokens': bi.last_decode_token_count, 'decodeTps': round(bi.last_decode_tokens_per_second, 1)}
            except Exception:
                bench = None
            tokens = s['conv'].token_count
        self.reply(200, {'text': ''.join(out), 'firstTokenMs': round((first - t0) * 1000) if first else None,
                         'totalMs': round((t1 - t0) * 1000), 'cancelled': cancelled, 'bench': bench, 'contextTokens': tokens})

    def op_cancel(self, req):
        s = SESSIONS.get(req['sessionId'])
        if s:
            s['conv'].cancel_process()
        self.reply(200, {'ok': bool(s)})

    def op_close(self, req):
        with LOCK:
            s = SESSIONS.pop(req['sessionId'], None)
            if s:
                s['conv'].close(); s['engine'].close()
        self.reply(200, {'ok': bool(s)})

    def op_validate(self, req):
        line, status = validate_spoken_summary(req['line'], req['language'], req['messages'])
        self.reply(200, {'line': line, 'status': status})


if __name__ == '__main__':
    print(f'HOST LLM adapter on 127.0.0.1:{PORT} (not on-device)', flush=True)
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
