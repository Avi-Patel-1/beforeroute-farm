#!/usr/bin/env python3
"""Experiment C ("method, not model"; docs/qa_week/C_PREREG.md): shared definitions.

Reuses the Addendum 32/35 machinery unchanged (farm/tune_a32.py, farm/tune_a35.py): the start set, the prompt text and
run summaries, the knob space, the reply parser (clamping, <= 8 pins) and the TPE study.
What is new here:
  scores_only()   the scores-only prompt = the full prompt with every signoff-report line deleted, one line with the three
                  constraint values the optimizer is told inserted per run, and three fixed sentences that point at the
                  reports re-worded to point at the scores (EDITS). Nothing else changes.
  script_pins()   arm c (tag letter d): the four-line deterministic rule-writer.
  validate()      a reply -> rule file check (tune_a35.parse_policy, the parser every A35 policy went through).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))                 # farm/qa/C
FARM = os.path.abspath(os.path.join(HERE, "..", ".."))             # farm
sys.path.insert(0, FARM)
import tune as T  # noqa: E402
import tune_a27 as A  # noqa: E402
import tune_a32 as B  # noqa: E402
import tune_a35 as R  # noqa: E402  (importing it points tune_a27 at the A35 state; drivers re-point it)

ROOT = T.ROOT
IDEAS = "/home/claude/ideas/overnight/method"                     # hand-off folder the coordinator reads and writes
OPUS_PROMPTS = os.path.join(IDEAS, "opus_prompts")
OPUS_REPLIES = os.path.join(IDEAS, "opus_replies")
REPO_PROMPTS = os.path.join(HERE, "prompts")                       # committed copies (byte-identical)
REPO_REPLIES = os.path.join(HERE, "replies")
A35_STATE = os.path.join(ROOT, "results", "tune_xa", "state.json")
A32_STATE = os.path.join(ROOT, "results", "tune_x8", "state.json")

RULE_DESIGNS = list(R.DES)            # xtea, cic_decimator, zipdiv, usb_cdc_core, wbqspiflash
SEEDS = list(R.SEEDS)                 # 1, 2
PROP_DESIGNS = list(B.HELD)           # xtea, zipdiv, usb_cdc_core, wbqspiflash, cic_decimator, APU, PPU


def rule_race(d, s):
    return f"rule-{d}-s{s}"


def prop_race(d):
    return f"prop-{d}"


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# ---------------------------------------------------------------- scores-only prompts

REPORT_PREFIXES = ("  setup: ", "  hold: ", "  electrical: ", "  cells: ", "  routing: ", "  clock: ",
                   "  run stopped before signoff")
HEAD = re.compile(r"^- (?:start \S+|round \d+) \[(?P<tag>[^\]]+)\] ")


def _phrase(s):
    """A regex for a fixed phrase whose line breaks may sit at any space (A32 and A35 wrap the same sentence differently)."""
    return r"\s+".join(re.escape(w) for w in s.split(" "))


EDITS = [
    (_phrase("Each run shows its setting and a signoff summary."),
     "Each run shows its setting and its scores (T_eff and the three constraint values the optimizer sees)."),
    (_phrase("using what the signoff summaries tell you (for example which corner limits setup, whether the worst path "
             "touches a port, hold-buffer counts, slew/cap pins against the bar, congestion, wire length against the "
             "pre-route estimate)"),
     "using what the scores tell you"),
    (_phrase("what the reports suggest"), "what the scores suggest"),
]


def views_for(rows, default_clock):
    """tag -> what TPE is told about the run: (value, constraints). rows = [(tag, record)]; record as in the states
    (teff, constraints). A run without a result is told 2 x the default clock and [1000, 1000, 1000] (tune_a35.warm/tell)."""
    out = {}
    for tag, v in rows:
        cons = v.get("constraints") or [1e3, 1e3, 1e3]
        out[tag] = {"teff": v.get("teff"), "cons": [float(c) for c in cons], "penalty": 2.0 * default_clock}
    return out


def _g(x):
    return f"{x:.0f}" if abs(x - round(x)) < 1e-9 else f"{x:.3f}"


def score_line(view):
    c = view["cons"]
    if view["teff"] is None:
        return (f"  scores: no result; the optimizer is told T_eff {view['penalty']:.3f} ns (twice the default clock) and "
                f"constraints [{_g(c[0])}, {_g(c[1])}, {_g(c[2])}]")
    return (f"  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = "
            f"[{_g(c[0])}, {c[1]:+.3f}, {_g(c[2])}]; FEASIBLE only if all three are <= 0")


def scores_only(text, views):
    """(scores-only text, report lines deleted, score lines inserted). Asserts every edit applies exactly once."""
    out, cur, n_del, n_ins = [], None, 0, 0
    for line in text.split("\n"):
        m = HEAD.match(line)
        if m:
            cur = m.group("tag")
        if line.startswith(REPORT_PREFIXES):
            n_del += 1
            continue
        out.append(line)
        if line.startswith("  setting ") and cur is not None:
            out.append(score_line(views[cur]))
            n_ins += 1
            cur = None
    new = "\n".join(out)
    for pat, rep in EDITS:
        new, k = re.subn(pat, rep, new)
        assert k == 1, (pat[:60], k)
    return new, n_del, n_ins


def rule_prompt_full(d, s):
    """g's round-1 prompt for race (d, s), regenerated by tune_a35.prompt_text (equals the committed file byte for byte)."""
    return R.prompt_text({"tags": {}, "policies": {}}, d, s, 1)


