"""Modal backend for the farm: the same LibreLane image and PDK as .github/workflows/farm.yml, the same br/run_job.py.

One call = one job spec (farm/jobs/<tag>.json content). The call returns results/<tag>/ as a tar.gz (the layout
farm/collect.py produces from the GitHub artifacts), so everything downstream (tune.py, criteria) is unchanged.

Deploy once:   modal deploy farm/modal_app.py
Smoke test:    modal run farm/modal_app.py::smoke
Calls are spawned and collected by farm/modal_backend.py (deployed functions keep running if this machine goes away).
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tarfile
import time

import modal

IMAGE_REF = "ghcr.io/librelane/librelane@sha256:4bc9042ba177f73f275b5b39e7d372a07d3f4043f548a0ba7f640097b7205051"
PDK_VERSION = "8afc8346a57fe1ab7934ba5a6056ea8b43078e71"
# the image's own Python (with librelane) and PATH, from its image config; Modal adds its own runtime Python
NIX_PY = "/nix/store/7zqpr7slgvjfjcqfabb2fmlpvc8k23ax-python3-3.13.9-env/bin/python3"
IMG_PATH = ("/nix/store/7zqpr7slgvjfjcqfabb2fmlpvc8k23ax-python3-3.13.9-env/bin:/nix/store/g119ksxxjhq190g79gkbqbpbg9zmvp0m-opensta/bin:"
            "/nix/store/vqq4mi8prw8x5rfwz7b3136rqi8v70m7-yosys-with-plugins-0.62-python3-3.13.9-env/bin:"
            "/nix/store/acqm3cm6m4bj83ygn6ynjksl920zz9zx-openroad-2026-02-17-python3-3.13.9-env/bin:"
            "/nix/store/kw3frc6fbv3zi2m9n0wv93y1nfiyjiy6-netgen-1.5.316/bin:/nix/store/i68lxdmnc7422hvlabbmrhss4sqqkjzq-magic-vlsi-8.3.623/bin:"
            "/nix/store/c8mymw0gckkiw7lqwnm2l6mqnd99xmzy-klayout-0.30.7/bin:/nix/store/nknbcs56x54kqhbv0slfca6v4gmi724v-iverilog-s20250103-60-gdb82380ce/bin:"
            "/nix/store/wl8c1s56dn566asz404bqwcl0gdrw933-verilator-5.044/bin:/nix/store/biz055ybc5x1vxar1dqlrjsw7w9axgc2-tcl-8.6.16/bin:"
            "/nix/store/0akh4i9af1sxvdn439mmx8iafac8cns5-ruby-3.3.10/bin:/root/.nix-profile/bin:/nix/var/nix/profiles/default/bin:"
            "/nix/var/nix/profiles/default/sbin")
NIX_ENV = {"PATH": IMG_PATH, "PDK_ROOT": "/pdk", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
           "SSL_CERT_FILE": "/nix/var/nix/profiles/default/etc/ssl/certs/ca-bundle.crt",
           "NIX_PYTHONPATH": "/host_librelane:/nix/store/7zqpr7slgvjfjcqfabb2fmlpvc8k23ax-python3-3.13.9-env/lib/python3.13/site-packages",
           "TMPDIR": "/tmp"}
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CPU = float(os.environ.get("BR_MODAL_CPU", "4"))        # physical cores (2 vCPU each); farm runners have 4 vCPU
MEM = int(os.environ.get("BR_MODAL_MEM_MB", "16384"))

_env = " ".join(f"{k}={v}" for k, v in NIX_ENV.items())
image = (
    modal.Image.from_registry(IMAGE_REF, add_python="3.12")
    .run_commands(f"mkdir -p /pdk && env {_env} ciel enable --pdk-family sky130 {PDK_VERSION}")
    .add_local_dir(os.path.join(ROOT, "br"), "/src/br", ignore=["**/__pycache__/**", "**/*.pyc"])
    .add_local_dir(os.path.join(ROOT, "designs"), "/src/designs", ignore=["**/runs/**", "**/config.*-*.json"])
    .add_local_dir(os.path.join(ROOT, "farm", "rc"), "/src/farm/rc")
)
app = modal.App("beforeroute-farm", image=image)


def _tar_dir(d: str, arc: str, extra: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        if os.path.isdir(d):
            tf.add(d, arcname=arc)
        for name, text in extra.items():
            data = text.encode()
            info = tarfile.TarInfo(f"{arc}/{name}")
            info.size = len(data)
            info.mtime = int(time.time())
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


@app.function(cpu=CPU, memory=MEM, timeout=6 * 3600, retries=0, ephemeral_disk=50 * 1024)
def run_flow(spec: dict, jobs: int = 4, timeout_s: int = 16000) -> bytes:
    """Run one farm job spec exactly as farm.yml does (br/run_job.py inside the LibreLane image)."""
    tag = spec["tag"]
    work = "/tmp/w"
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(os.path.join(work, "farm", "jobs"))
    shutil.copytree("/src/br", os.path.join(work, "br"))
    shutil.copytree("/src/farm/rc", os.path.join(work, "farm", "rc"))
    dsrc = os.path.join("/src", spec["design"])  # spec["design"] is "designs/<name>"
    shutil.copytree(dsrc, os.path.join(work, spec["design"]))
    p = os.path.join(work, "farm", "jobs", f"{tag}.json")
    json.dump(spec, open(p, "w"), indent=1)
    t0 = time.time()
    r = subprocess.run([NIX_PY, "br/run_job.py", "--job-spec", p, "--jobs", str(jobs), "--results", "results",
                        "--pdk-root", "/pdk", "--timeout", str(timeout_s)],
                       cwd=work, env=NIX_ENV, capture_output=True, text=True)
    runner = {"backend": "modal", "cpu": CPU, "memory_mb": MEM, "jobs": jobs, "exit": r.returncode,
              "seconds": round(time.time() - t0, 1), "host": os.uname().nodename}
    return _tar_dir(os.path.join(work, "results", tag), tag,
                    {"modal_runner.json": json.dumps(runner, indent=1),
                     "modal_runner.log": r.stdout[-20000:] + "\n--- stderr ---\n" + r.stderr[-20000:]})


@app.function(cpu=1, memory=2048, timeout=600)
def probe() -> dict:
    """Image sanity: tool versions and the PDK."""
    out = {}
    for name, cmd in (("librelane", ["librelane", "--version"]), ("openroad", ["openroad", "-version"]),
                      ("yosys", ["yosys", "-V"]), ("python", [NIX_PY, "--version"])):
        try:
            x = subprocess.run(cmd, env=NIX_ENV, capture_output=True, text=True, timeout=120)
            out[name] = (x.stdout or x.stderr).strip()[:200]
        except Exception as e:  # noqa: BLE001
            out[name] = f"error: {e}"
    out["pdk"] = sorted(os.listdir("/pdk"))[:10] if os.path.isdir("/pdk") else "missing"
    out["cpus"] = os.cpu_count()
    return out


@app.local_entrypoint()
def smoke():
    print(probe.remote())
    spec = {"tag": "mx-smoke-spm-001", "design": "designs/spm", "config": "config_sky130.json",
            "overrides": {"RUN_MAGIC_DRC": False, "RUN_KLAYOUT_DRC": False, "RUN_LVS": False, "RUN_KLAYOUT_XOR": False,
                          "RUN_IRDROP_REPORT": False, "RUN_LINTER": False}}
    data = run_flow.remote(spec, 4, 3600)
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        tf.extractall(os.path.join(ROOT, "results"), filter="data")
    print(open(os.path.join(ROOT, "results", spec["tag"], "modal_runner.json")).read())
