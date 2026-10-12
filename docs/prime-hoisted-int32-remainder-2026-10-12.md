# Hoisted int32 remainder probe for trial division — rejected

The earlier generic narrowing candidate checked operand widths at every
remainder operation and regressed. This probe tested a narrower design: branch
once per value to a fast path when `value` is nonnegative and at most
`INT32_MAX`; run the existing trial-divisor loop there with a direct signed
32-bit remainder; retain the original checked 64-bit loop as the fallback.
Within the fast path, `d` starts at 3 and increases by 2. The loop condition
`d*d <= value <= INT32_MAX` stops by `d == 46342`, before the square can
overflow `int64` and while `d` still fits `int32`. The 32-bit operation is
therefore equivalent on that path. All other values use the original path.

This was a code-generation prototype, not a compiler change: the benchmark
fixture added the explicit `value <= INT32_MAX` split, then the generated C
for only the small-value branch replaced `FORGE_MOD(value, d)` with a direct
`int32_t` remainder. The full-width fallback was left intact. The baseline
used the unmodified fixture. Both ran against the same Rust control and
artifacts, dimensions, 24 seeds, prewarmed balanced order, CPU 0 and
independent reference. All runner correctness checks passed. Both Forge
binaries also passed 13 direct primality checks around negative, small and
signed-32-bit boundary values (including `INT32_MAX` and values above it).

| Variant | Forge median | Rust median | Rust / Forge throughput (95% interval) |
| --- | ---: | ---: | ---: |
| Original checked 64-bit path | 74.555 ms | 75.686 ms | 1.0151 [1.0112, 1.0191] |
| Hoisted int32 path plus fallback | 75.000 ms | 75.726 ms | 1.0101 [1.0073, 1.0170] |

The separate Forge/Rust intervals overlap. A paired ratio-of-ratios using the
same seed and pair order in both runs gives candidate Forge/Rust divided by
baseline Forge/Rust = 0.9973 [0.9896, 1.0024] (10,000 bootstrap resamples of
the median). It includes 1, so the relative change is inconclusive; there is
no evidence this candidate improves Forge. Some baseline pairs contain shared
large timing excursions, so a comparison of Forge time alone across the two
separate runs overstates the certainty of a small regression. No sample was
removed. Candidate disassembly contains `idivl` at `0x2cc4` for the narrow
path and `idivq` at `0x2819` for the fallback. Even if the narrow divide helps
some inputs, the split did not establish an end-to-end benefit. This candidate
does not approach 1.10x Rust and is not adopted.
[Baseline samples](prime-hoisted-int32-baseline-2026-10-12.json),
[candidate samples](prime-hoisted-int32-candidate-2026-10-12.json).
