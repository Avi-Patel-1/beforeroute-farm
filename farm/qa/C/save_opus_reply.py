#!/usr/bin/env python3
"""Experiment C: save one Opus sub-agent's final reply unedited and log how it was produced (as A35's
agents/a35/extract_reply.py and audit.jsonl did).

Usage: save_opus_reply.py TRANSCRIPT.jsonl RACE CALL [--reask]
  TRANSCRIPT  the sub-agent's JSONL transcript (e.g. /tmp/claude-0/<session>/tasks/<agentId>.output)
  RACE CALL   as in farm/qa/C/prompts/MANIFEST.json (e.g. rule-xtea-s1 round1, prop-PPU round3)
Writes /home/claude/ideas/overnight/method/opus_replies/RACE/CALL.json (or CALL_reask.json) and appends one line to
/home/claude/ideas/overnight/method/opus_audit.jsonl: model ids, every tool call, and whether the instance kept to the
protocol (exactly one Read, of its own prompt file). A deviation is logged, and the reply is still used (Amendment 35.1).
Refuses to overwrite an existing reply.
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
IDEAS = "/home/claude/ideas/overnight/method"


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    src, race, call = sys.argv[1:4]
    reask = "--reask" in sys.argv[4:]
    man = json.load(open(os.path.join(HERE, "prompts", "MANIFEST.json")))
    e = next((x for x in man["prompts"] if x["race"] == race and x["call"] == call), None)
    if e is None:
        raise SystemExit(f"{race}/{call} is not in the manifest")
    dst = e["reask_path"] if reask else e["reply_path"]
    if os.path.exists(dst):
        raise SystemExit(f"{dst} exists: a saved reply is never overwritten")
    models, tools, last, first_user = set(), [], None, None
    for line in open(src):
        try:
            ev = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        msg = ev.get("message") or {}
        if msg.get("role") == "user" and first_user is None:
            c = msg.get("content")
            first_user = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict))
        if msg.get("role") != "assistant":
            continue
        if msg.get("model"):
            models.add(msg["model"])
        content = msg.get("content")
        if isinstance(content, str):
            last = content
            continue
        texts = []
        for c in content or []:
            if c.get("type") == "tool_use" and c.get("name") == "SubagentHandback":
                last = (c.get("input") or {}).get("message", "")
                continue
            if c.get("type") == "tool_use":
                inp = c.get("input") or {}
                tools.append({"tool": c.get("name"), "arg": inp.get("file_path") or inp.get("command") or inp.get("pattern") or ""})
            elif c.get("type") == "text":
                texts.append(c.get("text", ""))
        if texts:
            last = "".join(texts)
    if last is None:
        raise SystemExit(f"no assistant text in {src}")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, "w").write(last)
    ok_protocol = (len(tools) == 1 and tools[0]["tool"] == "Read" and tools[0]["arg"] == e["ideas_path"])
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "race": race, "call": call, "reask": reask,
           "transcript": src, "reply": dst, "models": sorted(models), "tools": tools, "protocol_ok": ok_protocol,
           "delivery_note_matches": (first_user or "").strip() == e["delivery_note"].strip(), "chars": len(last)}
    with open(os.path.join(IDEAS, "opus_audit.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps({k: rec[k] for k in ("race", "call", "models", "protocol_ok", "delivery_note_matches", "chars")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
