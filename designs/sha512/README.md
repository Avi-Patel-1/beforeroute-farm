# sha512: SHA-512/384/256/224 hash core with 32-bit register API: 64-bit adders/rotates, 16x64-bit W schedule

Unmodified RTL copied (not symlinked) from https://github.com/secworks/sha512 src/rtl (commit e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd).
Author/copyright: Joachim Strombergson / Secworks Sweden AB (c) 2014.
License: **BSD-2-Clause (LICENSE)**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `sha512`; single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 20.0 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: Not from openlane-ci-designs; the OpenLane v1 sha512 regression used clk 'clk' at ~20 ns. Here CLOCK_PERIOD 20, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45.

## Files

- `src/sha512.v`  sha256 `175837285a5eb7f8a620f632342629186478d9f0b7f3f959afa48c38d2ea00b1`
- `src/sha512_core.v`  sha256 `4f01ed075906c1ea065c5565ad36f3da72c3c2a482c3defebd3dedc1d5b296ac`
- `src/sha512_h_constants.v`  sha256 `6ab74a4fb77354a648c567cc6677cfaf8d6aab2c8e91d73e585b601cf920807e`
- `src/sha512_k_constants.v`  sha256 `b87e10a1065135f931884a68ae30acf9f78b38e4f050cbbd1ad0b056048923d1`
- `src/sha512_w_mem.v`  sha256 `51aca3c6157670bf3586550a94c33f8dfc52570972cf5c3d1a288a594f8ee46d`
- `src/LICENSE`  sha256 `81899e14798bc6a06e02f48959e1825b9e631f0415bccf5b74e589dabd7c7f80`
