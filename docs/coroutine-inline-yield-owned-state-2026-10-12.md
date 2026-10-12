# Complete-lifecycle coroutine comparison

Forge coroutines versus Tokio 1.53.0, measured from observer/runtime creation through spawning, all task completion and runtime shutdown. Every task ID appears exactly once and every final value matches independent Python modular exponentiation. Printing and argument parsing are outside timing.

| Case | Physical workers | Forge median ms | Tokio median ms | Throughput ratio (95% interval) | 1.10 target |
| --- | ---: | ---: | ---: | --- | --- |
| scheduler-heavy | 1 | 3.577 | 32.188 | 8.4550 [6.8564, 9.0470] | supported for this configuration |
| scheduler-heavy | 2 | 6.798 | 23.079 | 4.5349 [2.6344, 5.1340] | supported for this configuration |
| scheduler-heavy | 4 | 11.254 | 30.956 | 2.6299 [2.0078, 4.1008] | supported for this configuration |
| mixed-cpu | 1 | 249.175 | 268.750 | 1.0795 [1.0738, 1.0844] | below target |
| mixed-cpu | 2 | 139.127 | 147.512 | 1.0534 [0.9728, 1.1419] | inconclusive |
| mixed-cpu | 4 | 98.221 | 87.606 | 0.9024 [0.8191, 1.0535] | below target |
| budget-crossing | 1 | 4.592 | 58.099 | 12.7891 [11.9293, 13.2332] | supported for this configuration |
| budget-crossing | 2 | 3.417 | 42.551 | 12.4856 [10.7835, 14.0555] | supported for this configuration |
| budget-crossing | 4 | 4.352 | 47.276 | 10.7812 [9.2999, 11.9593] | supported for this configuration |

Ratio = Tokio elapsed / Forge elapsed for the same logical work. The ratio column is the median of within-pair ratios, which can differ from dividing the displayed independent medians. Each configuration has 16 order-balanced paired repetitions with randomized dynamic seeds and checked same-input prewarming. No checksum failure or timing outlier is excluded.

Both runtimes use 1/2/4 OS worker threads pinned to the same distinct physical cores. Both spawning drivers run on the main thread. Forge queues tasks in generated main_init before scheduler_run starts its workers; Tokio starts workers during runtime creation, before block_on spawns tasks. The exact generated-C adapter changes only worker count and lifecycle timer boundaries; original/adapted C and hashes are preserved. C provides config, timer and observer storage only; recurrence and logical yields live in FG/Rust.

Explicit yields are not equal context switches: Forge can continue within its reduction budget before requeue, while Tokio yield_now has its own cooperative scheduling and [non-guarantees](https://docs.rs/tokio/1.53.0/tokio/task/fn.yield_now.html). Worker configuration uses the [Tokio builder](https://docs.rs/tokio/1.53.0/tokio/runtime/struct.Builder.html). These measure supported scheduler policies and their complete lifecycle, not equivalent dispatch counts or a language-wide performance guarantee.

The scheduler-heavy case has 4,000 tasks × 128 yield rounds × 1 recurrence step. Mixed CPU has 4,000 tasks × 64 yield rounds × 256 steps. Budget crossing has 256 tasks × 4,096 yield rounds × 1 step, exceeding the observed Forge reduction budget of 2,000; the first two cases fit within that budget. Integer products remain bounded below signed 64-bit overflow. Results do not cover mailbox throughput, HTTP, I/O readiness or other machines. Shared-host services/frequency and runtime task-allocation differences remain relevant. RSS is a whole-process diagnostic, potentially including the forked Python runner footprint.

Raw samples, source/adapter/lock hashes and flags: [coroutine-inline-yield-owned-state-2026-10-12.json](coroutine-inline-yield-owned-state-2026-10-12.json).


Validated SDK input prefix: `/home/helloworld0822/coding/forge/build-inline-yield-nolto`. Actual compiler/archive/header hashes identify the measured inputs; sibling source observations can postdate their build.

Reproduce with that validated SDK and fresh paths:

```sh
python3 benchmark/coroutine_compare.py --sdk /home/helloworld0822/coding/forge/build-inline-yield-nolto --build-dir build-coroutine-inline-yield-owned-state-20261012-reproduction --output docs/coroutine-inline-yield-owned-state-2026-10-12-reproduction.json
```

Original and adapted C remain in the immutable local `/home/helloworld0822/coding/forge-benchmarks/build-coroutine-inline-yield-owned-state-20261012/snapshot`; the runner regenerates them and validates exact adapter anchors. Original SHA256: `41fc2e1c4ede5e790229ff8a9a25192152caae3dd04242ac8d28d50fa7fc8967`. Adapted SHA256: `96002b78017e6182677700c0ff52bfe072d8e66a7c513fca47e95edc1191e31a`.

The raw report retains the executed measurement-runner source/hash separately from later documentation edits.
