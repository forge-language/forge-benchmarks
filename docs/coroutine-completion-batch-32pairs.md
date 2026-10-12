# Paired coroutine codegen/runtime comparison

Each pair uses the same task count, rounds, chunk, seed, observer, Rust control, compiler flags, and per-input prewarm. The baseline and candidate differ only in the compiler/runtime SDK artifacts; both use the same stdlib archive.

| Case | Workers | Baseline ms | Candidate ms | Paired speedup (95% interval) | 1.10 improvement |
| --- | ---: | ---: | ---: | --- | --- |
| scheduler-heavy | 1 | 3.537 | 3.544 | 1.0034 [0.9959, 1.0153] | below |
| scheduler-heavy | 4 | 9.776 | 8.062 | 1.1339 [1.0395, 1.2905] | inconclusive |
| mixed-cpu | 1 | 250.120 | 249.443 | 1.0014 [0.9990, 1.0038] | below |
| mixed-cpu | 4 | 96.700 | 98.527 | 0.9626 [0.8983, 1.0444] | below |
| budget-crossing | 1 | 4.376 | 4.445 | 0.9815 [0.9709, 1.0029] | below |
| budget-crossing | 4 | 3.442 | 3.597 | 0.8552 [0.8092, 1.0170] | below |

The 1.10 improvement column tests whether the candidate is at least 10% faster than the old Forge SDK on this workload; it does not claim 1.10x Rust performance. Raw samples, artifact hashes, compiler commands, and this runner source are retained in the JSON.

Rust 1.53.0 uses the pinned fixture control and is used as a same-input correctness/measurement control, not as the ratio denominator in this report.
