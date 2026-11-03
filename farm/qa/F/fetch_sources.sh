#!/usr/bin/env bash
# F (Addendum 42): fetch the published materials on the runner, pinned and hash-checked. Nothing third-party is
# committed to this repo. Usage: fetch_sources.sh <dest_dir> [orfsagent] [edaenv]
#   orfsagent: ORFS-agent's AutoTuner-integration job configs, github.com/ABKGroup/ORFS-Agent @ 730f1fa (BSD-3)
#   edaenv:    the EDA-env ICCAD'26 artifact, Zenodo doi:10.5281/zenodo.22990248 (BSD-3; third-party parts keep theirs)
set -euo pipefail
DEST=$1; shift
mkdir -p "$DEST"
get() {  # url out sha256
  for i in 1 2 3 4 5; do
    if curl -sSfL --retry 3 -o "$2" "$1"; then break; fi
    echo "fetch failed ($i): $1"; sleep $((20 * i))
  done
  echo "$3  $2" | sha256sum -c -
}
for what in "$@"; do
  case "$what" in
    orfsagent)
      C=730f1fa11f9c17c0aaac332412af2b2538f42e9b
      B=https://raw.githubusercontent.com/ABKGroup/ORFS-Agent/$C/AutoTuner-integration/AutoTuner/autotune_configs
      O=$DEST/orfsagent/autotune_configs; mkdir -p "$O"
      while read -r f h; do get "$B/$f" "$O/$f" "$h"; done <<'EOF'
aes_asap7.mk c5dc8b523ef4e72702353268eeea841e22f22f412fc2d586e2b2c7bdeae43e9b
ibex_asap7.mk ba3b1d276f5ef4a7e55edd82406c0b3a49185cf58c2ad5375333e1bf9e9f0799
aes_sky130hd.mk 8c41e917b8e4af12479568aaec5de8b233596b8aa978acd1fab02776ac3838d4
ibex_sky130hd.mk e5503a3a780b757e7e42833c33c7f665862bf8803e7969a741040e3bed5d42e9
aes_cipher_top.sdc 599000ac815dfb1c6efe581baf603fd03c3a08dd817532c6d6647fcf105cb03e
ibex_core.sdc da5af96213ec53f50b20ecbf57cb61475f1558111888a09f752dec0f94b766cf
fastroute_asap7.tcl 4994914773d79545fbc2d67b911be1cb01d7621d9fa88d2a6b529f5d9788fe3a
fastroute_sky130hd.tcl 7675f58888702af65ea96b3ec8b4c8195f3437dc5fc4a77d2afc016681678dcc
private.mk 05c4b8c7034bf9fdefa03945c54ed4f68701a1339bd457186f485cb05bf61c73
report_param.sh 3f3a89fcfe95be6e4d7b5e673b883eb47eddcdd5844cf8b458286de9d561375e
EOF
      chmod +x "$O/report_param.sh"
      ;;
    edaenv)
      get "https://zenodo.org/api/records/22990248/files/EDA-env-85-tasks.tar.gz/content" "$DEST/eda-env.tar.gz" \
          3f80927e92be70b4e92deb1e5db7ad6c0009861d43e5c7bb7f8a5026b0a96205
      tar -xzf "$DEST/eda-env.tar.gz" -C "$DEST"
      ;;
    *) echo "unknown source $what"; exit 2 ;;
  esac
done
ls -la "$DEST"
