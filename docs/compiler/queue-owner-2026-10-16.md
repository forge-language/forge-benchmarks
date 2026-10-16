# Scheduler queue ownership, 2026-10-16

The scheduler already serializes every private queue operation with its owner
mutex. The candidate omits the redundant inner queue lock under that guard while
retaining synchronized standalone operations. It is kept as a local throughput
candidate with an explicit latency tradeoff, not an all-workloads improvement.

For 12 workers, mixed/16 total-time ratios are 1.119 and 1.128 in two complete
batches; native/1024 ratios are 1.134 and 1.256. **Blocked/1024 p99 worsened**:
at 8 workers, ratios are 0.541 and 0.443 (the latter CI [0.262, 0.706]); at 12,
1.369 and 0.803 (latter CI [0.621, 0.991]). Ratios are baseline/candidate time,
so below 1 means slower candidate. The 8-worker reverse p99 point estimate is
about 2.26 times baseline latency despite faster total completion. This evidence
does not establish a tail-latency, fairness, HTTP or general language speed win.

## Implementation and ownership proof

- `src/work_queue_core.h` shares push/take structure, FIFO local pops, tail
  steals, 256-node caches, empty-output behavior and allocation-failure behavior.
  Locked wrappers pass literal 1; six owned wrappers pass literal 0.
- `src/work_queue_owned.c` is a separate archive object placed last. The private
  declarations are in non-installed `src/work_queue.h`. There is no new public
  header API, queue/scheduler field, readiness counter or per-job allocation.
- Private queue mutexes are still constructed, checked and destroyed. Creation
  and destruction use exclusive/quiescent ownership. Every other head, count,
  cache, publication and claim access holds `sched->lock`.
- Conditional private unlock precedes overflow-node free. Callback execution
  remains outside the scheduler mutex; selection order and budgets are unchanged.
  Standalone/owned calls may not mix unless the same external guard excludes all
  access. These operations are externally serialized, not lock-free queues.

Access-site audit in final `src/scheduler.c`:

| Access | Guard/lifecycle |
| --- | --- |
| Constructor queue initialization, lock check | Unpublished exclusive owner |
| Destroy and native discard | Workers stopped/joined, exclusive lifetime |
| Start scan -> enqueue_coro_locked | scheduler_start holds owner |
| Process attachment -> enqueue | add_process holds owner |
| Attached spawn -> enqueue | owner acquired before process lock |
| Mailbox wake -> enqueue | process lock released, then owner acquired |
| Event resume -> enqueue | callback acquires owner |
| Worker local pop and all victim steals | owner from loop entry through claim |
| Worker coroutine result/requeue | owner reacquired after user invocation |
| Native publication and queued-depth snapshot | public entry acquires owner |
| Debug queue/count inventory | callers in owner-held paths |

## Regression and adversarial evidence

Linux `queue_owner_test.c` records actual mutex lock/unlock/condition-wait events
and independently checks every owned call has the registered owner held by the
calling thread, with no private queue lock held. It exercises 1/4 workers, native
and coroutine allocation failures, 4,000 mixed concurrent-producer jobs, yields
beyond one reduction budget, callback getter re-entry, stop/restart and exact-once
completion. A failed first worker forces both steal functions before producer
concurrency; final assertions also cover destruction.

The registration map depends on Linux constructor order (owner then 2*N private
locks). It fails loudly on drift; it is not an introspection API or a proof for
other event-loop implementations. CTest gives all runtime tests a 30-second limit.

Two retained mutation controls fail for the intended assertions: missing owner
publication fails the actual-held-owner check; substituting locked native push
fails the private-lock count. These mutants are of the initial semantically
equivalent owned implementation, not fresh mutants of the final split source.
Final strengthened test-only assertions passed Release and ASan/UBSan separately.

Observed completed checks:

| Surface | Result |
| --- | --- |
| Final runtime CTest | 10/10 |
| Final compiler + components CTest | 33/33, 64.44 s |
| Runtime + stdlib ASan/UBSan, leak detection | 19/19, 8.10 s |
| Strengthened protocol assertions | Release 1/1, ASan/UBSan 1/1 |
| Current project build and focused regression rerun | build succeeded, 6/6 |
| Self-host fixed point | stage3 C equals stage4 C byte-for-byte |
| Installed SDK benchmark targets | dispatch, lock probe, standalone queue built |
| Direct SDK use | blocked/native/mixed jobs and queue operations completed |
| SDK diagnostic probe | 8 private locks registered, 0 acquired for 4 workers |

