# Deferred native queue-depth accounting

This is a **local forge-runtime candidate** based on
`dcbb1929b17c2f1d11fd367ecf80c7c87c58a274`. The compiler's immutable runtime pin
is unchanged; clean default dependency fetching does not include this patch.
The complete local project is tested with an explicit runtime source override.
A tested published revision still needs to be integrated before a clean release
can contain the change. The standard library retains the separately archived
[local HTTP startup fix](http-startup-2026-10-15.md), identical across variants.

On the measured Linux host, a native producer that checks depth before each job
completes its finite workload **1.08x / 1.26x / 1.33x faster with 2 / 4 / 8 workers**.
The single-worker job case has no established change. Tail latency and isolated
single-queue query cost have tradeoffs below; this is not an HTTP or general
scheduler-capacity result.

## Observable states and proof

Previously `fr_sched_pool_queued` took the scheduler mutex, then every native
queue mutex to sum their counts on every query. Every publication, local pop and
steal already holds the scheduler mutex. No additional queue mutation path was
found in the complete `scheduler.c`/`work_queue.c` census.

The candidate keeps the existing pending-work completion count and adds one
private signed execution ledger. A value of −1 means unobserved. A first
multi-worker query locks the scheduler, takes the original protected queue
census, and initializes `executing = pending − queued`. Subsequent queries read
`pending − executing` under the same mutex, without scanning the queues.
Single-worker pools keep direct one-queue counting and never activate the ledger.

Once tracking is active:

| Transition under scheduler mutex | Pending | Executing ledger | Queue depth |
|---|---:|---:|---:|
| Successful publication | +1 | unchanged | +1 |
| Local pop or steal claims callback | unchanged | +1 | −1 |
| Callback returns and commits completion | −1 | −1 | unchanged |

Failed publication changes none of these counts. A steal removes one node from
the victim queue and claims it; it is not an extra queued copy. Nested same-pool
indexed callbacks retain their existing synchronous inline path, without new
queue publication. Wakeups, queue order, coroutine reductions/yields and the
`native_pending == 0` completion predicate remain unchanged.

The first census accounts for callbacks already claimed, even while their user
code is running. Claim and activation are serialized by the same mutex:
activation before claim lets the later claim increment the ledger; activation
after claim includes that callback in `pending − queued`. Completion must recheck
whether tracking became active **after** the user callback returns. Capturing
only the pre-callback state would miss an observation during the callback.
The tests exercise both orders and callback-originated first observation.

Stop retains queued work and ledger state; returning callbacks still commit
completion before their workers exit. A serialized restart drains the retained
backlog. The snapshot excludes claimed callbacks but does not reserve capacity
for a later submit: another producer can publish between those separate calls.
This change retains the existing signed-int pending-count domain; it does not
repair very-large-count overflow or add a cancellation/lifecycle contract.

No per-job allocation, public function signature, queue-node layout or lock is
added. Unqueried multi-worker pools still execute two predictable ledger-state
checks; they do not perform ledger updates. Once queried, tracking remains active
for that pool. On this x86_64 ABI the new int occupies former padding: scheduler
size remains 120 bytes, and the pending/worker-pointer offsets remain 56/64.
The layout probe and both runtime archives' exact source rebuilds are retained.

This applies the [counting and ownership principles](../../../forge/docs/design-principles.md):
queued, claimed and complete are distinct; an accounting shortcut must observe
the actual ownership transition, including work already in flight.

## Native measurement protocol

AMD BC-250, Linux 6.8.0-139-generic x86_64, GCC 13.3.0 Release, LTO off.
The same public C fixture is linked separately against the frozen before/after
runtime archives. Compiler SHA-256 remains
`b1165dd18d1367ee249e23f1a994120dfb9f525b2c8c5525042af542666f9c65`.
No generated C prototype or compiler/runtime mixture is used for the main result.

The benchmark supplies deterministic integer work through actual native-pool
callbacks and checks each result after joining. A separate Python affine-jump
oracle checks the unsigned LCG checksum independently of the C callback loop.
The producer checks depth before every job in `queried` mode (high-water 2,048),
and does no depth queries during jobs in `control` mode. Each finite batch has
20,000 jobs; short jobs have 16 LCG steps, and heavier jobs have 1,024.

Timing includes producer submission/backpressure, callback completion and worker
stop/join. Pool creation, a 64-job warmup, post-run validation and percentile
sorting are excluded. Per-job completion latency starts immediately before
submit, after any admission wait. It includes queueing and callback computation,
not time waiting for admission. Per-worker completion counts are retained.

