#!/usr/bin/env python3
"""Experiment C: write the scores-only prompt files every Opus call needs, plus MANIFEST.json (docs/qa_week/C_PREREG.md).

  rule races (lens A37, arm s): rule-<design>-s<seed>/round1.md  10 files, one fresh Opus instance each (as g's)
  prop races (lens A38, arm p): prop-<design>/round1.md            7 files now; rounds 2-4 are written by tune_c.py
                                                                    (same function) once the arm's previous round lands
Each file is written to farm/qa/C/prompts/ (committed) and copied byte for byte to the hand-off folder
/home/claude/ideas/overnight/method/opus_prompts/; its reply goes, unedited, to .../opus_replies/<race>/<call>.json.
A prompt already on disk is never rewritten (it is part of the record); a regenerated text that differs is an error.
Usage: make_prompts.py [--check]   (--check: verify only, write nothing)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import clib as C  # noqa: E402

# The delivery notes the A35 and A32 instances received (copied from their transcripts), with only the path changed.
NOTE_RULE = ("Your complete task is in one file: {path}\nRead that file once with the Read tool. Do not read any other file "
             "and do not use any other tool. Then do exactly what the file says, and reply with only the JSON it asks for "
             "(no other text).")
NOTE_PROP = ("Read the file {path} with the Read tool. That file is your entire task. Do not open any other file, run any "
             "command, or search anything. Reply with exactly the JSON the file asks for and nothing else.")
MANIFEST = os.path.join(C.REPO_PROMPTS, "MANIFEST.json")


def load_manifest():
    return C.A.load(MANIFEST, {"prompts": [], "delivery_notes": {"rule": NOTE_RULE, "prop": NOTE_PROP}})


def _write(rel_race, call, text, check):
    repo = os.path.join(C.REPO_PROMPTS, rel_race, f"{call}.md")
    ideas = os.path.join(C.OPUS_PROMPTS, rel_race, f"{call}.md")
    for path in (repo, ideas):
        if os.path.exists(path):
            if open(path).read() != text:
                raise SystemExit(f"{path} exists with different content: a written prompt is never rewritten")
            continue
        if check:
            raise SystemExit(f"{path} missing")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").write(text)
    return repo, ideas


def entry(kind, race, call, design, text_path, ideas_path, original=None, seed=None, rnd=1, state=None):
    e = {"kind": kind, "race": race, "call": call, "design": design, "seed": seed, "round": rnd,
         "repo_path": os.path.relpath(text_path, C.ROOT), "ideas_path": ideas_path, "sha256": C.sha256(text_path),
         "reply_path": os.path.join(C.OPUS_REPLIES, race, f"{call}.json"),
         "reask_path": os.path.join(C.OPUS_REPLIES, race, f"{call}_reask.json"),
         "delivery_note": (NOTE_RULE if kind == "rule" else NOTE_PROP).format(path=ideas_path)}
    if original:
        e["original"] = original
    if state:
        e["state"] = state
    return e


def add_entries(new):
    man = load_manifest()
    have = {(e["race"], e["call"]) for e in man["prompts"]}
    for e in new:
        if (e["race"], e["call"]) not in have:
            man["prompts"].append(e)
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    json.dump(man, open(MANIFEST, "w"), indent=1)
    os.makedirs(C.OPUS_PROMPTS, exist_ok=True)
    json.dump(man, open(os.path.join(C.OPUS_PROMPTS, "MANIFEST.json"), "w"), indent=1)


def rule_prompts(check=False):
    out = []
    for d in C.RULE_DESIGNS:
        for s in C.SEEDS:
            full = C.rule_prompt_full(d, s)
            orig = os.path.relpath(C.R.ppath(d, s, 1, "prompt.md"), C.ROOT)
            assert full == open(os.path.join(C.ROOT, orig)).read(), f"{orig}: regenerated text differs from the committed prompt"
            text, nd, ni = C.scores_only(full, C.rule_views(d))
            race = C.rule_race(d, s)
            repo, ideas = _write(race, "round1", text, check)
            out.append(entry("rule", race, "round1", d, repo, ideas, original=orig, seed=s))
            print(f"[C] {race}/round1: {len(full)} -> {len(text)} chars, {nd} report lines deleted, {ni} score lines")
    return out


def prop_prompt(st, d, k, check=False, state_path=None):
    full, views = C.prop_prompt_full(st, d, k)
    orig = None
    if k == 1:
        orig = os.path.join("farm", "agent_a32", d, "round1_prompt.md")
        assert full == open(os.path.join(C.ROOT, orig)).read(), f"{orig}: regenerated text differs from the committed prompt"
    text, nd, ni = C.scores_only(full, views)
    race = C.prop_race(d)
    repo, ideas = _write(race, f"round{k}", text, check)
    print(f"[C] {race}/round{k}: {len(full)} -> {len(text)} chars, {nd} report lines deleted, {ni} score lines")
    return entry("prop", race, f"round{k}", d, repo, ideas, original=orig, rnd=k, state=state_path if k > 1 else None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    new = rule_prompts(a.check)
    new += [prop_prompt({"tags": {}}, d, 1, a.check) for d in C.PROP_DESIGNS]
    if not a.check:
        add_entries(new)
    print(f"[C] {len(new)} prompts {'verified' if a.check else 'written'}; manifest {os.path.relpath(MANIFEST, C.ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
