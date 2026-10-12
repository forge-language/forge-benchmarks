# Paired coroutine codegen/runtime comparison

Each pair uses the same task count, rounds, chunk, seed, observer, Rust control, compiler flags, and per-input prewarm. The baseline and candidate differ only in the compiler/runtime SDK artifacts; both use the same stdlib archive.

| Case | Workers | Baseline ms | Candidate ms | Paired speedup (95% interval) | 1.10 improvement |
| --- | ---: | ---: | ---: | --- | --- |
| scheduler-heavy | 1 | 4.762 | 3.513 | 1.3682 [1.3445, 1.3776] | supported |
| scheduler-heavy | 2 | 4.904 | 5.916 | 0.8961 [0.7333, 1.2827] | inconclusive |
| scheduler-heavy | 4 | 9.982 | 9.295 | 1.0880 [1.0000, 1.2469] | inconclusive |
| mixed-cpu | 1 | 250.589 | 249.742 | 1.0023 [1.0009, 1.0099] | below |
| mixed-cpu | 2 | 139.335 | 137.372 | 1.0113 [0.9331, 1.1149] | inconclusive |
| mixed-cpu | 4 | 89.282 | 90.265 | 0.9391 [0.9137, 1.0823] | below |
| budget-crossing | 1 | 6.802 | 4.408 | 1.5562 [1.5323, 1.6406] | supported |
| budget-crossing | 2 | 4.362 | 2.849 | 1.5666 [1.5180, 1.7482] | supported |
| budget-crossing | 4 | 5.221 | 3.555 | 1.5258 [1.4120, 1.8059] | supported |

The 1.10 improvement column tests whether the candidate is at least 10% faster than the old Forge SDK on this workload; it does not claim 1.10x Rust performance. Raw samples, artifact hashes, compiler commands, and this runner source are retained in the JSON.

Rust 1.53.0 uses the pinned fixture control and is used as a same-input correctness/measurement control, not as the ratio denominator in this report.