The main comparison has 20 rows × 24 alternating AB/BA pairs, plus one excluded
warmup pair per row. All 960 measured invocations pass their checksum/error
checks. The native-job rows account for **9,600,000 measured completed jobs**;
query-only rows account for 96,000,000 depth observations. Those query-only pools
have configured queues but **no running worker threads**. Source/binary hashes,
commands, CPU/wall time, per-job percentiles and all samples are retained.
Intervals are row-wise 10,000-resample paired geometric-mean bootstrap intervals,
not simultaneous confidence or an equivalence test over all workloads.

## Results and tradeoffs

| Native workload | Baseline median wall | Candidate median wall | Paired speedup | 95% interval |
|---|---:|---:|---:|---:|
| 1 workers, 16 steps/job | 23.89ms | 22.70ms | 1.034x | 0.957–1.127x |
| 2 workers, 16 steps/job | 31.98ms | 30.29ms | 1.081x | 1.037–1.131x |
| 4 workers, 16 steps/job | 58.91ms | 49.73ms | 1.260x | 1.122–1.450x |
| 8 workers, 16 steps/job | 127.21ms | 103.93ms | 1.331x | 1.188–1.632x |
| 4 workers, 1024 steps/job | 67.88ms | 63.27ms | 1.118x | 1.044–1.204x |

These are geometric means of paired ratios, not ratios of marginal medians.
For the short 4/8-worker cases, median process CPU is 159.36 → 134.46ms and
387.70 → 349.59ms. The speedup belongs to this queue-observing finite producer
workload, not all work submitted to the pool.

The no-query controls' speedup intervals all include 1; the heavier 4-worker
control is 0.945x [0.852, 1.049]. That does **not** establish zero overhead or
exclude a regression. A separate diagnostic calls depth once and then submits
all jobs without further queries, leaving the ledger active:

| Workers | Single-observation paired speedup | 95% interval |
|---|---:|---:|
| 2 | 1.032x | 0.981–1.086x |
| 4 | 0.976x | 0.806–1.189x |
| 8 | 1.086x | 0.983–1.305x |

None of those sparse-observation intervals establishes a change. Its explicit
`FORGE_DEPTH_SINGLE_QUERY` fixture variant is separately built/labeled; default
builds of the final source reproduce the measured main binary byte for byte.

After first-query setup, isolated empty/fixed-backlog query speedups are about
3.05x for 2 queues, 5.04–5.32x for 4, 14.15–14.62x for 12 and 64.52–67.10x for 64.
Those are getter timings on non-running pools. The single-queue fixed-backlog
getter is **0.933x [0.889, 0.978]**: its extra dispatch has a measured microbenchmark
cost despite the job-level single-worker comparison being inconclusive. This
cost is retained rather than represented as a universal improvement.

Faster completed-work throughput does not imply lower tail latency. The following
are medians of per-batch p99 completion latencies, with paired p99 speedup
intervals retained in `latency-summary.json`:

| Queried workload | Baseline p99 | Candidate p99 | Paired p99 speedup 95% interval |
|---|---:|---:|---:|
| 2 workers, 16 steps/job | 709.65µs | 1187.31µs | 0.443–1.187x |
| 4 workers, 16 steps/job | 78.75µs | 110.86µs | 0.451–1.153x |
| 8 workers, 16 steps/job | 52.13µs | 52.85µs | 0.614–1.038x |
| 4 workers, 1024 steps/job | 12950.32µs | 11733.86µs | 1.026–1.448x |

The short-job tails trend worse in several cases; their intervals include 1.
Heavier 4-worker p99 improves in this comparison. No general tail-latency claim
is made. All workers complete measured work in every native batch; the smallest
8-worker candidate contribution in the queried row is 2,042 of 20,000 jobs.
Median largest-worker shares are 0.291 → 0.300 for 4 short-job workers and
0.13335 → 0.13330 for 8. These finite progress observations do not prove starvation
freedom or sustained fairness. All per-worker counts remain inspectable.

## Affinity and discarded prototypes

The pinned runtime's `fr_thread_pin_cpu` is a no-op on this Linux build because
`thread.c` does not include the header defining `FORGE_OS_LINUX`. This remains
unchanged in the accounting patch. A first preliminary probe accidentally
inherited a one-CPU mask for all workers; that probe and source are retained and
are not the multi-core result above.

The final fixture explicitly gives workers an inherited mask drawn from
`0,2,4,6,8,1,3,5,7,9`, then moves the producer to CPU 10. Every invocation checks
actual `/proc/self/task` thread masks. For up to 8 workers, their CPUs do not
share the producer's physical core. The topology record is retained; other host
work remains, so this is not exclusive CPU isolation. Affinity repair and its
scheduling-policy consequences need a separate evaluated change.

