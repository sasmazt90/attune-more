"""HOST probe: what happens to a Conversation after cancel_process() (LiteRT-LM Python 0.19.1). Not on-device."""
import json, sys, threading, time
import litert_lm
model, out = sys.argv[1], sys.argv[2]
def run(cancel_after):
    eng = litert_lm.Engine(model, backend=litert_lm.Backend.CPU(thread_count=4), max_num_tokens=4096)
    conv = eng.create_conversation(system_message="Answer briefly.", sampler_config=litert_lm.SamplerConfig(top_k=1, temperature=0.0, seed=1))
    res = {'cancelAfterS': cancel_after, 'replies': []}
    for i, msg in enumerate(["Tell me a long story about a lighthouse.", "What is the capital of France?", "What is 2 plus 2?"]):
        if i == 0 and cancel_after is not None:
            threading.Timer(cancel_after, conv.cancel_process).start()
        t0 = time.perf_counter(); text = ''; err = None
        try:
            for ch in conv.send_message_async(msg, max_output_tokens=60):
                text += ''.join(c.get('text', '') for c in ch.get('content', []))
        except Exception as e:
            err = repr(e)
        res['replies'].append({'msg': msg, 'text': text, 'error': err, 's': round(time.perf_counter() - t0, 2)})
    conv.close(); eng.close()
    return res
r = {'platform': 'HOST-linux-cpu', 'runtime': 'litert-lm-api 0.19.1', 'noCancel': run(None), 'cancelDuringFirst': run(0.8)}
json.dump(r, open(out, 'w'), ensure_ascii=False, indent=1); print(json.dumps(r, ensure_ascii=False, indent=1))