The installed runtime archive is byte-identical to the measured candidate.
All 32 diagnostic comparisons retain exact commands and whole-process counts:
one-worker native baseline took 40,003 private locks; candidate took zero.
Registration must equal 2*N and owner acquisitions remain nonzero. These counts
include setup/cleanup/getters, not just the timed kernel. Instrumented timings
are excluded from speed conclusions.

No new TSan pass is claimed. Earlier host initialization failed with exit 66.

## Variants and standalone compatibility

The first implementation placed owned functions in the legacy object; warm
standalone push/pop controls lost roughly 3-6%. A definition-order-only attempt
improved cycles but worsened native drains and was rejected too. Their snapshots
and observations are retained rather than mixed into final results.

The selected split object's legacy `work_queue.c.o` and the complete standalone
fixture executable are byte-identical to baseline under this GCC 13.3 Release
build without LTO. This bounds the linkage/code-placement concern for that
fixture and toolchain; it is not a guarantee for other linkers, compilers, LTO or
programs that pull in the whole scheduler.

| Artifact | SHA256 |
| --- | --- |
| Baseline runtime archive | 398ef73156aad21a8588f83be936ab0d6f652461ae8e98c932b636c4ee08dfdf |
| Final runtime archive / installed SDK archive | 9684329ddf09a4c874c2479df110eabefc24706346941263c53e0e3af1734338 |
| Baseline dispatch | 980c11103aecd4f9e54d9c0c23c8ba5540b4458858d1dab120054fa53ba7d910 |
| Final dispatch | 33696e59f9d6804cc68825968034f0bdbd45aea69b53c6cdd3dfaf45072172e7 |
| Both standalone executables | bdd3d41cba810ebb34faddf4fdc017db2535ac02f59f12358266461f67ce97a5 |
| Unchanged stage0 compiler | f3865084aad4db02f4d48bf8a258736ff8f8cbcbbcba7806c3cba911e186ffb0 |
| Both fixed-point C files | e1516621f8d9c3dbc0a7fe07a141936564a39b757c4e2325dae3df59925392b5 |

## Measurement contract

Each final batch contains all 32 combinations of 1/4/8/12 workers, 16/1024 LCG
steps and native/blocked/coroutine/mixed work. Each row has an excluded warmup
pair and 24 alternating AB/BA measured pairs; the reverse batch swaps initial
measured order. Each invocation completes 20,000 jobs. Blocked adds 32 parked
receivers; mixed splits coroutine/native work equally.

Both batches together retain 3,072 measured invocations and 128 warmups. Re-reading
the raw records verified checksums against the affine oracle, 20,000 total jobs,
per-worker job sums, explicit CPU masks and frozen binary hashes. The producer
shares the worker mask. Pools use the same explicit counts and CPU masks in both
variants. This is a shared 12-CPU AMD BC-250 host, not an idle dedicated machine.

Kernel time includes gate release, native publication, callbacks and stop/join;
it excludes creation and initial coroutine publication. Total time adds scheduler
lifecycle/setup and parked receiver cleanup, while excluding item/gate setup and
result verification/sort. Per-job latency is recorded separately. CPU time, wall
time, total CPU time, p50/p95/p99 and every raw sample remain in JSON.

The following table retains every final row. A/B are separate batches, not pooled
replicates. Each cell is the paired geometric mean baseline/candidate time with
an individual descriptive bootstrap 95% interval. Intervals do not adjust for
multiple comparisons or account for systematic bias, host drift or code placement.
Several total-time intervals cross 1; the four-worker native/16 point estimate
reverses sign between batches, and four-worker blocked/1024 moves from 1.224 to
0.980. No uniform nonregression claim follows.

