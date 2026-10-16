# Skip empty private queues without duplicating scheduler state

This local runtime candidate is incremental to the
[CPU-affinity candidate](cpu-affinity-2026-10-15.md), already containing the
native-depth and lifecycle fixes. Runtime base remains
`dcbb1929b17c2f1d11fd367ecf80c7c87c58a274`; compiler/stdlib dependency pins are
unchanged. Tests use explicit local runtime and stdlib source overrides. Default
clean dependency fetches do not contain these candidate changes.

The change avoids empty queue primitives while preserving the existing scheduler
mutex, nonempty queue locks, queue selection order, callback ownership and yield
boundaries. It also fixes a reproduced completion wake missing after failed
coroutine publication. It adds no scheduler field, queue metadata or per-job
allocation. Gains and remaining costs below belong to finite measured workloads.

## The protected inventory already exists

Every native claim previously tried the worker's coroutine queue and then other
coroutine queues, even when none contained a coroutine. Each primitive acquired
its queue mutex. With 12 workers and 2,000 native jobs, diagnostic wrapping counts
24,000 coroutine queue calls, both with no coroutines and beside 32 parked
receivers. A live parked coroutine contributes to `active_coros` but is not queued.

The queue objects are private inside the opaque scheduler. All their publication,
claim and observation paths hold `sched->lock`; initialization is unpublished and
terminal destruction follows stop/join and caller quiescence. While that owner
mutex is held, a queue-head test stays valid until the immediately following
pop/steal. Empty primitives have no queue mutation or user callback to preserve.
Nonempty primitives still acquire their original queue mutexes. Standalone/shared
queue APIs are unchanged, and no unsynchronized peek API is exported.

The worker skips empty own/victim queues and preserves own-FIFO followed by
ascending-victim LIFO selection. `active_coros == 0` can skip the entire coroutine
search: every queued coroutine is RUNNING, and active includes executing or any
nonterminal status. Attached spawn and process registration refresh that count
before first enqueue; wake paths retain an already active waiting coroutine.
Existing callback execution remains outside the owner lock. Reduction budgets,
I/O readiness flags, mailbox rechecks, native-depth accounting, stop/restart
backlog and terminal cleanup are unchanged.

Debug builds independently sum private queue inventories under the owner lock
and check coroutine inventory against active counts and total inventory against
`runnable`. These checks compile out in Release. They do not imply arbitrary
concurrent destruction is safe or authorize raw peeks on standalone queues.
Adding an independent queue mutator would require revisiting this shortcut.

The final diagnostic has zero coroutine queue calls in the native/parked cases,
2,000 successful calls for 2,000 coroutine jobs, and 1,000 for a half-coroutine
mixed batch. Diagnostic wrappers are separate executables; their overhead is not
part of the throughput comparison.

## An error can complete the last task

A failed coroutine queue push already marked the coroutine ERROR and updated
active counts. If an external sender woke the last WAITING_RECV coroutine while
`fr_scheduler_run` waited on its completion condition, push failure retired the
last active task but issued no completion signal. No worker had received work
that would later signal it. The controller could remain asleep.

The failure path now calls the existing completion notifier under `sched->lock`
after updating counts. Native or other active work still keeps the predicate
false and its normal completion path supplies the eventual wake.

The new regression proves the sole worker has committed WAITING_RECV and the
controller entered its actual condition wait. Sending acquires the same owner
mutex after those waits release it. GNU wrapping injects push failure and observes
the controller's exact condition signal. The baseline fails the missing-signal
assertion immediately, rather than relying on a timeout. The fixed library signals
and joins the controller, without executing the rejected resumption. Spurious wakeups
are not a substitute for publishing the predicate transition.

Mailbox acceptance still means ownership transferred to the mailbox; it does not
promise callback execution. Its retained message and coroutine storage follow
their existing terminal cleanup rules. This is not a new cancellation-result API.

## Compare the rejected alternatives too

An initial guard using only `active_coros == 0` removed native-only scans but
retained all 24,000 calls beside parked receivers. An eight-pair 12-worker probe
found gains for native/mixed work and little evidence of a blocked-receiver gain.

A second prototype maintained an exact queued-coroutine counter on successful
enqueue and claim. Its 32-row, 24-pair matrix improved native/mixed batches but
showed heavy coroutine-control ratios of **0.866x** at eight workers and **0.845x**
at twelve. Its private scheduler grew from 120 to 128 bytes, with glibc usable
allocation size 136 instead of 120, and shifted existing offsets. Store cost and
layout effects were not causally separated. The prototype was not retained.

