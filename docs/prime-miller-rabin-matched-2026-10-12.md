# Matched Miller–Rabin prime-search comparison

The prime benchmark checks 256,000 consecutive integers per timed run. A bounded deterministic Miller–Rabin path using bases 2 and 3 was added to both Forge and Rust fixtures for odd values below 1,373,653; larger values retain trial division. The fallback loop uses `d <= value / d`, avoiding overflow in the divisor bound. The timed seed range remains below the cutoff, so the benchmark exercises the Miller–Rabin path.

The four-way run used current Forge HEAD `368b9c8`, its frozen compiler/runtime/stdlib and native build artifacts, the unchanged Rust fixture, and matched candidate fixtures. It ran 48 randomized groups balanced over all 24 execution orders, with a same-input prewarm before each timed sample. All 175 direct cases—including cutoff/fallback boundaries and larger prime/composite values—plus 192 prewarms and 192 measurements matched the independent reference.

| Fixture | Median kernel time |
| --- | ---: |
| Baseline Forge | 74.790 ms |
| Miller–Rabin Forge | 26.443 ms |
| Baseline Rust | 75.805 ms |
| Miller–Rabin Rust | 27.026 ms |

| Comparison (numerator time / denominator time) | Median throughput ratio (95% interval) |
| --- | ---: |
| Baseline Forge / Miller–Rabin Forge | 2.8212 [2.8073, 2.8329] |
| Baseline Rust / Miller–Rabin Rust | 2.7874 [2.7807, 2.8071] |
| Miller–Rabin Rust / Miller–Rabin Forge | 1.0192 [1.0130, 1.0261] |
| Baseline Rust / Baseline Forge | 1.0100 [1.0091, 1.0123] |

This is an algorithm-level workload improvement: the matched algorithm makes both implementations about 2.8× faster. Forge is about 1.9% faster than Rust for the matched candidate on this host, which remains below the 1.10 target. The candidate fixtures are experimental benchmark code and are not adopted into the compiler or default kernels.

- Forge fixture: [kernels_prime_miller_rabin.fg](../benchmark/cpu/kernels_prime_miller_rabin.fg)
- Rust fixture: [kernels_prime_miller_rabin.rs](../benchmark/cpu/kernels_prime_miller_rabin.rs)
- Reproduction runner: [prime_mr_compare.py](../benchmark/prime_mr_compare.py)
- Full raw samples and hashes: [prime-mr-matched-fourway-2026-10-12.json](prime-mr-matched-fourway-2026-10-12.json)
- Baseline inputs: [current CPU report](cpu-current-all-2026-10-12.md)
