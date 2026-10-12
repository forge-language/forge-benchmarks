# Complete-lifecycle coroutine comparison

Forge coroutines versus Tokio 1.53.0, measured from observer/runtime creation through spawning, all task completion and runtime shutdown. Every task ID appears exactly once and every final value matches independent Python modular exponentiation. Printing and argument parsing are outside timing.

| Case | Physical workers | Forge median ms | Tokio median ms | Throughput ratio (95% interval) | 1.10 target |
| --- | ---: | ---: | ---: | --- | --- |
| scheduler-heavy | 1 | 4.676 | 30.378 | 6.5734 [6.2807, 6.8938] | supported for this configuration |
| scheduler-heavy | 2 | 6.695 | 23.955 | 4.5695 [2.5073, 5.3483] | supported for this configuration |
| scheduler-heavy | 4 | 11.420 | 29.498 | 2.5292 [2.2412, 3.3656] | supported for this configuration |
| mixed-cpu | 1 | 250.231 | 268.886 | 1.0747 [1.0709, 1.0785] | below target |
| mixed-cpu | 2 | 137.529 | 148.534 | 1.1058 [0.9887, 1.1799] | inconclusive |
| mixed-cpu | 4 | 94.130 | 94.613 | 0.9844 [0.8991, 1.0687] | below target |
| budget-crossing | 1 | 6.582 | 56.236 | 8.6445 [8.0754, 8.7256] | supported for this configuration |
| budget-crossing | 2 | 4.810 | 37.619 | 8.5397 [7.4116, 9.8032] | supported for this configuration |
| budget-crossing | 4 | 5.164 | 46.150 | 8.6452 [6.4813, 9.7679] | supported for this configuration |

Ratio = Tokio elapsed / Forge elapsed for the same logical work. The ratio column is the median of within-pair ratios, which can differ from dividing the displayed independent medians. Each configuration has 16 order-balanced paired repetitions with randomized dynamic seeds and checked same-input prewarming. No checksum failure or timing outlier is excluded.

Both runtimes use 1/2/4 OS worker threads pinned to the same distinct physical cores. Both spawning drivers run on the main thread. Forge queues tasks in generated main_init before scheduler_run starts its workers; Tokio starts workers during runtime creation, before block_on spawns tasks. The exact generated-C adapter changes only worker count and lifecycle timer boundaries; original/adapted C and hashes are preserved. C provides config, timer and observer storage only; recurrence and logical yields live in FG/Rust.

Explicit yields are not equal context switches: Forge can continue within its reduction budget before requeue, while Tokio yield_now has its own cooperative scheduling and [non-guarantees](https://docs.rs/tokio/1.53.0/tokio/task/fn.yield_now.html). Worker configuration uses the [Tokio builder](https://docs.rs/tokio/1.53.0/tokio/runtime/struct.Builder.html). These measure supported scheduler policies and their complete lifecycle, not equivalent dispatch counts or a language-wide performance guarantee.

The scheduler-heavy case has 4,000 tasks × 128 yield rounds × 1 recurrence step. Mixed CPU has 4,000 tasks × 64 yield rounds × 256 steps. Budget crossing has 256 tasks × 4,096 yield rounds × 1 step, exceeding the observed Forge reduction budget of 2,000; the first two cases fit within that budget. Integer products remain bounded below signed 64-bit overflow. Results do not cover mailbox throughput, HTTP, I/O readiness or other machines. Shared-host services/frequency and runtime task-allocation differences remain relevant. RSS is a whole-process diagnostic, potentially including the forked Python runner footprint.

Raw samples, source/adapter/lock hashes and flags: [coroutine-inline-yield-2026-10-12.json](coroutine-inline-yield-2026-10-12.json).


Validated SDK input prefix: `/home/helloworld0822/coding/forge/build-inline-yield-nolto`. Actual compiler/archive/header hashes identify the measured inputs; sibling source observations can postdate their build.

Reproduce with that validated SDK and fresh paths:

```sh
python3 benchmark/coroutine_compare.py --sdk /home/helloworld0822/coding/forge/build-inline-yield-nolto --build-dir build-coroutine-inline-yield-20261012-reproduction --output docs/coroutine-inline-yield-2026-10-12-reproduction.json
```

Original and adapted C remain in the immutable local `/home/helloworld0822/coding/forge-benchmarks/build-coroutine-inline-yield-20261012/snapshot`; the runner regenerates them and validates exact adapter anchors. Original SHA256: `92a910e45e78601625612eeeb72a66352e87b01370e052751acfffa14a402ba0`. Adapted SHA256: `a2a2783fddbfecfa82e41f969865addb6066a6049391ebf9a38584f52c867d4e`.

The raw report retains the executed measurement-runner source/hash separately from later documentation edits.