| Workers | Steps | Mode | Total A | Total B | p99 A | p99 B |
| ---: | ---: | --- | --- | --- | --- | --- |
| 1 | 16 | native | 1.126 [1.057, 1.213] | 1.107 [1.073, 1.142] | 1.168 [1.096, 1.257] | 1.078 [1.038, 1.123] |
| 1 | 16 | blocked | 1.077 [1.038, 1.116] | 1.074 [1.041, 1.106] | 1.092 [1.023, 1.157] | 1.122 [1.073, 1.179] |
| 1 | 16 | coro | 1.037 [1.019, 1.056] | 1.032 [0.999, 1.064] | 1.076 [1.045, 1.109] | 1.101 [1.063, 1.134] |
| 1 | 16 | mixed | 1.077 [1.013, 1.136] | 1.047 [1.008, 1.086] | 1.008 [0.935, 1.075] | 1.094 [1.032, 1.177] |
| 1 | 1024 | native | 1.015 [0.998, 1.031] | 1.015 [1.003, 1.026] | 1.000 [0.983, 1.015] | 1.007 [0.991, 1.023] |
| 1 | 1024 | blocked | 1.012 [1.004, 1.020] | 1.014 [1.006, 1.022] | 0.986 [0.962, 1.010] | 1.002 [0.975, 1.029] |
| 1 | 1024 | coro | 1.009 [0.999, 1.021] | 1.016 [1.008, 1.025] | 1.006 [0.996, 1.016] | 1.012 [1.004, 1.021] |
| 1 | 1024 | mixed | 1.012 [0.997, 1.029] | 1.017 [1.006, 1.028] | 1.002 [0.978, 1.026] | 0.978 [0.950, 1.007] |
| 4 | 16 | native | 0.897 [0.634, 1.245] | 1.075 [0.900, 1.312] | 2.631 [1.400, 5.496] | 1.071 [0.458, 2.529] |
| 4 | 16 | blocked | 1.116 [0.852, 1.425] | 1.101 [0.882, 1.365] | 0.882 [0.385, 1.971] | 1.195 [0.701, 1.980] |
| 4 | 16 | coro | 1.077 [0.966, 1.200] | 1.126 [0.961, 1.360] | 1.051 [0.872, 1.249] | 1.216 [0.960, 1.626] |
| 4 | 16 | mixed | 1.005 [0.774, 1.262] | 1.004 [0.847, 1.161] | 0.924 [0.708, 1.194] | 0.998 [0.898, 1.100] |
| 4 | 1024 | native | 1.128 [1.030, 1.231] | 1.099 [0.973, 1.240] | 0.885 [0.509, 1.530] | 1.031 [0.715, 1.490] |
| 4 | 1024 | blocked | 1.224 [1.095, 1.374] | 0.980 [0.901, 1.069] | 1.081 [0.614, 1.950] | 1.243 [0.791, 2.110] |
| 4 | 1024 | coro | 1.098 [0.998, 1.200] | 1.108 [1.020, 1.201] | 1.089 [0.983, 1.203] | 1.120 [1.026, 1.220] |
| 4 | 1024 | mixed | 1.117 [0.994, 1.247] | 1.136 [1.015, 1.265] | 1.069 [0.923, 1.224] | 1.158 [1.025, 1.307] |
| 8 | 16 | native | 1.108 [1.013, 1.176] | 1.324 [1.152, 1.601] | 1.078 [0.993, 1.219] | 0.673 [0.381, 1.009] |
| 8 | 16 | blocked | 1.158 [1.044, 1.310] | 1.215 [1.169, 1.263] | 0.784 [0.491, 1.054] | 1.052 [1.013, 1.093] |
| 8 | 16 | coro | 1.070 [1.001, 1.141] | 1.036 [0.957, 1.126] | 1.142 [1.086, 1.201] | 1.120 [1.041, 1.203] |
| 8 | 16 | mixed | 1.149 [1.045, 1.232] | 1.138 [1.051, 1.204] | 1.134 [1.006, 1.223] | 1.125 [1.023, 1.202] |
| 8 | 1024 | native | 1.247 [1.093, 1.456] | 1.107 [1.038, 1.184] | 0.596 [0.285, 1.247] | 0.713 [0.454, 1.154] |
| 8 | 1024 | blocked | 1.103 [1.017, 1.200] | 1.241 [1.149, 1.340] | 0.541 [0.289, 1.005] | 0.443 [0.262, 0.706] |
| 8 | 1024 | coro | 1.080 [0.996, 1.170] | 1.264 [1.161, 1.387] | 1.131 [1.047, 1.215] | 1.317 [1.212, 1.442] |
| 8 | 1024 | mixed | 1.110 [1.033, 1.198] | 1.242 [1.161, 1.329] | 1.135 [1.047, 1.233] | 1.225 [1.154, 1.300] |
| 12 | 16 | native | 1.102 [0.982, 1.180] | 1.189 [1.114, 1.326] | 1.155 [1.058, 1.317] | 0.894 [0.624, 1.091] |
| 12 | 16 | blocked | 1.150 [1.116, 1.196] | 1.126 [1.106, 1.146] | 1.070 [0.996, 1.150] | 1.010 [0.865, 1.124] |
| 12 | 16 | coro | 1.052 [0.990, 1.109] | 1.150 [1.060, 1.251] | 1.141 [1.087, 1.189] | 1.220 [1.147, 1.307] |
| 12 | 16 | mixed | 1.119 [1.099, 1.138] | 1.128 [1.104, 1.157] | 1.138 [1.120, 1.154] | 1.148 [1.131, 1.163] |
| 12 | 1024 | native | 1.134 [1.066, 1.205] | 1.256 [1.156, 1.415] | 1.038 [0.800, 1.340] | 0.771 [0.451, 1.182] |
| 12 | 1024 | blocked | 1.064 [0.965, 1.170] | 1.127 [1.059, 1.212] | 1.369 [0.894, 2.352] | 0.803 [0.621, 0.991] |
| 12 | 1024 | coro | 1.199 [1.088, 1.326] | 1.053 [0.966, 1.140] | 1.221 [1.091, 1.352] | 1.033 [0.942, 1.113] |
| 12 | 1024 | mixed | 1.161 [1.087, 1.246] | 1.139 [1.064, 1.239] | 1.149 [1.075, 1.236] | 1.126 [1.058, 1.198] |

