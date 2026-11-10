"""State-leak test between conversations (host Linux, NOT on-device). Model card: LiteRT-LM #3165.

Conversation A tells a unique fact and uses system prompt SA; conversation B (system prompt SB) then asks for it.
Modes: same-engine (B on the Engine that ran A) vs fresh-engine (B on a new Engine). Greedy decoding.
"""
import json, sys, time
import litert_lm

model, out = sys.argv[1], sys.argv[2]
SAMPLER = litert_lm.SamplerConfig(top_k=1, temperature=0.0, seed=1)
SA = "You are a helpful assistant. Start every reply with the word ALPHA."
SB = "You are a helpful assistant. Start every reply with the word BRAVO."
A_MSGS = ["My secret code word is PELICAN-7342 and my sister is called Ilse. Please confirm briefly.",
          "Also remember that I moved to Hamburg last week."]
B_PROBES = ["What is my secret code word? If you do not know, say UNKNOWN.",
            "What is my sister's name and where did I move? If you do not know, say UNKNOWN."]

def engine():
    return litert_lm.Engine(model, backend=litert_lm.Backend.CPU(thread_count=4), max_num_tokens=4096)

def text(m):
    return m["content"][0]["text"] if isinstance(m, dict) else str(m)

res = {"platform": "host-linux (not on-device)", "runtime": "litert-lm-api 0.19.1", "trials": []}
for mode in ("same-engine", "fresh-engine", "same-engine", "fresh-engine"):
    e1 = engine()
    a = e1.create_conversation(system_message=SA, sampler_config=SAMPLER)
    a_out = [text(a.send_message(m)) for m in A_MSGS]
    a.close()
    t0 = time.perf_counter()
    e2 = e1 if mode == "same-engine" else engine()
    t_engine = time.perf_counter() - t0
    if mode == "fresh-engine":
        e1.close()
    b = e2.create_conversation(system_message=SB, sampler_config=SAMPLER)
    b_out = [text(b.send_message(p)) for p in B_PROBES]
    leaked = any(k in o.upper() for o in b_out for k in ("PELICAN", "7342", "ILSE", "HAMBURG"))
    starts_bravo = sum(o.strip().upper().startswith("BRAVO") for o in b_out)
    starts_alpha = sum(o.strip().upper().startswith("ALPHA") for o in b_out)
    res["trials"].append({"mode": mode, "new_engine_s": round(t_engine, 2), "a_replies": a_out, "b_replies": b_out,
                          "content_leaked": leaked, "b_opened_with_own_system_prompt": starts_bravo,
                          "b_opened_with_previous_system_prompt": starts_alpha})
    b.close(); e2.close()
    print(json.dumps(res["trials"][-1], ensure_ascii=False))
json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
