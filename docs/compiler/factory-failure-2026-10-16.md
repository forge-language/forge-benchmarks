# Factory failure boundaries — 2026-10-16

Resource factories now return a complete owner or NULL. The previous local
candidate reproduced eight construction/growth defects, including two SIGSEGVs;
the same fault probes all pass with the change. This is a correctness change at
construction boundaries. It adds no scheduler field, queue counter, dispatch
validity branch, public symbol or ABI layout change. No speedup or general
performance nonregression is claimed.

## Source and scope

The baseline is the local dispatch candidate documented in
[scheduler-dispatch-2026-10-15.md](scheduler-dispatch-2026-10-15.md), including
its earlier lifecycle, accounting and CPU affinity fixes. It is not the published
runtime revision. The raw archive contains complete baseline/candidate runtime
sources, candidate compiler/stdlib sources, this step's diffs, working-tree
patches, frozen tested binaries/libraries, commands, environment and model records.
The baseline runtime library rebuilt byte-for-byte from its retained sources.
The frozen baseline compiler SHA256 is
`a7781418b399a91c5db14e77d0c1ee1242efd19fc41c3514b12d7f6bb176c6fa`;
the isolated candidate compiler is
`f3865084aad4db02f4d48bf8a258736ff8f8cbcbbcba7806c3cba911e186ffb0`.
Build locations are embedded in the compiler; these hashes identify the retained
artifacts rather than promise identical compiler bytes under arbitrary paths.

Immutable dependency pins remain unchanged: runtime
`dcbb1929b17c2f1d11fd367ecf80c7c87c58a274`, stdlib
`6aa28667b83009a415ab2d7ac13ef6c675af7012`. Use both local source overrides to
exercise the tested candidate pair; a clean pinned build does not include the
runtime changes. No commit, push, publication or revision substitution was made.

## Construction and ownership

- POSIX mutex/condition factories check native initialization results. Failure
  frees storage without destroying an uninitialized primitive.
- Scheduler construction checks every private run/native queue lock. Queue arrays
  are zero-initialized, primitive factories return valid objects or NULL, and
  destructors tolerate NULL. Partial cleanup therefore needs no extra per-queue
  initialization flag. It starts no workers. The arena-provider hook is installed
  only after all required resources exist.
- Process construction checks name, lock and condition; a supervisor checks process
  creation before setting policy. Failed borrowed child-list growth commits neither
  pointer nor count. Registration remains a void, best-effort API with exclusive
  caller configuration; children do not transfer ownership.
- The stage0 C backend (`compiler/codegen.c`) emits process entry points that
  check scheduler, each process and each supervisor
  before body initialization. Prior objects already transferred to the scheduler
  are destroyed on failure, and the program reports the failure with exit status 1.
- Generated coroutine spawn checks a NULL result, frees the unattached raw state
  exactly once, reports the failure and aborts, matching the existing state-calloc
  fail-stop policy. All runtime NULL paths precede consuming the input state.
  Non-NULL coroutine results can still carry a terminal queue-publication error;
  this is not an execution guarantee. Nested owned fields on a fatal path and
  graceful in-process OOM recovery are not established by this change.

## Counterfactuals and regression checks

`factory_probe.c` is compiled unchanged against each frozen runtime library.
`baseline-probes.json` and `candidate-probes.json` retain exact commands and output.

| Injected fault | Baseline observation | Candidate observation |
|---|---|---|
| First native-queue mutex creation | Non-NULL scheduler; submit succeeds but pre-start depth is 0 | NULL owner |
| Process name allocation | Non-NULL process with NULL name | NULL owner |
| Process mutex creation | Non-NULL incomplete process | NULL owner |
| Process condition creation | Non-NULL incomplete process | NULL owner |
| Supervisor's process allocation | SIGSEGV | NULL owner |
| Second child-list realloc | SIGSEGV and previous array lost | Previous list survives; third insertion retries correct size |
| pthread mutex initialization | Non-NULL invalid primitive | NULL primitive |
| pthread condition initialization | Non-NULL invalid primitive | NULL primitive |