## Reproduce and inspect

[Raw archive](queue-owner-2026-10-16.raw.tar.gz),
[checksum](queue-owner-2026-10-16.sha256). The archive retains baseline, initial,
definition-order, final and mutant runtime sources; frozen archives/executables;
all final and initial dispatch samples; standalone controls; exact build recipes;
test logs; OMO requests, completed reviews and source identities. Initial raw
commands used candidate paths before the final split was selected; the explicit
artifact-generations.json maps retained initial names to their original hashes.

After extraction, rebuild snapshots with ordinary CMake and regenerate fixtures
using bench-builds.json or the installed SDK benchmark CMake targets. The complete
final runtime snapshot includes the last strengthened protocol assertions.
The earlier candidate-runtime snapshot differs only in those assertions.
From forge-benchmarks, an installed local candidate can be checked with:

```bash
cmake -S . -B build-owner -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH=/path/to/installed-sdk \
  -DFORGE_RUNTIME_SOURCE_DIR=/path/to/matching/forge-runtime \
  -DFORGE_BUILD_HTTP_BENCHMARKS=OFF
cmake --build build-owner --target dispatch_bench dispatch_lock_probe work_queue_bench -j2
build-owner/bin/dispatch_lock_probe blocked 4 20000 16 1009
build-owner/bin/work_queue_bench 20000
python3 benchmark/dispatch_compare.py --baseline /path/to/dispatch-baseline \
  --candidate /path/to/dispatch-candidate --output /tmp/owner-primary
python3 benchmark/dispatch_compare.py --baseline /path/to/dispatch-baseline \
  --candidate /path/to/dispatch-candidate --output /tmp/owner-reverse --candidate-first
```

The full paired controller requires Linux CPUs 0..11. Adapt both fixtures
consistently on another host rather than silently changing one variant.

## Scope and remaining limits

This stage adds no fallback for total worker-start failure: the previous scheduler
can still report pool availability with no functioning worker. Coroutine enqueue
failure can leave a non-NULL terminal coroutine. The independent self-hosted
generator's scheduler/process construction still lacks stage0's guards. These are
pre-existing, explicitly bounded limits, not regressions claimed fixed here.

Runtime/stdlib pins in forge remain published commits
dcbb1929b17c2f1d11fd367ecf80c7c87c58a274 /
6aa28667b83009a415ab2d7ac13ef6c675af7012. Local verification uses source overrides;
the unpublished candidate was not substituted into dependency pins.

Completed OMO source/final reviews are retained as secondary evidence. The root
audit corrected overly broad review language against the actual full table,
especially the adverse 8-worker blocked p99 interval. Missing LSP tools and
quota-failed discovery workers do not count as verification or review approval.
