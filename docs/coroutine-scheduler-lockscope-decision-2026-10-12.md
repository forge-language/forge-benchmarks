# Scheduler queue-dequeue lock-scope experiment

This experiment tests whether moving coroutine queue pop and work-stealing outside the scheduler-wide mutex improves multi-worker scheduling. The base is forge-runtime `0b1e7d4`; the candidate changes only `worker_main` and is preserved as [a patch](coroutine-scheduler-lockscope-candidate.patch). The Forge compiler and stdlib artifacts were identical, and the Rust 1.53 control and harness were unchanged. The runtime archive SHA-256 values are recorded in both raw JSON reports.

The 12-pair screen covered all three coroutine workloads with 1, 2, and 4 workers. A focused 32-pair rerun covered 1 and 4 workers. Each pair used matched seeds, a same-input prewarm, the same CPU set, and exact per-task reference/completion checks. The complete lifecycle timer includes observer/runtime creation, task spawn, completion, shutdown, and result validation. These are scheduler-policy comparisons; Forge reduction-budget continuation and Tokio `yield_now` are not equivalent context switches.

| Case | Workers | Baseline ms | Candidate ms | Candidate speedup (paired median, 95% CI) |
| --- | ---: | ---: | ---: | ---: |
| Scheduler-heavy | 1 | 3.815 | 3.591 | 1.0087× [0.9918, 1.0661] |
| Scheduler-heavy | 4 | 8.953 | 7.918 | 1.2524× [1.0437, 1.4665] |
| Mixed CPU | 1 | 250.753 | 251.536 | 0.9972× [0.9951, 0.9993] |
| Mixed CPU | 4 | 87.659 | 90.077 | 1.0005× [0.9501, 1.0410] |
| Reduction-budget crossing | 1 | 4.488 | 4.434 | 1.0018× [0.9746, 1.0465] |
| Reduction-budget crossing | 4 | 2.969 | 3.068 | 0.9652× [0.8336, 1.1748] |

The scheduler-heavy 4-worker median improved, but its interval includes gains below 10%. The mixed-CPU 4-worker result was effectively parity, and budget-crossing did not show a reliable gain. Therefore the candidate does not establish broad scheduler improvement or move any Rust-relative result to the 1.10 target. Do not promote this patch. It is reverted from the runtime checkout.

The 12-pair screening report covers 1/2/4 workers across all workloads: [Markdown](coroutine-scheduler-lockscope-12pairs-2026-10-12.md), [raw JSON](coroutine-scheduler-lockscope-12pairs-2026-10-12.json). The higher-confidence focused rerun is [Markdown](coroutine-scheduler-lockscope-32pairs-2026-10-12.md), [raw JSON](coroutine-scheduler-lockscope-32pairs-2026-10-12.json). The runner is [`coroutine_codegen_compare.py`](../benchmark/coroutine_codegen_compare.py).