`runtime/tests/factory_test.c` additionally sweeps every allocation/native-init
site observed in successful mutex, condition, process, supervisor and explicit
three-worker scheduler creation, plus epoll creation failure. An independent
allocation/primitive/FD ledger verifies cleanup and rejects destroying a failed
native initialization or freeing a still-live primitive. Failed scheduler creation
preserves a sentinel arena provider; a separate started scheduler remains globally
registered and executes a job after another constructor fails. Child-list retries
are observed through realloc arguments and the borrowed returned pointers, without
mirroring the private process layout. Successful pre-start submission, exact queue
depth and execution remain covered. These are deterministic single-fault boundary
tests, not proof of all possible resource exhaustion or concurrent destruction.

For the process-name probe, `name_null:false` with a NULL returned owner means
no object was inspected, not that allocation succeeded. Successful queue behavior
is covered separately from rejecting an invalid constructor result.

The generated-C probe holds the runtime constant while switching between the
frozen old and new compilers. Old generated scheduler/process/supervisor failure
paths SIGSEGV; new paths exit 1 with diagnostics, zero tracked live owners and the
expected scheduler destruction count. Old coroutine failure silently drops output
and exits 0; new code frees the rejected raw state once and terminates with
SIGABRT. A second subcase fails the first calloc inside the actual runtime
coroutine factory and observes the same old/new behavior; the harness free marker
is observational, while abort is emitted by the compiler. Normal code still prints `7` and releases every tracked owner. Core dumps
are disabled in these subprocess tests. The fixture is retained in the compiler
regression suite through `tests/factory_faults.c` and GNU linker wrapping.

Validation:

- Isolated combined compiler/stdlib/runtime Release: **32/32 CTest suites**.
- Standalone runtime Release: **9/9 suites**.
- Combined stdlib/runtime Debug with ASan + UBSan, leak detection: **18/18 suites**.
- Real self-host rebuild and fixed point: stage 3 and stage 4 C files match SHA256
  `e1516621f8d9c3dbc0a7fe07a141936564a39b757c4e2325dae3df59925392b5`.
- The normal workspace build was refreshed with the same local source overrides;
  its new generated-failure regression passes separately. The complete compiler
  regression suite was rerun after adding the real coroutine-allocation subcase.

These runs are Linux-specific; macOS and Windows execution is not claimed.
All-worker thread-start failure, NULL-unaware external C callers and automatic
supervisor recovery remain separate work. The independent self-host generator
(`bootstrap/compiler.fg:964–970`) still emits unchecked scheduler/process creation;
this patch changes stage0 C code generation only. The fixed point proves output
stability for that subset, not that the two generators share the new failure paths. TSan was not run for this step; the
previous host initialization failure is not counted as coverage.

A retained negative control forces both worker thread starts to fail. Both frozen
versions still report pool availability and accept a queued job without executing
it. The probe stops and destroys the scheduler without invoking run; it does not
claim to measure a run timeout. This separately confirms the worker-start boundary
remains unresolved; no fallback policy is added in this patch.

## Normal dispatch controls

The unchanged dispatch fixture compares the frozen libraries at explicit 1 and
12 workers with 20,000 jobs, 16/1024 recurrence steps, native-only, 32 parked
receivers plus native work, yielded coroutine controls and half-native mixed
work. Every run validates an independent checksum, exact-once job execution and
all live CPU masks. Primary rows use 24 paired AB/BA observations plus excluded
warmups. Because adverse native results occurred, a second native-only batch
uses 32 pairs with the initial order reversed. Both batches are retained without
pooling or selecting favorable rows. This shared host is not an isolated machine;
a short baseline reconstruction build overlapped the beginning of the first
batch, and model CLI processes were also present.

Ratios are baseline time / candidate time: above 1 is faster. Kernel time excludes
owner creation and coroutine publication but includes gated release, native
publication, callbacks and stop/join. Total includes lifecycle/setup and parked
receiver cleanup, but excludes item/gate setup and result verification/sorting;
it is not whole-process elapsed time. Intervals are individual descriptive paired
bootstrap intervals, with no multiplicity or systematic-bias guarantee.

Primary batch:

