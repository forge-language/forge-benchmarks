# Paired coroutine codegen/runtime comparison

Each pair uses the same task count, rounds, chunk, seed, observer, Rust control, compiler flags, and per-input prewarm. The baseline and candidate differ only in the compiler/runtime SDK artifacts; both use the same stdlib archive.

| Case | Workers | Baseline ms | Candidate ms | Paired speedup (95% interval) | 1.10 improvement |
| --- | ---: | ---: | ---: | --- | --- |
| scheduler-heavy | 1 | 4.531 | 4.139 | 1.0981 [0.9918, 1.1490] | inconclusive |
| scheduler-heavy | 2 | 3.833 | 3.740 | 1.0323 [0.9265, 1.1456] | inconclusive |
| scheduler-heavy | 4 | 8.757 | 8.903 | 1.1504 [0.8535, 1.3596] | inconclusive |
| mixed-cpu | 1 | 249.957 | 249.828 | 1.0001 [0.9965, 1.0064] | below |
| mixed-cpu | 2 | 139.124 | 150.926 | 0.8855 [0.8289, 0.9873] | below |
| mixed-cpu | 4 | 96.447 | 100.134 | 0.9815 [0.8764, 1.1539] | inconclusive |
| budget-crossing | 1 | 6.259 | 6.296 | 0.9958 [0.9538, 1.0416] | below |
| budget-crossing | 2 | 3.289 | 3.299 | 0.9849 [0.9165, 1.0825] | below |
| budget-crossing | 4 | 3.240 | 2.372 | 0.9771 [0.9382, 1.1071] | inconclusive |

The 1.10 improvement column tests whether the candidate is at least 10% faster than the old Forge SDK on this workload; it does not claim 1.10x Rust performance. Raw samples, artifact hashes, compiler commands, and this runner source are retained in the JSON.

Rust 1.53.0 uses the pinned fixture control and is used as a same-input correctness/measurement control, not as the ratio denominator in this report.