The selected private-head candidate retains the baseline's 120-byte scheduler,
120-byte usable allocation and pending/worker offsets 56/64. It reuses existing
ownership instead of introducing another readiness ledger. Full inner-lock
elision was deferred: it needs a wider interface/callgraph change and is not
required for this empty-operation optimization.

A final local-head-first ordering experiment targeted the small single-worker
coroutine cost. Against the selected candidate, its coroutine ratio was 0.996x
[0.966, 1.029] over 24 pairs, with no established gain. It was not selected. All
prototype sources, libraries, samples and review records remain available; no
series is pooled or silently dropped.

## Main dispatch measurements

The selected candidate is compared with the immediately preceding affinity-aware
runtime, using the same C fixture and GCC 13.3.0 `-O3 -std=c11 -Wall -Wextra`, no
LTO. All counts are explicit and equal between variants. Workers 1/4/8/12 inherit
verified masks selected from logical CPUs 0–11; producer and workers share those
CPUs. One gated warmup callback runs on every worker before timed release.

Each invocation computes 20,000 unsigned LCG results with 16 or 1024 steps.
Native-only, native beside 32 parked receivers, yielded-coroutine-only and
half-coroutine/half-native modes are distinct comparisons. Every item executes
exactly once and its value is checked; Python independently checks the checksum
using affine exponentiation. All live thread masks and per-worker job totals
are verified. Corpus inputs and source are identical within each comparison.

There are 32 rows × 24 alternating AB/BA pairs, or **1,536 measured invocations**
and **30,720,000 jobs**. The first pair is BA; each row has a separate excluded
warmup pair that remains in the raw data. The earlier eight-pair private-head
probe is retained separately and is not pooled into the main matrix.

Kernel time includes gate release, native publication, callbacks and stop/join.
Coroutine publication is outside it. Additional total time includes lifecycle,
setup and parked-receiver cleanup; item setup, gate primitive setup/teardown,
result verification and sorting are outside. Modes are not cross-ranked as
though they timed identical publication work. Latency is sampled inside each
callback after its result, before bookkeeping; coroutine items share the timed
release timestamp, native items use their submission timestamps.

Numbers are paired geometric means of baseline/candidate time; **below 1 means
slower**. Brackets are individual 95% bootstrap sampling intervals (5,000 paired
resamples). They are descriptive estimates without multiplicity correction,
protection against shared-host drift, or a formal non-inferiority guarantee.
The variants were selected after experiments; intervals are not calibrated
post-selection evidence against all systematic bias. Four-worker rows in this
run have particularly wide intervals. All samples remain, without outlier removal.

| Workers | LCG steps | Native ratio [interval] | Parked + native | Coroutine control | Half mixed |
|---:|---:|---:|---:|---:|---:|
| 1 | 16 | 1.043 [1.004, 1.080] | 1.033 [1.006, 1.062] | 0.976 [0.955, 0.994] | 1.026 [0.995, 1.051] |
| 1 | 1024 | 1.005 [0.997, 1.012] | 1.012 [1.001, 1.025] | 0.999 [0.990, 1.008] | 1.003 [0.995, 1.010] |
| 4 | 16 | 1.190 [0.903, 1.611] | 1.052 [0.754, 1.395] | 1.139 [0.843, 1.551] | 1.258 [1.016, 1.596] |
| 4 | 1024 | 1.411 [1.301, 1.539] | 1.509 [1.369, 1.674] | 1.059 [0.950, 1.181] | 1.199 [1.099, 1.320] |
| 8 | 16 | 1.430 [1.366, 1.499] | 1.320 [1.194, 1.428] | 0.989 [0.944, 1.038] | 1.479 [1.351, 1.651] |
| 8 | 1024 | 1.370 [1.262, 1.470] | 1.563 [1.406, 1.722] | 1.085 [0.993, 1.210] | 1.376 [1.302, 1.452] |
| 12 | 16 | 1.698 [1.538, 1.922] | 1.788 [1.668, 1.913] | 1.042 [1.009, 1.076] | 1.414 [1.376, 1.454] |
| 12 | 1024 | 1.744 [1.651, 1.847] | 1.845 [1.725, 1.967] | 1.136 [1.043, 1.254] | 1.444 [1.377, 1.518] |