| Workers | Steps | Mode | Kernel ratio [95% interval] | Total ratio [95% interval] |
|---:|---:|---|---|---|
| 1 | 16 | native | 0.988 [0.947, 1.033] | 0.985 [0.943, 1.030] |
| 1 | 16 | blocked | 1.013 [0.973, 1.056] | 1.009 [0.969, 1.050] |
| 1 | 16 | coro | 1.004 [0.977, 1.035] | 0.972 [0.943, 0.998] |
| 1 | 16 | mixed | 0.995 [0.962, 1.026] | 0.999 [0.977, 1.021] |
| 1 | 1024 | native | 1.001 [0.996, 1.007] | 1.002 [0.996, 1.007] |
| 1 | 1024 | blocked | 0.992 [0.982, 1.001] | 0.991 [0.981, 1.001] |
| 1 | 1024 | coro | 1.002 [0.990, 1.013] | 0.997 [0.986, 1.009] |
| 1 | 1024 | mixed | 0.998 [0.989, 1.007] | 0.995 [0.985, 1.004] |
| 12 | 16 | native | 0.951 [0.919, 0.981] | 0.952 [0.921, 0.982] |
| 12 | 16 | blocked | 0.980 [0.956, 1.003] | 0.980 [0.956, 1.003] |
| 12 | 16 | coro | 1.015 [0.986, 1.043] | 1.038 [0.989, 1.087] |
| 12 | 16 | mixed | 1.004 [0.983, 1.028] | 1.004 [0.984, 1.026] |
| 12 | 1024 | native | 0.869 [0.755, 0.975] | 0.872 [0.762, 0.973] |
| 12 | 1024 | blocked | 1.151 [0.949, 1.406] | 1.149 [0.957, 1.390] |
| 12 | 1024 | coro | 1.056 [0.959, 1.154] | 1.082 [0.989, 1.181] |
| 12 | 1024 | mixed | 1.029 [0.926, 1.160] | 1.024 [0.929, 1.142] |

Reversed initial order, native-only follow-up:

| Workers | Steps | Mode | Kernel ratio [95% interval] | Total ratio [95% interval] |
|---:|---:|---|---|---|
| 1 | 16 | native | 1.009 [0.959, 1.057] | 1.005 [0.956, 1.052] |
| 1 | 1024 | native | 1.000 [0.989, 1.011] | 1.000 [0.989, 1.012] |
| 12 | 16 | native | 0.989 [0.965, 1.014] | 0.989 [0.966, 1.014] |
| 12 | 1024 | native | 1.098 [0.987, 1.262] | 1.096 [0.987, 1.257] |

The primary 12-worker native total ratios are 0.952 (16 steps) and 0.872 (1024
steps), while the follow-up gives 0.989 and 1.096. The single-worker tiny-coroutine
primary total ratio is 0.972. These adverse measurements remain visible. The
follow-up changes direction for the expensive native case; this does not prove
the first result was noise, establish equivalence or justify a speedup claim.
Unresolved host variation, layout effects and workload tradeoffs remain limits.
Selected object bytes (`worker_main`, `fr_mutex_lock`, `fr_mutex_unlock`) match
between builds, but relocation targets and final placement can differ; identical
object bytes do not establish identical timing. The correctness fix is retained
without tuning layout to select a favorable benchmark outcome.

## Review and workspace recovery

OMO/Sisyphus was used for design, exact-source ownership review and evidence
review. Requests, JSONL responses and exported sessions are retained in the raw
archive. Model suggestions are hypotheses, not test results. The initial request
for extra per-queue init flags was rejected because the actual zeroed arrays,
nullable valid-only primitives and null-tolerant cleanup already represent partial
state; the resource ledger tests this boundary independently. See the retained
review resolution for final source/evidence findings.

During the work, disk exhaustion interrupted a header write. The header was fully
restored from a retained snapshot plus the intended edits and verified byte-for-byte.
Only derived local caches were temporarily relocated to RAM. Once disk space was
available, all six were copied back and verified including symlink targets; their
original paths are ordinary directories again. No source, user image, lockfile or
credential was removed. Recovery and restoration receipts are in the archive.

The [design principles](../../../forge/docs/design-principles.md) now connect complete construction,
publication, failure ownership and cold-boundary validation to the existing
performance contract. Raw evidence: [archive](factory-failure-2026-10-16.raw.tar.gz)
and [SHA256](factory-failure-2026-10-16.sha256).
