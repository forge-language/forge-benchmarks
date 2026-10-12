# Range-guarded Mersenne fold for the LCG benchmark

The existing LCG implementation was already close to the unchanged Rust control. This source-level Forge candidate adds a fast path when the initial seed is in `[0, 2147483647)`, then uses the recurrence invariant to keep every value in that range. Seeds outside it retain the original wrapping multiply and signed remainder path. The Rust fixture is unchanged, so this is an algorithm-level Forge optimization result, not a compiler-wide language comparison.

For `M = 2^31 - 1` and `0 <= value < M`, the product `x = value * 48271` is positive and fits in 47 bits. Write `x = high * 2^31 + low`. Since `2^31` is congruent to 1 modulo `M`, `x mod M` equals `(high + low) mod M`. Here `high <= 48270`, `low <= M`, so at most one subtraction of `M` is needed. That result is again in `[0, M)`, establishing the fast-path invariant. The product and fold intermediates cannot overflow `int64`.

The current Forge `368b9c8` SDK, runtime, stdlib, headers, native flags, Rust control and dimensions were frozen from the current CPU report. The three-way comparison used 60 paired groups with balanced randomized order among baseline Forge, candidate Forge and Rust; each same-seed binary was prewarmed immediately before its measurement. The ratio is numerator kernel time divided by denominator kernel time. All 584 direct boundary/randomized cases matched the independent Python reference for all three binaries; all 180 per-input prewarms and 180 measurements also matched.

| Comparison | Median ratio | Paired 95% interval | Interpretation |
| --- | ---: | ---: | --- |
| Baseline Forge / candidate Forge | 1.1464 | [1.1419, 1.1488] | Candidate Forge is 14.6% faster |
| Rust / candidate Forge | 1.1563 | [1.1506, 1.1590] | Candidate Forge exceeds the Rust control by 15.6% |
| Rust / baseline Forge | 1.0058 | [1.0024, 1.0092] | Confirms the original near-parity baseline |

This supports the 1.10 target for the tested LCG workload with the specialized Forge implementation. It does not show a general `%` lowering improvement or guarantee the same gain for arbitrary inputs; the fast path is restricted by a runtime seed guard and the original path remains the fallback. The candidate source and all timing samples, checksums, artifact/header hashes, benchmark dimensions, and runner source are preserved below.

- Candidate fixture: [kernels_lcg_mersenne_fold.fg](../benchmark/cpu/kernels_lcg_mersenne_fold.fg)
- Reproduction runner: [lcg_mersenne_fold_compare.py](../benchmark/lcg_mersenne_fold_compare.py)
- Raw report: [lcg-positive-mersenne-fold-2026-10-12.json](lcg-positive-mersenne-fold-2026-10-12.json)
- Current SDK comparison: [cpu-current-all-2026-10-12.md](cpu-current-all-2026-10-12.md)
