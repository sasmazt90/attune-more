"""Host Linux smoke test of the pinned Qwen3.5-2B LiteRT-LM file (NOT an on-device result).

Measures: engine creation (cold/warm), a short real reply, prefill/decode speed via the runtime's
benchmark info, peak RSS. Usage: python -I smoke_host.py MODEL_PATH OUT_JSON
"""
import json, os, resource, sys, time, platform
import litert_lm

model, out = sys.argv[1], sys.argv[2]
rec = {"platform": "host-linux (not on-device)", "machine": platform.machine(), "cpus": os.cpu_count(),
       "runtime": "litert-lm-api 0.19.1 (PyPI wheel manylinux_2_27_x86_64)", "backend": "CPU (XNNPACK)", "runs": []}
for label in ("cold-process-first-engine", "second-engine-same-process"):
    t0 = time.perf_counter()
    eng = litert_lm.Engine(model, backend=litert_lm.Backend.CPU(thread_count=4), max_num_tokens=4096, enable_benchmark=True)
    t1 = time.perf_counter()
    conv = eng.create_conversation(system_message="Answer in one short sentence.",
                                   sampler_config=litert_lm.SamplerConfig(top_k=1, temperature=0.0, seed=1))
    t2 = time.perf_counter()
    msg = conv.send_message("What is the capital of France?")
    t3 = time.perf_counter()
    text = msg["content"][0]["text"] if isinstance(msg, dict) else str(msg)
    try:
        bi = conv.get_benchmark_info(); bench = {k: getattr(bi, k) for k in dir(bi) if not k.startswith('_') and not callable(getattr(bi, k))}
    except Exception as e:  # benchmark info is optional
        bench = {"error": repr(e)}
    rec["runs"].append({"label": label, "engine_create_s": round(t1 - t0, 3), "conversation_create_s": round(t2 - t1, 3),
                        "first_reply_s": round(t3 - t2, 3), "reply": text, "benchmark": json.loads(json.dumps(bench, default=str))})
    conv.close(); eng.close()
rec["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
json.dump(rec, open(out, "w"), ensure_ascii=False, indent=1)
print(json.dumps(rec, ensure_ascii=False, indent=1)[:3000])
