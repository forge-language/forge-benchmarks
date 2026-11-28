# Recovering medium UTF-8 length performance in Forge-generated JavaScript

The earlier string-runtime study recorded a 4.6% increase in elapsed time on its long `str_len` workload. Replaying its original emitted baseline against the length-change commit reduced median paired elapsed time by **48.2%** on that workload. Comparing the preceding substring-only compiler with the length-change commit reduced it by **48.1%**. Both comparisons ran the same 35,000-iteration Forge loop, which sums the byte lengths of a 1,024-unit ASCII string and 256 repetitions of a CJK character followed by an emoji. [Earlier study](js-string-runtime-2026-11-28.md) · [Original measurements](js-string-runtime-2026-11-28-v3.json)

The JavaScript runtime previously allocated a UTF-8 encoding for each length query above 64 UTF-16 code units. The new path reuses the substring buffer for primitive strings of 65 through 2,730 code units. A length query allocates 8 KiB only when the shared buffer is smaller. Three bytes per code unit bound the entire encoding, including lone surrogates, so `TextEncoder.encodeInto(...).written` gives the complete byte length. Substring calls can grow the same buffer to 192 KiB. The runtime retains storage across calls and re-encodes each input. Strings of up to 64 units still use the 192-byte prefix buffer. Larger inputs, host objects and environments without `encodeInto` use the allocating encoder.

## Final compiler confirmation

The production compiler includes a later change to substring code layout. On the published long workload, its emitted JavaScript reduced median paired elapsed time by **47.2% against the historical pre-regression program** and **49.1% against the preceding release**. Each row has ten fresh alternating pairs on CPU 8. The short and above-cap controls use the preceding release as their baseline. All 80 processes returned their expected UTF-8 totals. [Preceding release](https://github.com/forge-language/forge/commit/b9fa8dd03e5643b013072fbff150e10481e548fc) · [Production compiler](https://github.com/forge-language/forge/commit/addddb0fe2722fb804854190e9002a2c76a96142) · [Final observations](js-length-recovery-2026-11-28-final.json)

| Baseline and workload | Baseline → production (ms) | Paired median | Paired IQR |
| --- | ---: | ---: | ---: |
| Historical program, published long workload | 131.46 → 69.32 | −47.2% | −47.5% to −46.8% |
| Preceding release, published long workload | 135.37 → 69.03 | −49.1% | −49.5% to −48.4% |
| Preceding release, short ASCII | 11.00 → 10.94 | −0.4% | −1.4% to +0.6% |
| Preceding release, 16,384-unit ASCII | 84.28 → 84.49 | +0.8% | −0.8% to +2.7% |

The final replay archive contains the three exact emitted programs, the published bridge and the four-case runner. [Final replay archive](js-length-recovery-2026-11-28-final-emitted.tar.xz)

```sh
work=$(mktemp -d)
tar -xJf docs/compiler/js-length-recovery-2026-11-28-final-emitted.tar.xz -C "$work"
taskset -c 8 node "$work/replay.cjs" "$work/final.json"
```

## Length-change commit measurements

Each sample ran in a fresh Node v24.15.0 process pinned to logical CPU 8 of an Intel Core i5-13400F. Two quarter-length calls warmed the emitted function before one timed call. Ten baseline/candidate pairs alternated order. The times below are separate medians in milliseconds. The percentage and interquartile range summarize the ten paired elapsed-time changes, calculated as 100 × (candidate / baseline − 1). The archived baseline appears only in the first row. All subsequent rows use the immediately preceding compiler with the substring optimization already enabled. [All 17 published fixture cases](js-length-recovery-2026-11-28-selected.json) · [Archived-baseline replay and six additional length controls](js-length-recovery-2026-11-28-controls.json)

| Workload | Baseline → selected (ms) | Paired median | Paired IQR |
| --- | ---: | ---: | ---: |
| Original emitted baseline, published long workload | 134.11 → 68.95 | −48.2% | −48.9% to −47.7% |
| Immediate baseline, published long workload | 133.17 → 69.05 | −48.1% | −49.0% to −46.1% |
| 65-unit ASCII | 65.64 → 13.90 | −78.8% | −79.0% to −78.7% |
| 1,024-unit ASCII | 69.40 → 30.65 | −55.6% | −56.3% to −55.4% |
| 1,024-unit mixed Unicode | 218.19 → 136.24 | −36.4% | −38.2% to −36.0% |
| 2,730-unit dense Unicode | 106.80 → 77.03 | −26.4% | −27.7% to −25.3% |
| 2,731-unit dense Unicode | 103.44 → 103.68 | +0.4% | 0.0% to +2.1% |
| 16,384-unit ASCII | 82.39 → 84.40 | +2.5% | +0.4% to +4.1% |
| 16,384-unit mixed Unicode | 334.50 → 333.05 | −0.3% | −0.7% to +0.2% |
| Short ASCII | 11.01 → 11.06 | +2.6% | −0.9% to +6.5% |
| Short Unicode | 9.58 → 9.75 | +1.7% | +0.8% to +6.9% |
| Boxed string | 63.57 → 62.91 | +0.2% | −2.6% to +1.0% |
| Mixed report using lengths and builder appends | 26.03 → 25.96 | −0.8% | −1.2% to +1.4% |

The 16,384-unit ASCII control took 2.5% longer even though it uses the allocating path. The tiny ASCII and Unicode medians also increased. Allocation on first use happens during warm-up. These timings measure steady-state calls in this Node version.

## Inputs and reproduction

The original emitted baseline matches SHA-256 `ce7d682aeabf7a921d8c7682460627a7ac62fdf1baacc2b3734be522d70fd9d4` in the earlier raw report. The immediate baseline and selected compiler used GCC 15.2.0, CMake Release and `-O3 -DNDEBUG`. Their `compiler/codegen_js.c` SHA-256 values were `4b32fb0195d56d2d96bb99297db4fca5a122a1006aa4cf5ecb20d55bf306f8a8` and `fff352287198c92ac50d742ea1a289c3441ea67cf8fbef45018b93deb09307a8`. The raw reports include executable and emitted-source identities. The Forge fixture, bridge and official runner match the hashes from the earlier study. The official runner verifies every length total and builder output using its Python oracle. The additional replay checks every total against Node's `Buffer.byteLength`. [Immediate baseline compiler](https://github.com/forge-language/forge/commit/64574006ce36e2e10eed4935fad247186823f3f5) · [Selected compiler](https://github.com/forge-language/forge/commit/a5e1d9a592395f9285aed0092242b3d889016f8b)

The archive contains all three emitted programs, the FFI bridge and an executable replay for the historical comparison and extra controls. Run from the benchmark repository and substitute an available CPU as needed. [Emitted programs and replay](js-length-recovery-2026-11-28-emitted.tar.xz)

```sh
work=$(mktemp -d)
tar -xJf docs/compiler/js-length-recovery-2026-11-28-emitted.tar.xz -C "$work"
taskset -c 8 node "$work/replay.cjs" "$work/controls.json"
```

To repeat the full 17-case suite with two Release compilers and an SDK, run the existing benchmark.

```sh
python3 -B benchmark/compiler/js_string_runtime_bench.py \
  --baseline /path/to/suffix-only/forge --candidate /path/to/length/forge \
  --root ../forge/build --cpu 8 --pairs 10 --build-note 'Local Release builds' \
  --output /tmp/length-selected.json
```
