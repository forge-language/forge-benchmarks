# Paired coroutine codegen/runtime comparison

Each pair uses the same task count, rounds, chunk, seed, observer, Rust control, compiler flags, and per-input prewarm. The baseline and candidate differ only in the compiler/runtime SDK artifacts; both use the same stdlib archive.

| Case | Workers | Baseline ms | Candidate ms | Paired speedup (95% interval) | 1.10 improvement |
| --- | ---: | ---: | ---: | --- | --- |
| scheduler-heavy | 1 | 3.518 | 3.484 | 1.0062 [0.8705, 1.1375] | inconclusive |
| scheduler-heavy | 2 | 3.654 | 3.378 | 1.1917 [0.9933, 1.3460] | inconclusive |
| scheduler-heavy | 4 | 8.962 | 6.697 | 1.0325 [0.9153, 1.3904] | inconclusive |
| mixed-cpu | 1 | 249.278 | 249.385 | 0.9994 [0.9974, 1.0011] | below |
| mixed-cpu | 2 | 146.421 | 139.700 | 1.0132 [0.9960, 1.0883] | below |
| mixed-cpu | 4 | 97.767 | 97.820 | 1.0472 [0.9903, 1.1503] | inconclusive |
| budget-crossing | 1 | 4.454 | 4.431 | 0.9964 [0.9629, 1.0235] | below |
| budget-crossing | 2 | 2.756 | 2.890 | 0.9436 [0.8538, 1.0109] | below |
| budget-crossing | 4 | 4.050 | 4.101 | 1.0593 [0.9123, 1.2175] | inconclusive |

The 1.10 improvement column tests whether the candidate is at least 10% faster than the old Forge SDK on this workload; it does not claim 1.10x Rust performance. Raw samples, artifact hashes, compiler commands, and this runner source are retained in the JSON.

Rust 1.53.0 uses the pinned fixture control and is used as a same-input correctness/measurement control, not as the ratio denominator in this report.
