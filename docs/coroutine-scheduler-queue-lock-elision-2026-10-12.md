# Paired coroutine codegen/runtime comparison

Each pair uses the same task count, rounds, chunk, seed, observer, Rust control, compiler flags, and per-input prewarm. The baseline and candidate differ only in the compiler/runtime SDK artifacts; both use the same stdlib archive.

| Case | Workers | Baseline ms | Candidate ms | Paired speedup (95% interval) | 1.10 improvement |
| --- | ---: | ---: | ---: | --- | --- |
| scheduler-heavy | 1 | 4.261 | 5.081 | 1.0232 [0.8053, 1.0588] | below |
| scheduler-heavy | 2 | 4.366 | 4.461 | 1.0658 [0.8034, 1.3420] | inconclusive |
| scheduler-heavy | 4 | 13.144 | 9.838 | 1.1894 [1.0558, 1.4633] | inconclusive |
| mixed-cpu | 1 | 249.427 | 249.725 | 0.9985 [0.9960, 1.0014] | below |
| mixed-cpu | 2 | 138.400 | 127.807 | 1.0080 [0.9845, 1.0836] | below |
| mixed-cpu | 4 | 84.483 | 87.670 | 0.9783 [0.9179, 1.1312] | inconclusive |
| budget-crossing | 1 | 4.434 | 4.423 | 1.0116 [0.9940, 1.0694] | below |
| budget-crossing | 2 | 2.840 | 2.542 | 1.1075 [1.0681, 1.1600] | inconclusive |
| budget-crossing | 4 | 3.910 | 3.713 | 0.9997 [0.9301, 1.0968] | below |

The 1.10 improvement column tests whether the candidate is at least 10% faster than the old Forge SDK on this workload; it does not claim 1.10x Rust performance. Raw samples, artifact hashes, compiler commands, and this runner source are retained in the JSON.

Rust 1.53.0 uses the pinned fixture control and is used as a same-input correctness/measurement control, not as the ratio denominator in this report.

## Decision

The candidate removes per-queue mutex acquisitions from scheduler-internal queue operations, which already run while the scheduler mutex is held. The public queue APIs retain their own locking. Runtime CTest passed all 3 suites, and the paired comparison passed all 27 direct correctness checks plus 288 prewarm and 288 measured runs.

Do not promote this candidate yet. The 4-worker scheduler-heavy median improved 18.9%, but its 95% interval lower bound was only 5.6%; mixed-CPU at 4 workers regressed 2.2% at the median, and the remaining worker/workload combinations were mixed. The observed gain is workload-specific and does not establish a reliable general improvement. The temporary runtime patch was kept out of the production runtime repository.
