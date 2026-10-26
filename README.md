# BeforeRoute — run farm and experiment code

Predicting, at the last pre-route repair point, which nets the flow's own parasitic
estimate will get wrong at nine-corner signoff, and spending repair margin only there.

This repository holds only open-source designs and worker scripts. Results are
produced as workflow artifacts and analysed elsewhere.

- `br/` — LibreLane custom steps (`DumpNetsPostGRT`, `TargetedRepairPostGRT`), worker,
  feature/label extraction, dataset builder, trainer, scorer, arm runner, figures.
- `designs/` — spm, crc_pipe, aes_cipher, picorv32 (SKY130 HD configs).
- `farm/` — job specs, dispatcher, collector, local worker.
- `.github/workflows/farm.yml` — one job per spec on the pinned LibreLane 3.0.16 image.

Toolchain: `ghcr.io/librelane/librelane:3.0.16` (OpenROAD `dcf36133a`, Yosys 0.62),
SKY130 PDK at ciel `8afc8346a57fe1ab7934ba5a6056ea8b43078e71`.
