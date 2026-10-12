# Complete-lifecycle coroutine comparison

Forge coroutines versus Tokio 1.53.0, measured from observer/runtime creation through spawning, all task completion and runtime shutdown. Every task ID appears exactly once and every final value matches independent Python modular exponentiation. Printing and argument parsing are outside timing.

| Case | Physical workers | Forge median ms | Tokio median ms | Throughput ratio (95% interval) | 1.10 target |
| --- | ---: | ---: | ---: | --- | --- |
| scheduler-heavy | 1 | 3.599 | 30.332 | 8.3481 [8.0873, 8.6236] | supported for this configuration |
| scheduler-heavy | 2 | 5.285 | 23.132 | 4.6961 [2.9962, 5.6887] | supported for this configuration |
| scheduler-heavy | 4 | 10.743 | 30.302 | 2.8328 [2.3452, 3.2740] | supported for this configuration |
| mixed-cpu | 1 | 249.768 | 268.197 | 1.0722 [1.0702, 1.0774] | below target |
| mixed-cpu | 2 | 139.167 | 147.455 | 1.0664 [1.0476, 1.1204] | inconclusive |
| mixed-cpu | 4 | 93.730 | 85.923 | 0.9184 [0.8082, 1.1274] | inconclusive |
| budget-crossing | 1 | 4.426 | 56.396 | 12.7527 [12.0316, 12.9444] | supported for this configuration |
| budget-crossing | 2 | 3.438 | 43.113 | 12.7067 [10.5315, 14.6895] | supported for this configuration |
| budget-crossing | 4 | 4.468 | 49.593 | 11.9510 [7.5528, 15.3874] | supported for this configuration |

Ratio = Tokio elapsed / Forge elapsed for the same logical work. The ratio column is the median of within-pair ratios, which can differ from dividing the displayed independent medians. Each configuration has 16 order-balanced paired repetitions with randomized dynamic seeds and checked same-input prewarming. No checksum failure or timing outlier is excluded.

Both runtimes use 1/2/4 OS worker threads pinned to the same distinct physical cores. Both spawning drivers run on the main thread. Forge queues tasks in generated main_init before scheduler_run starts its workers; Tokio starts workers during runtime creation, before block_on spawns tasks. The exact generated-C adapter changes only worker count and lifecycle timer boundaries; original/adapted C and hashes are preserved. C provides config, timer and observer storage only; recurrence and logical yields live in FG/Rust.

Explicit yields are not equal context switches: Forge can continue within its reduction budget before requeue, while Tokio yield_now has its own cooperative scheduling and [non-guarantees](https://docs.rs/tokio/1.53.0/tokio/task/fn.yield_now.html). Worker configuration uses the [Tokio builder](https://docs.rs/tokio/1.53.0/tokio/runtime/struct.Builder.html). These measure supported scheduler policies and their complete lifecycle, not equivalent dispatch counts or a language-wide performance guarantee.

The scheduler-heavy case has 4,000 tasks × 128 yield rounds × 1 recurrence step. Mixed CPU has 4,000 tasks × 64 yield rounds × 256 steps. Budget crossing has 256 tasks × 4,096 yield rounds × 1 step, exceeding the observed Forge reduction budget of 2,000; the first two cases fit within that budget. Integer products remain bounded below signed 64-bit overflow. Results do not cover mailbox throughput, HTTP, I/O readiness or other machines. Shared-host services/frequency and runtime task-allocation differences remain relevant. RSS is a whole-process diagnostic, potentially including the forked Python runner footprint.

Raw samples, source/adapter/lock hashes and flags: [coroutine-inline-yield-step-defer-2026-10-12.json](coroutine-inline-yield-step-defer-2026-10-12.json).


Validated SDK input prefix: `/home/helloworld0822/coding/forge/build-inline-yield-nolto`. Actual compiler/archive/header hashes identify the measured inputs; sibling source observations can postdate their build.

Reproduce with that validated SDK and fresh paths:

```sh
python3 benchmark/coroutine_compare.py --sdk /home/helloworld0822/coding/forge/build-inline-yield-nolto --build-dir build-coroutine-inline-yield-step-defer-20261012-reproduction --output docs/coroutine-inline-yield-step-defer-2026-10-12-reproduction.json
```

Original and adapted C remain in the immutable local `/home/helloworld0822/coding/forge-benchmarks/build-coroutine-inline-yield-step-defer-20261012/snapshot`; the runner regenerates them and validates exact adapter anchors. Original SHA256: `41fc2e1c4ede5e790229ff8a9a25192152caae3dd04242ac8d28d50fa7fc8967`. Adapted SHA256: `96002b78017e6182677700c0ff52bfe072d8e66a7c513fca47e95edc1191e31a`.

The raw report retains the executed measurement-runner source/hash separately from later documentation edits.