At 12 workers the observed native/parked ratios are about 1.70–1.85x, and mixed
ratios about 1.41–1.44x. These are kernel wall-time ranges, not claims that every
p99 interval establishes improvement. The large eight/twelve-worker heavy coroutine regressions
of the extra-counter prototype are not repeated in the selected matrix.
There is still a cost: the one-worker tiny coroutine control is 0.976x
[0.955, 0.994], about 2.5% more kernel time. Its p99 ratio is 0.978x
[0.961, 0.994]. This is retained as an observed tradeoff, not rounded into
"no regression". No native or mixed wall-time row has an interval wholly below
1; that observation is not a non-inferiority proof.

Selected p99 observations illustrate the latency scope:

| Workers | Steps | Mode | Baseline median p99 (ms) | Candidate median p99 (ms) | Paired p99 ratio [interval] |
|---:|---:|---|---:|---:|---:|
| 1 | 16 | coro | 2.246 | 2.283 | 0.978 [0.961, 0.994] |
| 12 | 16 | native | 0.068 | 0.048 | 1.177 [0.758, 1.531] |
| 12 | 16 | blocked | 0.106 | 0.051 | 1.759 [1.450, 2.053] |
| 12 | 16 | coro | 20.965 | 20.980 | 1.041 [1.008, 1.076] |
| 12 | 16 | mixed | 11.613 | 11.030 | 1.043 [1.004, 1.083] |
| 12 | 1024 | native | 0.124 | 0.083 | 1.595 [1.324, 2.002] |
| 12 | 1024 | blocked | 0.137 | 0.076 | 1.391 [1.082, 1.683] |
| 12 | 1024 | coro | 32.468 | 30.047 | 1.142 [1.046, 1.266] |
| 12 | 1024 | mixed | 19.154 | 17.753 | 1.065 [0.998, 1.147] |

Ratios of medians are not paired geometric statistics. Raw files retain all
percentiles, CPU time, setup-inclusive time and worker distributions. Removing
empty primitives does not prove bounded waiting, scheduler fairness or sustained
service capacity. Native submissions in these fixtures have no in-flight bound.

## Direct check against the pre-affinity baseline

A separate matrix uses the unchanged all-worker-gated affinity fixture from the
preceding study. Its baseline is the frozen **pre-affinity** runtime (already
including native-depth/lifecycle fixes), not the immediately preceding dispatch
baseline. The candidate combines affinity-aware defaults and private-head dispatch.
The exact same fixture, inputs, flags and masks are used on each side. Four/full
12-CPU masks, auto/explicit counts and both weights make 8 rows × 24 pairs:
**384 measured invocations**, **7,680,000 jobs**. These samples are not pooled with
the dispatch matrix and no product of historical speedup ratios is used.

| Allowed CPUs | Requested count | Steps | Kernel ratio [interval] | p99 ratio [interval] |
|---|---:|---:|---:|---:|
| {4,6,8,10} | 0 | 16 | 3.098 [2.288, 4.019] | 0.975 [0.494, 1.743] |
| {4,6,8,10} | 4 | 16 | 1.518 [1.165, 2.014] | 0.898 [0.517, 1.516] |
| {4,6,8,10} | 0 | 1024 | 2.738 [2.392, 3.086] | 0.054 [0.026, 0.120] |
| {4,6,8,10} | 4 | 1024 | 1.311 [1.218, 1.410] | 1.310 [0.880, 1.982] |
| {0..11} | 0 | 16 | 1.784 [1.671, 1.896] | 2.044 [1.297, 3.447] |
| {0..11} | 12 | 16 | 1.682 [1.599, 1.770] | 1.505 [1.345, 1.664] |
| {0..11} | 0 | 1024 | 1.770 [1.623, 1.908] | 1.994 [1.351, 3.364] |
| {0..11} | 12 | 1024 | 1.782 [1.698, 1.874] | 1.236 [0.814, 1.657] |

In this direct workload the full-mask auto kernel ratios are about 1.77–1.78x,
so the prior full-mask tiny slowdown is recovered in the integrated candidate's
measured comparison. This is a scoped before/after result, not a universal
absence-of-cost claim. Both full-mask variants use 12 workers.
Including the explicit-count full-mask controls gives a 1.68–1.78x range. This
anchor measures the combined candidate; it does not isolate affinity's contribution.

The four-CPU auto heavy row still has a **0.054x p99 ratio** despite a 2.738x batch
ratio: the baseline starts 12 workers and the integrated candidate starts four.
The explicit-four heavy control, with equal worker counts, improves kernel and
p99 by about 1.31x. Dispatch improvement therefore does not establish that the
separate auto-sizing/unbounded-backlog latency tradeoff is cured. Backpressure
and workload-specific latency policy remain separate design tasks. Neither
matrix measures HTTP throughput, CPU quotas, database/TLS work or application
capacity.

