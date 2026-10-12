# Complete-lifecycle coroutine comparison

Forge coroutines versus Tokio 1.53.0, measured from observer/runtime creation through spawning, all task completion and runtime shutdown. Every task ID appears exactly once and every final value matches independent Python modular exponentiation. Printing and argument parsing are outside timing.

| Case | Physical workers | Forge median ms | Tokio median ms | Throughput ratio (95% interval) | 1.10 target |
| --- | ---: | ---: | ---: | --- | --- |
| mixed-cpu | 6 | 68.081 | 62.606 | 0.9560 [0.8996, 1.0592] | below target |

Ratio = Tokio elapsed / Forge elapsed for the same logical work. The ratio column is the median of within-pair ratios, which can differ from dividing the displayed independent medians. Each configuration has 32 order-balanced paired repetitions with randomized dynamic seeds and checked same-input prewarming. No checksum failure or timing outlier is excluded.

Both runtimes use the configured worker counts [6] OS worker threads pinned to the same distinct physical cores. Both spawning drivers run on the main thread. Forge queues tasks in generated main_init before scheduler_run starts its workers; Tokio starts workers during runtime creation, before block_on spawns tasks. The exact generated-C adapter changes only worker count and lifecycle timer boundaries; original/adapted C and hashes are preserved. C provides config, timer and observer storage only; recurrence and logical yields live in FG/Rust.

Explicit yields are not equal context switches: Forge can continue within its reduction budget before requeue, while Tokio yield_now has its own cooperative scheduling and [non-guarantees](https://docs.rs/tokio/1.53.0/tokio/task/fn.yield_now.html). Worker configuration uses the [Tokio builder](https://docs.rs/tokio/1.53.0/tokio/runtime/struct.Builder.html). These measure supported scheduler policies and their complete lifecycle, not equivalent dispatch counts or a language-wide performance guarantee.

The scheduler-heavy case has 4,000 tasks × 128 yield rounds × 1 recurrence step. Mixed CPU has 4,000 tasks × 64 yield rounds × 256 steps. Budget crossing has 256 tasks × 4,096 yield rounds × 1 step, exceeding the observed Forge reduction budget of 2,000; the first two cases fit within that budget. Integer products remain bounded below signed 64-bit overflow. Results do not cover mailbox throughput, HTTP, I/O readiness or other machines. Shared-host services/frequency and runtime task-allocation differences remain relevant. RSS is a whole-process diagnostic, potentially including the forked Python runner footprint.

Raw samples, source/adapter/lock hashes and flags: [coroutine-mixed-cpu-6w-32pairs-2026-10-12.json](coroutine-mixed-cpu-6w-32pairs-2026-10-12.json).


Validated SDK input prefix: `/home/helloworld0822/coding/forge/build-inline-yield-nolto`. Actual compiler/archive/header hashes identify the measured inputs; sibling source observations can postdate their build.

Reproduce with that validated SDK and fresh paths:

```sh
python3 benchmark/coroutine_compare.py --sdk /home/helloworld0822/coding/forge/build-inline-yield-nolto --build-dir build-coroutine-workers-3-6-r2-20261012-reproduction --output docs/coroutine-mixed-cpu-6w-32pairs-2026-10-12-reproduction.json --pairs 32 --workers 6 --cases mixed-cpu
```

Original and adapted C remain in the immutable local `/home/helloworld0822/coding/forge-benchmarks/build-coroutine-workers-3-6-r2-20261012/snapshot`; the runner regenerates them and validates exact adapter anchors. Original SHA256: `888e64178b8b70ecdbab08e6db5f9175e3a78b36d8212e81df295b7fa09df675`. Adapted SHA256: `a98accfdb63efd7a6a1da21844b9e3ef0c0b7500ef6d962bf14e146beb8f6902`.

The raw report retains the executed measurement-runner source/hash separately from later documentation edits.