def rule_views(d):
    return views_for([(t, v) for t, v, _ in B.start_set(d)], B.HELD[d])


def prop_prompt_full(st, d, k, arm="p"):
    """Arm a's prompt text (tune_a32.agent_prompt) for round k of design d, with this arm's own history in state st."""
    ref = B.ref_drv_x8(d)
    rows = B.history(st, d, arm)
    hist = []
    for label, tag, p, v, why in rows:
        line = B.run_line(label, tag, p, v, ref)
        if why:
            line += f"\n  (your rationale then: {why})"
        hist.append(line)
    fn, cells = B.FUNCTION.get(d, ("", ""))
    text = B.PROMPT.format(design=d, function=fn or "open-source design", default=B.HELD[d], cells=cells or "?", bar=ref,
                           knobs=B.knob_text(), n=len(rows), history="\n".join(hist), round=k, rounds=B.ROUNDS,
                           k=B.PER_ROUND)
    views = views_for([(t, v) for t, v, _ in B.start_set(d)] +
                      [(t, v) for t, v in sorted(st["tags"].items()) if v["design"] == d and v["arm"] == arm],
                      B.HELD[d])
    return text, views


# ---------------------------------------------------------------- arm c: the four-line script (tag letter d)

def script_pins(start):
    """Pin period_frac 0.45 + SYNTH_STRATEGY, RC_MODEL, FP_CORE_UTIL of the lowest-T_eff feasible start run (scores only)."""
    ok = [(v["teff"], i, p) for i, (_, v, p) in enumerate(start) if v.get("teff") is not None and T.feasible(v.get("constraints"))]
    best = min(ok)[2]
    return {"period_frac": 0.45, "SYNTH_STRATEGY": best["SYNTH_STRATEGY"], "RC_MODEL": best["RC_MODEL"], "FP_CORE_UTIL": best["FP_CORE_UTIL"]}


def script_rule_file(d):
    pins = script_pins(B.start_set(d))
    return {"rationale": "four-line script (farm/qa/C/clib.py script_pins): period_frac 0.45 plus SYNTH_STRATEGY, RC_MODEL "
                         "and FP_CORE_UTIL of the lowest-T_eff feasible start run", "pins": pins}


# ---------------------------------------------------------------- replies -> rule files

def validate(raw):
    """Parse a rule-writer reply exactly as Addendum 35 did (tune_a35.parse_policy: first '{' to last '}', JSON, unknown
    knobs dropped, values clamped, pins beyond 8 dropped). ok=False only when no JSON policy can be read."""
    try:
        pol = R.parse_policy(raw)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    pf = pol["pins"].get("period_frac")
    return {"ok": True, "pins": pol["pins"], "rationale": pol["rationale"], "log": pol["log"], "n_pins": len(pol["pins"]),
            "period_frac": pf, "pins_period_frac_le_05": pf is not None and pf <= 0.5}


def validate_settings(raw):
    """Parse a proposer reply exactly as Addendum 32 did (tune_a32.agent_ingest): JSON with 'settings', >= 2 of them."""
    try:
        m = re.search(r"\{.*\}", raw, re.S)
        rep = json.loads(m.group(0))
        sets = rep["settings"][:B.PER_ROUND]
        if len(sets) < B.PER_ROUND:
            return {"ok": False, "error": f"reply has {len(sets)} settings"}
        return {"ok": True, "rationale": str(rep.get("rationale", ""))[:1200], "settings": sets}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