## Verification and review boundaries

Full project CTest passes **31/31** with both local component overrides. Standalone
runtime Release and ASan/UBSan/leak runs pass **8/8**. Combined stdlib/runtime
ASan/UBSan/leak checks pass **17/17**. New transition cases exercise:

- Already-created work attached and additional work spawned from a native callback.
- Queued coroutines retained through a gated stop and restart without duplicate work.
- First worker creation failure forcing the second worker to steal the only coroutine.
- Failed initial enqueue, failed reduction-boundary requeue and later successful work.
- A receiver woken while the sole worker executes a native callback.
- Last-receiver external wake publication failure and controller completion.

Existing scheduler tests cover readiness during an executing callback, mailbox
wake-before-commit, reduction budgets and mixed native/I/O completion. Debug
inventory checks exercise the independent state invariant throughout these runs.
The original missing-wake probe fails on the baseline and passes on the frozen
candidate. The live project runtime archive matches the measured candidate.

Self-host stage3/stage4 C fixed-point verification passes, with hash
`e1516621f8d9c3dbc0a7fe07a141936564a39b757c4e2325dae3df59925392b5`.
The linked stage0 compiler remains
`a7781418b399a91c5db14e77d0c1ee1242efd19fc41c3514b12d7f6bb176c6fa`.
The installed-SDK CMake dispatch fixture builds successfully.

The current ThreadSanitizer target builds but exits 66 before testing with
`FATAL: ThreadSanitizer: unexpected memory mapping`. It is unavailable evidence,
not a passing race check. Executed validation is Linux/GCC/glibc only; other OSes,
real allocation exhaustion and general scheduler lifetime safety are not certified.
The injected push rejection models a valid publication failure; it is not a
measurement of allocator exhaustion on this host.

Four OMO/Sisyphus reviews completed with `opencode/mimo-v2.6-flash-free`: design,
the rejected counter implementation, the selected private-head source and a
measurement/anchor excerpt. Actual requests, answers and finish records are
retained; completion is not presented as four approvals of the final code.

Findings were resolved against source and executable evidence. The proposed
`active_coros >= runnable` assertion was wrong because native jobs contribute to
`runnable`; the independent queue-inventory checks use the correct inequalities.
The counter review speculated that steal deposited a node into the thief queue;
the actual primitive removes and returns it, ignoring the thief argument. Existing
commit ordering, `await_ready`, mailbox rechecks, native dispatch and retained stop
counts resolve its other conditional concerns. Its last-task publication-failure
concern led to the concrete external-send reproducer and completion fix above.

The selected-source review required confirming initialization before enqueue.
Attached spawn and process registration do refresh active counts first; the
late-attachment regression exercises the detached-then-registered case. The
measurement review prompted explicit wall/p99 and combined-anchor qualifications.
It saw only the 1/12-worker excerpt and anchor: its request for missing 4/8-worker
rows is covered by the complete report table and all 32 raw/controller-verified
rows, not counted as model review of those omitted rows. Model findings neither
replace the owner-lock proof nor certify concurrency safety.

The source overrides use the coordinated runtime/stdlib candidates from the
affinity study. Its older-runtime fallback does not approve arbitrary mixed SDKs
or an older stdlib that still issues implicit pin calls against the newly active
runtime helper. No dependency pin is changed to an unpublished revision.

## Retained reproduction evidence

The archive includes exact before/after and rejected source snapshots, frozen
libraries and executables, deterministic failure probes, all raw samples and
completed OMO requests/responses. Incremental and cumulative patches identify
the local-candidate and immutable-runtime boundaries. `REPRODUCE.md` gives exact
normal/sanitizer/project/benchmark commands; `manifest.json` hashes every retained
file. Source reconstruction and binary comparisons are recorded separately from
the functional test claims.
All six runtime archives, five dispatch executables and two anchor executables
reconstruct byte for byte from their retained sources. Controller hashes and an
independent 54-case affine-versus-loop oracle check also match.

The [design principles](../../../forge/docs/design-principles.md) now state both lessons: use an
established ownership interval before duplicating state, and notify completion
when failed publication retires the last task.

- [Raw source, samples and reviews](scheduler-dispatch-2026-10-15.raw.tar.gz)
- [Archive SHA-256](scheduler-dispatch-2026-10-15.sha256)
