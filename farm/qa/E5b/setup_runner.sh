#!/usr/bin/env bash
# E5b: prepare a GitHub-hosted runner. Downloads the GT2N kit's OpenROAD example (BSD-3) at a pinned commit,
# checks its SHA-256, unpacks it under ./kit, pulls the ORFS image pinned by digest, and records provenance.
set -euo pipefail
: "${IMAGE:?}" "${GT2N_COMMIT:?}" "${KIT_SHA256:?}"

mkdir -p kit/provenance
base="https://raw.githubusercontent.com/azadnaeemi/GT2N/${GT2N_COMMIT}"
curl -fsSL --retry 5 --retry-delay 10 -o kit/gt2n_example.tar.gz \
  "${base}/Openroad_example/gt2n_openroad_runscripts_no_work_20260601.tar.gz"
curl -fsSL --retry 5 --retry-delay 10 -o kit/provenance/GT2N_LICENSE "${base}/LICENSE"
echo "${KIT_SHA256}  kit/gt2n_example.tar.gz" | sha256sum -c -
tar -xzf kit/gt2n_example.tar.gz -C kit --no-same-owner
chmod -R u+rwX,go+rX kit
{
  echo "gt2n_repo=https://github.com/azadnaeemi/GT2N"
  echo "gt2n_commit=${GT2N_COMMIT}"
  echo "kit_tarball=Openroad_example/gt2n_openroad_runscripts_no_work_20260601.tar.gz"
  echo "kit_sha256=${KIT_SHA256}"
} > kit/provenance/kit.txt

ok=0
for i in 1 2 3 4 5; do
  if docker pull "${IMAGE}"; then ok=1; break; fi
  echo "docker pull failed (attempt ${i}); retrying" >&2
  sleep $((i * 30))
done
[ "${ok}" = 1 ] || { echo "could not pull ${IMAGE}" >&2; exit 1; }
docker image inspect "${IMAGE}" --format '{{json .RepoDigests}} {{.Id}}' | tee kit/provenance/image.txt
docker run --rm "${IMAGE}" bash -c \
  'cd /OpenROAD-flow-scripts/flow && . ../env.sh >/dev/null 2>&1; echo "openroad $(openroad -version 2>&1 | tail -1)"; yosys -V; sha256sum /OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v; echo "orfs_scripts_sha256 $(cat /OpenROAD-flow-scripts/flow/scripts/*.tcl | sha256sum | cut -c1-64)"; grep -A6 "^LEC_CHECK:" /OpenROAD-flow-scripts/flow/scripts/variables.yaml | grep default' \
  | tee kit/provenance/tools.txt
{ nproc; free -g | head -2; df -h . | tail -1; lscpu | grep -E 'Model name|^Flags' | cut -c1-2000; } | tee kit/provenance/runner.txt
