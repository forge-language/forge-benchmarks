# CPU availability, explicit pinning and automatic pool sizing

This is a local runtime/stdlib candidate, incremental to the
[scheduler lifecycle candidate](scheduler-lifecycle-2026-10-15.md). Immutable
dependency pins remain runtime `dcbb1929b17c2f1d11fd367ecf80c7c87c58a274` and
stdlib `6aa28667b83009a415ab2d7ac13ef6c675af7012`. The default compiler dependency
fetch does not contain these local changes. Source snapshots and cumulative and
incremental patches identify both boundaries.

The candidate makes explicit Linux pinning work and sizes automatic pools from
the caller's allowed CPUs. It preserves the online-CPU observation API and
explicit worker counts. Restricted-mask finite batches improve, with substantial
queue-latency tradeoffs in some cases. Full-mask performance remains a limitation;
this is not a universal throughput or latency improvement.

## Correct the mechanism without imposing placement policy

`thread.c` tested `FORGE_OS_LINUX` without including its defining platform header.
In the recorded CMake baseline its explicit pin function is just a return;
disassembly and an actual-mask probe are retained. The scheduler and HTTP worker
nevertheless called it using `worker_id % online_cpu_count`. Enabling that function
alone would turn those previously ineffective calls into implicit hard pins.
With a sparse inherited mask, ordinals can select entirely different CPU IDs.

The Linux helper now uses the compiler's `__linux__` target macro, has GNU feature
declarations enabled before includes, and rejects negative and out-of-range IDs
before constructing its fixed-size mask. The int64 stdlib binding checks range
before conversion to int: the former `(2^32 + 7)` input reached the helper as 7.
Public signatures stay unchanged. Pinning remains best effort with no returned
status; IDs at or above `CPU_SETSIZE`, OS rejection and unsupported targets do
nothing. Callers requiring proof of placement must query the OS. Explicit pinning
can replace an inherited taskset mask, subject to kernel restrictions.

Both implicit worker pin calls are removed. Workers inherit their starting
thread's mask and the OS selects placement within it. This describes the stock
baseline's effective behavior; custom builds that previously activated the old
Linux branch can observe a placement-policy change. The capability macro below
advertises a counting API, not the existence or success of pinning.

