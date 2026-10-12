# Paired coroutine codegen/runtime comparison

Each pair uses the same task count, rounds, chunk, seed, observer, Rust control, compiler flags, and per-input prewarm. The baseline and candidate differ only in the compiler/runtime SDK artifacts; both use the same stdlib archive.

| Case | Workers | Baseline ms | Candidate ms | Paired speedup (95% interval) | 1.10 improvement |
| --- | ---: | ---: | ---: | --- | --- |
| scheduler-heavy | 1 | 3.892 | 3.840 | 0.9745 [0.7695, 1.0372] | below |
| scheduler-heavy | 2 | 4.154 | 4.946 | 0.9599 [0.7253, 1.0597] | below |
| scheduler-heavy | 4 | 7.801 | 7.246 | 0.9865 [0.7690, 1.7028] | inconclusive |
| mixed-cpu | 1 | 251.074 | 251.422 | 0.9997 [0.9634, 1.0008] | below |
| mixed-cpu | 2 | 127.099 | 130.325 | 0.9899 [0.9027, 1.0109] | below |
| mixed-cpu | 4 | 96.885 | 89.045 | 1.0452 [0.9692, 1.3636] | inconclusive |
| budget-crossing | 1 | 4.588 | 4.465 | 1.0193 [0.9856, 1.0714] | below |
| budget-crossing | 2 | 2.868 | 2.831 | 1.0412 [0.9677, 1.1489] | inconclusive |
| budget-crossing | 4 | 3.133 | 3.239 | 0.8842 [0.6878, 1.1288] | inconclusive |

The 1.10 improvement column tests whether the candidate is at least 10% faster than the old Forge SDK on this workload; it does not claim 1.10x Rust performance. Raw samples, artifact hashes, compiler commands, and this runner source are retained in the JSON.

Rust 1.53.0 uses the pinned fixture control and is used as a same-input correctness/measurement control, not as the ratio denominator in this report.
