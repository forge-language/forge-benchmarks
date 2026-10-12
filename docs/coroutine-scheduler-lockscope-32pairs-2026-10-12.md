# Paired coroutine codegen/runtime comparison

Each pair uses the same task count, rounds, chunk, seed, observer, Rust control, compiler flags, and per-input prewarm. The baseline and candidate differ only in the compiler/runtime SDK artifacts; both use the same stdlib archive.

| Case | Workers | Baseline ms | Candidate ms | Paired speedup (95% interval) | 1.10 improvement |
| --- | ---: | ---: | ---: | --- | --- |
| scheduler-heavy | 1 | 3.815 | 3.591 | 1.0087 [0.9918, 1.0661] | below |
| scheduler-heavy | 4 | 8.953 | 7.918 | 1.2524 [1.0437, 1.4665] | inconclusive |
| mixed-cpu | 1 | 250.753 | 251.536 | 0.9972 [0.9951, 0.9993] | below |
| mixed-cpu | 4 | 87.659 | 90.077 | 1.0005 [0.9501, 1.0410] | below |
| budget-crossing | 1 | 4.488 | 4.434 | 1.0018 [0.9746, 1.0465] | below |
| budget-crossing | 4 | 2.969 | 3.068 | 0.9652 [0.8336, 1.1748] | inconclusive |

The 1.10 improvement column tests whether the candidate is at least 10% faster than the old Forge SDK on this workload; it does not claim 1.10x Rust performance. Raw samples, artifact hashes, compiler commands, and this runner source are retained in the JSON.

Rust 1.53.0 uses the pinned fixture control and is used as a same-input correctness/measurement control, not as the ratio denominator in this report.
