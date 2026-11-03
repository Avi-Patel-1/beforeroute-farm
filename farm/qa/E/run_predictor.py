#!/usr/bin/env python3
"""Experiment E: run a frozen predict(run_dir) module (rung 3's formula, Codex's deterministic baseline) on every main
rung-2 packet and write <pred>/<arm>/<packet_id>.json in the PACKET_FORMAT.md schema.

  run_predictor.py --module /path/baseline.py --deps /path/packet.py /path/weights.json --sums /path/SHA256SUMS \
      --arm codex_det --packets /home/claude/ideas/overnight/reading/packets \
      --pred /home/claude/ideas/overnight/reading/predictions
  run_predictor.py --module farm/qa/E/frozen/formula.py --sha256 <hash> --arm rung3 --packets ... --pred ...

Fail-closed (pre-registration clarification 12; Codex's audit: the earlier version exited 0 with errors or skipped
packets and hashed only the entry module):
  * EVERY inference file is hashed: the entry (--module) and each --deps file must have an expected SHA-256 (from --sums,
    lines "<sha256>  <basename>", or --sha256 for the entry); a missing or different digest refuses before anything runs.
    The verified bytes are copied into a fresh private directory and imported from there, so an unlisted file cannot be
    imported or read from the predictor's own folder.
  * The expected packets come from the committed farm/qa/E/packets_manifest.sha256 (main = pids with rung1 and rung2):
    the packet directories must match it exactly, each rung2/MANIFEST.json must have its committed digest and every
    file it lists must match (no extra files). Nothing is skipped silently.
  * While the predictor runs, an audit hook refuses any file opened outside its verified copies, the packet being read
    and the Python installation, any write, subprocess or network use.
  * predict() is called twice per packet; the outputs must be identical (deterministic) and valid: p_pass finite in
    [0, 1], call pass/fail/abstain, slope finite, kept_clock_ns null or finite > 0 (claim1_ns, if given, finite).
  * Outputs are first written to a staging folder; only if EVERY expected packet produced a valid prediction are they
    copied to <pred>/<arm>/ and the exit code is 0. Any error: exit 1, nothing enters <pred>/<arm>/ unless
    --promote-errors is given (then error records are written; by the registered rule they score as abstentions).
A receipt (dependency digests, runtime versions, packet-manifest digest, counts, errors) is written to
<pred>/../predictor_runs/<arm>/receipt.json.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import math
import os
import shutil
import sys
import sysconfig
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PACKET_MANIFEST = os.path.join(HERE, "packets_manifest.sha256")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_sums(path):
    out = {}
    for line in open(path):
        s = line.strip()
        if not s:
            continue
        h, name = s.split(None, 1)
        name = name.lstrip("*").strip()
        if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
            raise SystemExit(f"[run] malformed digest line in {path}: {s!r}")
        out[name] = h
    return out


def expected_packets(manifest_path):
    rungs, digest = {}, {}
    for line in open(manifest_path):
        s = line.split()
        if len(s) != 2:
            continue
        pid, rung, _ = s[1].split("/", 2)
        rungs.setdefault(pid, set()).add(rung)
        digest[(pid, rung)] = s[0]
    main = sorted(p for p, r in rungs.items() if r == {"rung1", "rung2"})
    return main, set(rungs), digest


def verify_packet(view, want_manifest_sha):
    """The rung-2 view must be byte-identical to what the readers were given."""
    mp = os.path.join(view, "MANIFEST.json")
    if sha(mp) != want_manifest_sha:
        return "MANIFEST.json digest differs from the committed packets_manifest.sha256"
    files = json.load(open(mp))["files"]
    present = set()
    for dp, _, fs in os.walk(view):
        for f in fs:
            present.add(os.path.relpath(os.path.join(dp, f), view))
    extra = present - set(files) - {"MANIFEST.json"}
    if extra:
        return f"{len(extra)} files not in MANIFEST.json (e.g. {sorted(extra)[0]})"
    for rel, meta in files.items():
        p = os.path.join(view, rel)
        if not os.path.isfile(p) or os.path.islink(p) or sha(p) != meta["sha256"]:
            return f"{rel} missing or differs from MANIFEST.json"
    return None


class Guard:
    """Audit hook: while active, only reads under the allowed roots are permitted; writes, subprocesses and sockets
    are violations. Audit hooks cannot be removed; the guard is switched on only around import and predict()."""

    BAD_EVENTS = ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
                  "socket.connect", "socket.bind", "socket.sendto", "socket.getaddrinfo", "urllib.Request",
                  "shutil.rmtree", "os.remove", "os.rename", "os.mkdir", "os.chmod")

    def __init__(self):
        self.active = False
        self.roots = []
        self.violations = []
        self.opened = 0
        py = {sysconfig.get_paths()[k] for k in ("stdlib", "platstdlib", "purelib", "platlib")}
        py |= {sys.prefix, sys.base_prefix, sys.exec_prefix}
        self.py_roots = sorted(os.path.realpath(p) for p in py) + ["/dev/", "/proc/", "/sys/"]
        sys.addaudithook(self.hook)

    def under(self, path, roots):
        rp = os.path.realpath(path)
        return any(rp == r.rstrip("/") or rp.startswith(r.rstrip("/") + "/") for r in roots)

    def hook(self, event, args):
        if not self.active:
            return
        self.active = False         # no re-entry while the hook itself resolves paths
        try:
            self._check(event, args)
        finally:
            self.active = True

    def _check(self, event, args):
        if event == "open":
            path, mode, flags = (list(args) + [None, None, None])[:3]
            if isinstance(path, int):
                return
            if isinstance(path, bytes):
                path = path.decode(errors="replace")
            self.opened += 1
            writes = (isinstance(mode, str) and any(c in mode for c in "wax+")) or \
                     (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC))
            if writes and not path.startswith("/dev/"):
                self.violations.append(f"write {path} ({mode or flags})")
            elif not self.under(path, self.roots + self.py_roots):
                self.violations.append(f"read outside allowed roots: {path}")
        elif any(event == b or event.startswith(b + ".") for b in self.BAD_EVENTS):
            self.violations.append(f"{event} {str(args)[:120]}")


def finite(x):
    return not isinstance(x, bool) and isinstance(x, (int, float)) and math.isfinite(x)


def validate(r, pid):
    if not isinstance(r, dict):
        raise ValueError("predict() did not return a dict")
    if r.get("packet_id") not in (None, pid):
        raise ValueError(f"packet_id {r.get('packet_id')!r} != {pid}")
    pp, call, sl, k = r.get("p_pass"), r.get("call"), r.get("slope"), r.get("kept_clock_ns", "absent")
    if not finite(pp) or not 0.0 <= float(pp) <= 1.0:
        raise ValueError(f"p_pass {pp!r}")
    if call not in ("pass", "fail", "abstain"):
        raise ValueError(f"call {call!r}")
    if not finite(sl):
        raise ValueError(f"slope {sl!r}")
    if k == "absent":
        raise ValueError("kept_clock_ns missing")
    if k is not None and (not finite(k) or float(k) <= 0):
        raise ValueError(f"kept_clock_ns {k!r}")
    rec = {"packet_id": pid, "p_pass": float(pp), "call": call, "slope": float(sl),
           "kept_clock_ns": None if k is None else float(k)}
    if r.get("claim1_ns") is not None:
        if not finite(r["claim1_ns"]):
            raise ValueError(f"claim1_ns {r['claim1_ns']!r}")
        rec["claim1_ns"] = float(r["claim1_ns"])
    if isinstance(r.get("rationale"), str):
        rec["rationale"] = r["rationale"][:2000]
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", required=True, help="entry module (defines --func)")
    ap.add_argument("--deps", nargs="*", default=[], help="every other file the predictor needs (all hashed)")
    ap.add_argument("--sums", default=None, help="SHA256SUMS-style file: expected digests by basename")
    ap.add_argument("--sha256", default=None, help="expected digest of the entry module")
    ap.add_argument("--arm", required=True)
    ap.add_argument("--packets", required=True)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--func", default="predict")
    ap.add_argument("--packets-manifest", default=DEFAULT_PACKET_MANIFEST)
    ap.add_argument("--receipt", default=None)
    ap.add_argument("--promote-errors", action="store_true",
                    help="also write error records into <pred>/<arm>/ (they score as abstentions); exit code stays 1")
    a = ap.parse_args()
    t_start = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    sys.dont_write_bytecode = True
    work = os.path.join(os.path.dirname(os.path.abspath(a.pred)), "predictor_runs", a.arm)
    receipt_path = a.receipt or os.path.join(work, "receipt.json")

    # 1. every inference file hashed
    sums = read_sums(a.sums) if a.sums else {}
    files = [os.path.abspath(a.module)] + [os.path.abspath(d) for d in a.deps]
    names = [os.path.basename(f) for f in files]
    if len(set(names)) != len(names):
        print(f"[run] duplicate basenames among {names}: refusing")
        return 2
    deps = {}
    for f, n in zip(files, names):
        want = sums.get(n) or (a.sha256 if f == files[0] else None)
        if a.sha256 and f == files[0] and sums.get(n) and sums[n] != a.sha256:
            print(f"[run] --sha256 and --sums disagree for {n}: refusing")
            return 2
        got = sha(f)
        print(f"[run] {n}: sha256 {got} (expected {want})")
        if want is None:
            print(f"[run] {n} has no expected digest: every dependency must be hashed; refusing")
            return 2
        if got != want:
            print(f"[run] SHA-256 mismatch for {n}: refusing")
            return 2
        deps[n] = got
    priv = tempfile.mkdtemp(prefix=f"frozen_{a.arm}_")
    for f, n in zip(files, names):
        shutil.copyfile(f, os.path.join(priv, n))
        if sha(os.path.join(priv, n)) != deps[n]:
            print(f"[run] copy of {n} differs: refusing")
            return 2
        os.chmod(os.path.join(priv, n), 0o444)

    # 2. expected packets = the committed manifest (no silent skip)
    main_ids, all_ids, digest = expected_packets(a.packets_manifest)
    present = sorted(p for p in os.listdir(a.packets) if os.path.isdir(os.path.join(a.packets, p)))
    present_main = [p for p in present if os.path.isdir(os.path.join(a.packets, p, "rung1"))
                    and os.path.isdir(os.path.join(a.packets, p, "rung2"))]
    problems = []
    if present_main != main_ids:
        problems.append(f"main packets on disk {len(present_main)} != committed {len(main_ids)}: "
                        f"missing {sorted(set(main_ids) - set(present_main))}, extra {sorted(set(present_main) - set(main_ids))}")
    if set(present) != all_ids:
        problems.append(f"packet folders differ from the committed manifest: {sorted(set(present) ^ all_ids)}")
    for pid in main_ids:
        try:
            why = verify_packet(os.path.join(a.packets, pid, "rung2"), digest[(pid, "rung2")])
        except Exception as e:
            why = f"{type(e).__name__}: {e}"
        if why:
            problems.append(f"{pid}: {why}")
    if problems:
        for p in problems:
            print("[run] PACKET CHECK FAILED:", p)
        return 2
    print(f"[run] {len(main_ids)} main packets match the committed manifest ({sha(a.packets_manifest)[:12]}…)")

    # 3. import the verified copies under the guard
    guard = Guard()
    guard.roots = [priv]
    sys.path.insert(0, priv)
    before = set(sys.modules)
    guard.active = True
    try:
        spec = importlib.util.spec_from_file_location("frozen_predictor", os.path.join(priv, names[0]))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fn = getattr(mod, a.func)
    finally:
        guard.active = False
    if guard.violations:
        print("[run] import violated the guard:", guard.violations[:5])
        return 2

    # 4. predict every expected packet, twice
    stage = os.path.join(work, "staging")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    recs, errors = {}, {}
    for pid in main_ids:
        view = os.path.join(a.packets, pid, "rung2")
        guard.roots = [priv, os.path.realpath(view)]
        nv = len(guard.violations)
        try:
            guard.active = True
            try:
                r1 = fn(view)
                r2 = fn(view)
            finally:
                guard.active = False
            if guard.violations[nv:]:
                raise RuntimeError(f"guard: {guard.violations[nv:][:3]}")
            v1, v2 = validate(r1, pid), validate(r2, pid)
            if v1 != v2:
                raise ValueError("predict() is not deterministic on this packet")
            rec = dict(v1, arm=a.arm, module_sha256=deps[names[0]], deps_sha256=deps)
            recs[pid] = rec
        except Exception as e:
            errors[pid] = f"{type(e).__name__}: {e}"
            traceback.print_exc()
            rec = {"packet_id": pid, "arm": a.arm, "error": errors[pid], "module_sha256": deps[names[0]],
                   "deps_sha256": deps}
        json.dump(rec, open(os.path.join(stage, pid + ".json"), "w"), indent=1)

    third = sorted({m.split(".")[0] for m in set(sys.modules) - before} - set(sys.stdlib_module_names)
                   - {"frozen_predictor", "trueclock_packet", "_distutils_hack"})
    versions = {}
    for m in third:
        v = getattr(sys.modules.get(m), "__version__", None)
        if v:
            versions[m] = str(v)
    ok = not errors and len(recs) == len(main_ids)
    out = os.path.join(a.pred, a.arm)
    written = 0
    if ok or a.promote_errors:
        os.makedirs(out, exist_ok=True)
        for f in sorted(os.listdir(stage)):
            shutil.copyfile(os.path.join(stage, f), os.path.join(out, f))
            written += 1
    receipt = {"arm": a.arm, "entry": names[0], "func": a.func, "dependencies_sha256": deps,
               "runtime": {"python": sys.version.split()[0], **versions},
               "packets_manifest": os.path.relpath(a.packets_manifest, os.path.join(HERE, "..", "..", "..")),
               "packets_manifest_sha256": sha(a.packets_manifest),
               "expected": len(main_ids), "valid": len(recs), "errors": errors,
               "guard_violations": guard.violations, "files_opened_under_guard": guard.opened,
               "deterministic_double_call": True, "written_to_pred": written,
               "promoted_errors": bool(errors) and a.promote_errors,
               "started_utc": t_start,
               "ended_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    os.makedirs(os.path.dirname(receipt_path), exist_ok=True)
    json.dump(receipt, open(receipt_path, "w"), indent=1)
    print(f"[run] {a.arm}: {len(recs)}/{len(main_ids)} valid, {len(errors)} errors, {len(guard.violations)} guard "
          f"violations; runtime {receipt['runtime']}; {written} files written to {out}; receipt {receipt_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