Linux affinity is per thread, and newly created pthreads inherit the creator's
mask. Kernel cpusets can further restrict a requested mask. The implementation
and measurements use these documented rules, rather than assuming CPU numbers
are consecutive. See the primary [affinity specification](https://man7.org/linux/man-pages/man2/sched_getaffinity.2.html),
[pthread creation documentation](https://man7.org/linux/man-pages/man3/pthread_create.3.html)
and [explicit pthread affinity documentation](https://man7.org/linux/man-pages/man3/pthread_setaffinity_np.3.html).

## Keep observations and defaults distinct

| Interface or policy | Candidate behavior |
|---|---|
| `fr_platform_cpu_count`, language `thread_cpu_count()` | Existing online-CPU result retained |
| New `fr_platform_available_cpu_count` | Linux caller-affinity CPU count; online fallback elsewhere or on failure |
| Scheduler auto count, requested count 0 | Available count captured at construction |
| Explicit positive scheduler count | Retained, including deliberate oversubscription |
| HTTP auto pool sizing with matched new runtime | Available count captured where each pool is constructed |
| HTTP auto sizing with matched older runtime | Prior online-count fallback |
| Worker placement | Starting thread's inherited mask, without implicit pinning |

Backend sizing formulas are retained: TLS still has its minimum/multiplier/cap,
and enabled io_uring still multiplies the auto CPU count. An affinity-aware input
does not remove those deliberate oversubscription policies. Hybrid acceptor
defaults remain separate from an explicitly sized native pool.

The new count first queries a stack `cpu_set_t`. EINVAL retries doubling heap
buffers, up to 1 MiB, counting with the size-aware macro and freeing every buffer.
The syscall's error is saved before cleanup. Empty success, other errors,
allocation failure and the bound fall back to the previous online count. That
fallback can overprovision. No cache crosses threads or mask changes. The Linux
manual documents large kernel masks exceeding fixed `cpu_set_t` and the need for
increasing-size probes; large-mask behavior here is also exercised synthetically.

Construction and start may occur under different masks; changing a mask or CPU
hotplug does not resize an existing pool. Allowed logical CPUs do not measure
bandwidth quotas, exclusive physical cores or a service's entitlement. The
[kernel cgroup documentation](https://docs.kernel.org/admin-guide/cgroup-v2.html)
defines cpuset availability separately from CPU bandwidth controls.

Cross-repository capability detection matters while pins remain immutable.
The new runtime header defines `FORGE_PLATFORM_HAS_AVAILABLE_CPU_COUNT`. A small
private stdlib helper chooses the new API only with those headers and otherwise
uses the old API. Current stdlib builds and passes 13 suites against the exact
pristine pinned runtime, including HTTP auto-count and inherited-mask checks.
This does not authorize mixing new headers with an arbitrary older archive;
headers and libraries must match as usual. No weak symbol, dynamic lookup or
unpublished revision is needed for the retained old-runtime fallback.

## Regression and review evidence

The runtime regression checks real singleton and sparse masks, gated execution
on every worker, explicit oversubscription, unchanged online counts and separate
caller/child-thread counts. Simulated affinity calls exercise a mask containing
CPU 4095, EINVAL retries, empty results, EPERM, first and mid-probe allocation
failure and the 1 MiB bound. Allocation/free tracking and deliberately changed
errno after free check cleanup and error preservation. Explicit pin tests cover
valid requests, invalid bounds, OS rejection and preservation of the parent mask.

HTTP startup tests now inspect actual worker masks under a high singleton CPU
and a sparse auto mask, retaining all queued-request and startup-failure cases.
The int64 binding regression prevents large values from becoming valid CPU IDs.
Separate counterfactual probes fail on the baseline for auto count and explicit
pinning. A naive macro-only enablement makes explicit pinning pass but fails the
inherited-worker-mask probe. The fixed library passes all three.

- Full project: **30/30** suites, using explicit local component overrides.
- Runtime Release: **7/7**; final ASan/UBSan/leak checks: **7/7**.
- Combined stdlib/runtime ASan/UBSan/leak checks: **16/16**.
- Current stdlib against pristine pinned runtime: **13/13**.
- Fresh self-host stage3/stage4 C fixed point: byte-identical.
- Installed-SDK benchmark CMake target: built successfully.

Compiler sources did not change in this step, but its linked platform object did:
the stage0 binary hash is now
`a7781418b399a91c5db14e77d0c1ee1242efd19fc41c3514b12d7f6bb176c6fa`.
The fixed-point generated C hash is
`e1516621f8d9c3dbc0a7fe07a141936564a39b757c4e2325dae3df59925392b5`.
The candidate SDK runtime archive matches the measured frozen archive.

Three OMO/Sisyphus reviews completed with `opencode/mimo-v2.6-flash-free`: design,
actual implementation and measurement/compatibility evidence. Findings prompted
explicit fallback/size-limit documentation, per-thread and narrowing checks and
broader call-site inspection. Suggested caching was rejected because callers'
masks can differ. A status-returning replacement would change the public API;
the existing best-effort contract is documented instead. Suggestions for weak
symbol dispatch were unnecessary for matching older headers/archives, as the
pristine compatibility build verifies. The reviews' statistical cautions are
retained below. One CLI invocation failed before a session started; it is kept
as a failed invocation and is not counted as review. Model review is not a proof.

Only Linux/GCC 13.3/glibc 2.39 was executed. Windows, macOS, musl and real hardware
with CPU IDs above 1023 were not tested. io_uring is unavailable on this host;
its fallback builds, while its enabled path is unverified. TLS compiles, but no
TLS capacity or handshake result follows from these tests. The earlier TSan
initialization failure remains unresolved; no TSan race result is claimed here.

## Performance evidence and limits

The frozen before/after runtime libraries differ only by this affinity step;
both already include native-depth accounting and lifecycle cleanup. GCC 13.3.0
uses `-O3 -std=c11 -Wall -Wextra`, no LTO. The same C source is linked against each
archive. An external taskset supplies singleton `{11}`, sparse `{8,10}` and
`{4,6,8,10}`, and full `{0..11}` masks. Producer and workers share that mask.
Every live thread's actual mask and expected worker count are checked, along with
per-item exact-once execution, per-worker counts and independent affine checksums.
Each invocation submits 20,000 unsigned LCG jobs of 16 or 1024 steps.

The first series has 16 rows × 24 alternating AB/BA pairs, or 768 measured
invocations. Automatic baseline pools have 12 workers; candidate auto pools have
1, 2, 4 or 12. Controls explicitly request the mask's size in both variants.
One warmup pair per row is excluded and retained. Per-invocation warmup initially
used 64 jobs; that did not guarantee every worker had run. The full-mask tiny auto
row's 0.897x ratio prompted a separate 24-pair confirmation, starting BA instead.
It remained 0.927x [0.812, 1.035], with explicit control 0.992x [0.912, 1.084].
This is not evidence that the cost disappeared.

A final 16-row, 24-pair series uses a condition-variable gate to run one warmup
callback on **every** worker before releasing them. Its first pair is BA. This
strengthens the initial-state check without changing production code or deleting
prior data. It does not eliminate the full-mask concern. The original two-pair
fixture probe, both 24-pair matrices and focused confirmation remain separate;
none is pooled or selected away. The three main/confirmation series contain
1,632 measured invocations and 32,640,000 jobs, excluding retained warmup pairs.

Kernel wall time includes submission, callbacks, completion and stop/join. Item
setup, creation, warmup, result verification, sorting and terminal destruction
are outside it. Additional total-time and process-CPU measurements are retained;
total includes lifecycle, warmup and CPU-mask inspection, so it is a harness
interval, not pure application latency. The final gate primitives are set up and
torn down outside that interval.

Ratios below are baseline time / candidate time, using paired log-geometric
means; numbers below 1 mean the candidate took longer. Brackets are individual
95% paired-bootstrap intervals (5,000 resamples), not family-wise guarantees.

| Allowed CPUs | Policy | Steps | Original warmup ratio [interval] | Every-worker gate ratio [interval] |
|---|---|---:|---:|---:|
| {11} | auto | 16 | 2.871x [2.782, 2.949] | 2.585x [2.505, 2.656] |
| {11} | explicit 1 | 16 | 1.006x [0.987, 1.025] | 0.967x [0.902, 1.022] |
| {11} | auto | 1024 | 1.261x [1.236, 1.293] | 1.241x [1.232, 1.249] |
| {11} | explicit 1 | 1024 | 0.995x [0.989, 1.000] | 0.994x [0.981, 1.002] |
| {8,10} | auto | 16 | 2.769x [2.478, 3.099] | 3.112x [2.707, 3.589] |
| {8,10} | explicit 2 | 16 | 1.059x [0.978, 1.195] | 1.019x [0.977, 1.072] |
| {8,10} | auto | 1024 | 1.213x [1.098, 1.328] | 1.142x [1.031, 1.257] |
| {8,10} | explicit 2 | 1024 | 1.086x [0.967, 1.228] | 1.033x [0.905, 1.178] |
| {4,6,8,10} | auto | 16 | 3.332x [2.738, 4.079] | 2.864x [2.085, 3.783] |
| {4,6,8,10} | explicit 4 | 16 | 1.253x [1.029, 1.581] | 1.187x [0.988, 1.484] |
| {4,6,8,10} | auto | 1024 | 2.019x [1.763, 2.340] | 2.297x [2.011, 2.660] |
| {4,6,8,10} | explicit 4 | 1024 | 0.990x [0.919, 1.059] | 1.081x [1.013, 1.153] |
| {0..11} | auto | 16 | 0.897x [0.807, 0.983] | 0.927x [0.851, 1.010] |
| {0..11} | explicit 12 | 16 | 1.021x [0.954, 1.100] | 1.067x [1.001, 1.138] |
| {0..11} | auto | 1024 | 0.968x [0.899, 1.044] | 0.986x [0.920, 1.058] |
| {0..11} | explicit 12 | 1024 | 0.999x [0.940, 1.065] | 1.000x [0.930, 1.073] |

Restricted-mask auto batches improve by about 1.14–3.11x in the gated series;
that observation belongs to this finite workload. The full-mask tiny auto point
is still about 7% slower, with a wide interval. There is no demonstrated absence
of that cost. Some explicit controls also have intervals excluding 1 despite
unchanged worker counts. These many rows and metrics have no multiplicity
correction; shared-host drift, lock contention, scheduling phase and correlated
samples can bias the intervals. AB/BA reduces order imbalance, not those effects.
Treat them as descriptive sampling estimates, not calibrated confidence against
all systematic error or a non-inferiority proof.

Batch completion time and individual queue latency diverge. Latency is sampled
inside the callback just after computing its result, before test counters and
scheduler completion bookkeeping. Gated auto results include these cases:

| Allowed CPUs | Steps | Baseline median p99 (ms) | Candidate median p99 (ms) | Paired p99 ratio [interval] |
|---|---:|---:|---:|---:|
| {11} | 1024 | 31.477 | 25.070 | 1.248x [1.236, 1.257] |
| {8,10} | 1024 | 17.313 | 20.892 | 0.679x [0.528, 0.846] |
| {4,6,8,10} | 1024 | 0.431 | 17.577 | 0.054x [0.029, 0.108] |
| {0..11} | 16 | 0.083 | 0.101 | 0.891x [0.800, 0.995] |
| {0..11} | 1024 | 0.121 | 0.144 | 0.809x [0.697, 0.920] |

A ratio of medians is not the paired geometric statistic. The four-CPU heavy row
has much lower total batch time but much worse queued-job p99. The producer has
no in-flight bound; latency includes backlog. Fewer workers and less submission
contention can let submission outrun service, but this study does not decompose
the causal contributions. Explicit worker counts remain available for workloads
with different latency/I/O needs. This candidate is not a replacement for caller
backpressure, fairness analysis or workload-specific sizing. Full-mask p99 costs
also remain visible. No sustained service capacity, CPU-quota behavior, HTTP
throughput or universal improvement follows from these batches.

## Reproduction

The raw archive retains source snapshots, both patch boundaries, frozen libraries
and executables, baseline and naive-enable counterexamples, exact build commands,
all benchmark samples, completed OMO requests/responses and the failed invocation.
`REPRODUCE.md` describes the normal/sanitized/old-runtime builds and each timing
series. `manifest.json` hashes every retained file. Both measured runtime archives
are rebuilt from retained source and compared byte for byte.
All four measured benchmark executables and all three controller source hashes
also reconstruct exactly.

These changes follow the [design principles](../../../forge/docs/design-principles.md): distinguish
observed hardware from usable resources, retain caller placement policy, preserve
dependency boundaries and report latency costs alongside throughput.

- [Raw evidence](cpu-affinity-2026-10-15.raw.tar.gz)
- [Archive SHA-256](cpu-affinity-2026-10-15.sha256)
