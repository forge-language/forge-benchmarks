# Forge 6k wheel kernel against the existing Rust prime-search fixture

The Forge candidate tests divisibility by 2 and 3 first, then tests divisors in the `6k-1`, `6k+1` sequence. It returns the same prime sum for the benchmark's generated interval. The Rust control and baseline Forge are unchanged. This is an algorithm-level comparison against the existing Rust fixture; it does not isolate a compiler or language advantage.

The current Forge `368b9c8` compiler, runtime, stdlib, headers, native flags, Rust control and workload dimensions were frozen from the current CPU report. A three-way comparison used 60 balanced randomized paired groups, with a same-input prewarm immediately before each measurement. All 160 direct edge/random cases and all 180 prewarms plus 180 measured runs matched the independent sieve reference.

| Comparison | Median time | Paired throughput ratio (95% interval) |
| --- | ---: | ---: |
| Baseline Forge | 74.711 ms | — |
| 6k wheel Forge | 49.731 ms | Baseline Forge / candidate: 1.4979 [1.4961, 1.5008] |
| Existing Rust fixture | 75.491 ms | Rust / candidate: 1.5143 [1.5104, 1.5174] |

The candidate materially reduces the runtime of this task against both existing controls. A previous source-matched experiment applied the same wheel algorithm to Rust and Forge and measured 1.0074 [1.0025, 1.0103] Forge/Rust throughput. That result shows the gain comes from the algorithm change shared by both languages; this report does not claim the compiler itself is 1.5× faster.

- Candidate fixture: [kernels_prime_wheel.fg](../benchmark/cpu/kernels_prime_wheel.fg)
- Reproduction runner: [prime_wheel_compare.py](../benchmark/prime_wheel_compare.py)
- Raw report: [prime-wheel-vs-rust-baseline-2026-10-12.json](prime-wheel-vs-rust-baseline-2026-10-12.json)
- Prior matched-algorithm wheel comparison: [cpu-prime-wheel-2026-10-12.md](cpu-prime-wheel-2026-10-12.md)
- Frozen baseline inputs: [cpu-current-all-2026-10-12.md](cpu-current-all-2026-10-12.md)