Three earlier source/library/binary variants and complete paired matrices are
retained:

- Eager size_t queue total: faster getters, but short no-query 4-worker jobs
  regress to 0.867x [0.796, 0.927]. Its scheduler grows 120 → 128 bytes. Rejected.
- Eager execution count beside pending: keeps the 120-byte layout, but short
  no-query 8-worker jobs regress to 0.971x [0.949, 0.993]. Rejected.
- Deferred count without a single-worker guard: short queried 1-worker jobs
  regress to 0.880x [0.800, 0.952]. It informed the final direct-count guard.

Layout, write traffic and code layout are plausible contributors to differences;
these comparisons do not isolate a causal explanation for each regression.
The final design was selected using queried/no-query workload evidence, not
merely fewer mutex calls. Prototype controller hashes match their retained
source, and their samples are not pooled into the final confidence intervals.

## Correctness validation and OMO

The new Linux GNU-wrap native-depth regression covers cold queue-node allocation
failure, rejected functions, partial worker creation and work stealing, exact
queued-versus-claimed snapshots, and stop/restart retaining backlog. It activates
the ledger before execution, while callbacks are gated, after stop begins with
callbacks still gated, and from inside the first callback. Four producers and
two observers submit/check 12,000 jobs over three rounds, with exact-once checks
and final zero depth. Exact intermediate assertions use gated quiescent queue
inventories; they do not subtract racy separately sampled producer counters.

The full local project passes **27/27 CTest suites**, including the existing
coroutine reduction/yield, I/O progress and native-completion regressions.
Standalone runtime tests pass **5/5**, also **5/5 with ASan, UBSan and leak
checking**. Fresh self-host stage3/stage4 fixed-point verification passes. The
installed SDK builds and smoke-checks the new benchmark CMake target. Both runtime
archives are rebuilt from retained sources byte for byte; the project's runtime
archive equals the measured candidate and the compiler binary stays unchanged.

ThreadSanitizer could not initialize on this host (`unexpected memory mapping`,
exit 66). It is **not counted as a pass**, and sanitizer testing does not constitute
a proof of all scheduler races or lifetimes.

Three completed OMO reviews and actual exports are retained. The first two audit
the eager prototype and its mutation/locking/test premises; the third proves
lazy activation and completion rechecking. Its missing after-stop first-observation
case was added. The final one-worker bypass is covered separately by the final
matrix/tests. No agent response is treated as a release approval.

The malloc-failure test premise was checked against `work_queue.c`: a fresh queue
has no cached node and its first publication calls malloc. The intended fault is
counted explicitly. Every scheduler-owned native queue mutation occurs under the
scheduler mutex; the standalone internal queue API keeps its own mutex protocol.

## Verified pre-existing lifecycle findings

The eager-prototype OMO audit also raised issues outside depth accounting. The
retained `lifecycle_probe.c` runs against **both frozen libraries**:

- Stop with an internal `fr_sched_pool_spawn` wrapper queued, then destroy:
  LeakSanitizer reports the same 16-byte context leak in both variants.
- Start while stop is joining a gated callback: both variants remain stuck and
  the owned test process is killed after its two-second timeout.

Those are unresolved existing lifecycle defects, not passes, and the runtime
README now states them. No cancellation, concurrent-lifecycle or graceful-shutdown
claim accompanies this candidate. Fixing these ownership/progress issues and the
inactive affinity helper remains follow-up work toward the active project goal.

## Reproduction and artifacts

The benchmark repository contains `benchmark/native_depth_bench.c` and
`benchmark/native_depth_compare.py`; the latter accepts frozen `--baseline`,
`--candidate` executables and an unused `--output` directory. Compile the same
fixture twice against the before/after archives with GCC `-std=c11 -O3 -pthread`,
then run the controller with `--pairs 24`. The explicit Linux CPU map requires
CPUs 0–10; adapt fixture/controller together on another host. See the archive's
`REPRODUCE.md` for exact commands and sparse-activation diagnostics.

The archive includes before/after source and library snapshots, runtime/benchmark
patches, all main/sparse/prototype samples, workload/oracle source, flags, layout
and affinity records, sanitizer/regression/self-host logs, lifecycle counterexamples,
and all three completed OMO exports. `manifest.json` covers retained files. Both
patches apply to their recorded baseline and reconstruct the changed files exactly.
No dependency pin is updated to an unpublished local revision.

- [Raw sources, measurements and OMO records](native-depth-2026-10-15.raw.tar.gz)
- [Archive SHA-256](native-depth-2026-10-15.sha256)
