#!/usr/bin/env python3
"""Experiment C, arm m9 (docs/qa_week/C_PREREG.md): one rule-writing call to the pinned open model, runner side.

Starts llama-server (built at the pinned commit, config.json) on the pinned GGUF, sends the prompt file's bytes as the
single user message with the registered decoding (greedy, thinking off, max 2048 tokens), saves the reply unedited,
reads it with tune_a35.parse_policy (the parser every A35 policy went through) and, only if that fails, makes the one
registered re-ask (same prompt, output constrained to the reply's JSON form). Writes receipt.json with the timings.
Usage: run_m9.py --config C --server BIN --model GGUF --prompt FILE --item ID --out DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import clib as C  # noqa: E402


def http(url, body=None, timeout=60):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode() or "{}")


def cpu():
    out = {"machine": platform.machine(), "nproc": os.cpu_count()}
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                out["model"] = line.split(":", 1)[1].strip()
                break
        flags = next(l for l in open("/proc/cpuinfo") if l.startswith("flags")).split()
        out["avx512f"] = "avx512f" in flags
        out["mem_gb"] = round(int(next(l for l in open("/proc/meminfo") if l.startswith("MemTotal")).split()[1]) / 1048576, 1)
    except Exception:  # noqa: BLE001
        pass
    return out


def ask(base, body, timeout):
    t = time.time()
    _, resp = http(f"{base}/v1/chat/completions", body, timeout)
    wall = time.time() - t
    msg = resp["choices"][0]["message"]
    return resp, msg.get("content") or "", msg.get("reasoning_content"), wall


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--server", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--item", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--port", type=int, default=8080)
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    os.makedirs(a.out, exist_ok=True)
    raw = open(a.prompt, "rb").read()
    prompt = raw.decode("utf-8")
    rec = {"item": a.item, "prompt": a.prompt, "prompt_sha256": hashlib.sha256(raw).hexdigest(), "prompt_chars": len(prompt),
           "model": cfg["model"], "llama_cpp": {k: cfg["llama_cpp"][k] for k in ("tag", "commit")}, "cpu": cpu(),
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    sv = cfg["server"]
    args = [a.server, "-m", a.model, "--host", "127.0.0.1", "--port", str(a.port), "-t", str(sv["threads"]),
            "-tb", str(sv["threads_batch"]), "-c", str(sv["ctx_size"]), "-np", str(sv["parallel"])] + sv["args"]
    rec["server_args"] = args[1:]
    base = f"http://127.0.0.1:{a.port}"
    log = open(os.path.join(a.out, "server.log"), "w")
    t0 = time.time()
    proc = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
    try:
        while True:
            if proc.poll() is not None:
                raise SystemExit(f"llama-server exited with {proc.returncode} before it was ready (see server.log)")
            try:
                st, js = http(f"{base}/health", timeout=5)
                if st == 200 and js.get("status", "ok") == "ok":
                    break
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
                pass
            if time.time() - t0 > cfg["timeouts_s"]["server_load"]:
                raise SystemExit("llama-server not ready in time")
            time.sleep(2)
        rec["server_load_s"] = round(time.time() - t0, 1)
        req = {k: v for k, v in cfg["request"].items() if k != "messages"}
        body = dict(req, messages=[{"role": "user", "content": prompt}], stream=False)
        resp, content, reasoning, wall = ask(base, body, cfg["timeouts_s"]["request"])
        open(os.path.join(a.out, "reply.txt"), "w").write(content)
        json.dump(resp, open(os.path.join(a.out, "response.json"), "w"), indent=1)
        tm = resp.get("timings") or {}
        rec["call"] = {"wall_s": round(wall, 1), "prompt_tokens": tm.get("prompt_n"), "prompt_tokens_per_s": tm.get("prompt_per_second"),
                       "reply_tokens": tm.get("predicted_n"), "reply_tokens_per_s": tm.get("predicted_per_second"),
                       "cached_tokens": tm.get("cache_n"), "finish_reason": resp["choices"][0].get("finish_reason"),
                       "reasoning_chars": len(reasoning or "")}
        v = C.validate(content)
        rec["valid"] = v
        if not v["ok"]:
            body2 = dict(body, response_format=cfg["reask"]["response_format"])
            resp2, content2, _, wall2 = ask(base, body2, cfg["timeouts_s"]["request"])
            open(os.path.join(a.out, "reask_reply.txt"), "w").write(content2)
            json.dump(resp2, open(os.path.join(a.out, "reask_response.json"), "w"), indent=1)
            tm2 = resp2.get("timings") or {}
            rec["reask"] = {"wall_s": round(wall2, 1), "reply_tokens": tm2.get("predicted_n"),
                            "reply_tokens_per_s": tm2.get("predicted_per_second"), "valid": C.validate(content2)}
        final = rec.get("reask", {}).get("valid") if not v["ok"] else v
        rec["rule_file"] = ({"rationale": final["rationale"], "pins": final["pins"]} if final and final.get("ok")
                            else {"rationale": "no readable policy after the registered re-ask: empty policy", "pins": {}})
        rec["rule_file_source"] = "reply" if v["ok"] else ("reask" if final and final.get("ok") else "empty")
        json.dump(rec["rule_file"], open(os.path.join(a.out, "rule.json"), "w"), indent=1)
    finally:
        proc.terminate()
        try:
            proc.wait(30)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
        rec["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        json.dump(rec, open(os.path.join(a.out, "receipt.json"), "w"), indent=1)
    c = rec.get("call", {})
    print(f"[m9] {a.item}: load {rec.get('server_load_s')} s; prompt {c.get('prompt_tokens')} tok at {c.get('prompt_tokens_per_s')} tok/s; "
          f"reply {c.get('reply_tokens')} tok at {c.get('reply_tokens_per_s')} tok/s; call {c.get('wall_s')} s; "
          f"parsed: {rec['valid']['ok']}; rule file from {rec.get('rule_file_source')}: {json.dumps(rec.get('rule_file', {}).get('pins'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
