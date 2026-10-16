# Scheduler lifecycle: serialize restart and reclaim owned pending work

This local **forge-runtime candidate** fixes the two lifecycle defects reproduced
in the [native-depth study](native-depth-2026-10-15.md). It is incremental to that
local deferred-depth candidate, on runtime base
`dcbb1929b17c2f1d11fd367ecf80c7c87c58a274`. The compiler dependency pin remains
unchanged; a default clean dependency fetch does not include these local changes.
Both source snapshots, a cumulative patch and an incremental patch are retained.

The complete local project passes 28 CTest suites; standalone runtime tests pass
6 suites, also with ASan, UBSan and leak checking. The original 16-byte internal
spawn-wrapper leak reproducer exits without a leak in the new build. Restart
ordering is tested with deterministic three-actor gates and a deliberately
incomplete mutant, rather than inferred from a timeout disappearing.

## Start and stop publication

Old `fr_scheduler_start` set `running` and the global scheduler before acquiring
the scheduler mutex. A start during stop could therefore re-enable a worker that
stop was joining, leaving it idle instead of exiting. There was a second window:
stop cleared the global scheduler after dropping its final mutex, so it could
erase a new start's registration of the very same object.

Start now acquires the existing scheduler mutex and waits in a loop while stop
is in progress, then publishes running/global state and creates workers under
that mutex. Stop retains its unlock across worker joins. After joining, it clears
the old global registration under the mutex, before clearing `stopping` and
waking starters. The compare/exchange remains atomic: another scheduler has its
own mutex and may have become global, so a plain store would erase that other
object's registration.

The mutex orders state publication; it does not extend a raw pointer's lifetime.
These blocking lifecycle operations belong to external controllers. Callbacks
must not wait for their own workers to stop, and terminal destruction requires
publication and other lifecycle callers to be quiescent. This change does not
make arbitrary concurrent destruction or callback-owned lifecycle calls safe.

The old minimal two-thread restart probe held its callback gate while calling
start synchronously from the gate owner. With corrected serialization, that
start intentionally waits for stop; the gate owner cannot release its gate in
that arrangement. Its historical timeout is therefore not used as the new
completion oracle. The new regression separates gate owner, stopper and starter,
checks that start really waits, and then releases the callback to let stop finish.

## Terminal cleanup is distinct from stopping

Stop still retains queued work for restart. Terminal destruction stops/joins
workers, then supplies a private disposer to native-queue destruction. Only
pending head nodes are disposed; cached nodes already transferred their arguments
when they were popped and are never disposed again.

| Pending argument | Terminal action |
|---|---|
| Internal one-argument spawn wrapper | Free wrapper storage; do not call user function |
| Internal indexed wrapper | Finish its batch reference under the batch mutex, signal the final waiter, free wrapper; do not call user function |
| Direct-submit opaque argument | Leave caller-owned storage untouched |
| Argument in a cached/already-claimed node | Never revisit it during queue-cache destruction |

Normal indexed completion and terminal discard share one small finish helper.
The user's function runs only on normal execution. Last-reference signaling is
followed by unlocking the batch mutex; the helper then frees only its own context
and does not access the shared batch state again. The indexed caller returns
from its wait before destroying its own condition/mutex/stack count. Already
completed callbacks and pending discards both contribute exactly once.

The lifetime argument uses POSIX's requirement that a successful condition wait
returns owning its mutex and its allowance for destroying an unlocked mutex
after the last reference releases it. Here the sole waiter destroys the batch
primitives only after its own wait returns; no finisher accesses them after
unlock. See the primary [condition-wait specification](https://pubs.opengroup.org/onlinepubs/9799919799/functions/pthread_cond_clockwait.html)
and [mutex-destruction rationale](https://pubs.opengroup.org/onlinepubs/9799919799/functions/pthread_mutex_destroy.html).

An indexed waiter may finish after scheduler destruction only once its publication
phase has ended: its post-publication wait/teardown touches batch state, not the
scheduler. Tests establish that boundary with a real condition-wait entry marker.
Destroy racing further publication remains forbidden; adding a `running` check
to submit would not solve raw-pointer lifetime and would break deliberate
pre-start enqueue and stopped-pool backlog behavior.

This reclaims runtime-owned wrapper storage. It does not infer ownership of
arbitrary void pointers, integer handles or resources referenced by user code,
and adds no general cancellation-result API. The queue cleanup callback is a
private runtime interface; public function signatures and node layouts remain
unchanged. No new allocation, lock or ownership tag is added to normal push/pop.
Constructor partial cleanup still permits zeroed/uninitialized queues: empty
lists invoke no disposer and the platform mutex destroy is NULL-tolerant.

This follows the [ownership and lifecycle principles](../../../forge/docs/design-principles.md):
joining execution and destroying retained work are different operations, borrowed
arguments do not become owned by proximity, and an old stop cannot erase a fresh
publication of the same live object.

## Deterministic regression coverage

- Fifty overlapping start/stop cycles make start enter its actual wait while the
  old callback is gated. A GNU wrapper holds stop **after its final unlock**,
  allowing new start to return before old stop returns. This forces the former
  trailing-CAS window. Global identity/availability and fresh callback progress
  are checked after both callers join.
- A distinct scheduler becomes global while the first stops; destroying/stopping
  the first must not clear the second registration.
- A tracked owned allocation is freed exactly once by terminal discard. A
  borrowed stack argument remains intact, and no user callback runs on discard.
  An executed cached wrapper is not freed a second time.
- Full, five-item partial and zero-publication indexed batches terminate correctly.
  Forced queue-publication failure tests rollback as well as discard. Pending
  wrappers span four native queues. A separate batch executes its first callback
  and discards the remaining 36, releasing its waiter without replaying work.
- The low-level queue test contains both pending nodes and cached nodes with
  already-freed arguments. Its disposer sees exactly the one pending argument.

The baseline fails the new overlap regression because start returns before stop
finishes. A start-only mutant (corrected start, old unlocked global CAS) fails the
post-join global-identity assertion. Both baseline and mutant also fail the
tracked-owned-discard assertion. The fixed library passes all of these checks.
The mutant prevents a test that catches only the first race from being mistaken
for coverage of both ordering defects.

The original isolated leak-mode fixture is retained separately: baseline has the
previously recorded 16-byte LeakSanitizer report; the fully instrumented fixed
library exits zero with empty sanitizer output. This is a wrapper leak fix,
not evidence of complete lifecycle or user-payload memory safety.

## Performance scope

Before/after libraries differ by this lifecycle change, with the same native-depth
ledger already present in both. The same GCC 13.3.0 Release C fixture/controller
runs 20 rows of 24 alternating AB/BA pairs on the recorded Linux AMD BC-250 host.
It verifies independent LCG checksums, exact result checks, CPU masks, per-worker
counts and completion percentiles. The 960 measured invocations complete
9,600,000 native jobs in the job rows and 96,000,000 observations in getter rows.
One warmup pair per row is excluded. The CPU map and finite-workload limitations
are the same as the native-depth study; the host is shared.

| Native workload | Paired lifecycle-candidate speedup | 95% bootstrap interval |
|---|---:|---:|
| queried, 1 workers, 16 steps | 0.992x | 0.951–1.033x |
| control, 1 workers, 16 steps | 0.993x | 0.950–1.036x |
| queried, 2 workers, 16 steps | 0.985x | 0.947–1.020x |
| control, 2 workers, 16 steps | 1.041x | 1.014–1.068x |
| queried, 4 workers, 16 steps | 1.110x | 0.987–1.281x |
| control, 4 workers, 16 steps | 0.962x | 0.845–1.083x |
| queried, 8 workers, 16 steps | 1.019x | 0.993–1.048x |
| control, 8 workers, 16 steps | 1.000x | 0.974–1.024x |
| queried, 4 workers, 1024 steps | 0.969x | 0.917–1.026x |
| control, 4 workers, 1024 steps | 1.029x | 0.949–1.119x |

No native-job row has a 95% speedup interval wholly below 1. This is not a
non-inferiority proof, and no new throughput improvement is claimed for this
correctness fix. Wide intervals in some rows leave meaningful costs possible.
All samples, including getter-only costs and tail/worker-count observations,
remain in the raw report.

The timed job interval includes submission, completion and stop/join; creation,
warmup, verification and terminal destruction are outside it. The new pending
cleanup adds necessary linear work when destroying a backlog. These ordinary
drained-batch timings do not measure that cleanup cost or compare equal semantics
against the old leaking destructor. No HTTP, sustained-capacity or general
fairness claim follows from this finite native workload.

## Independent OMO review and verification boundary

Three OMO/Sisyphus reviews completed using `opencode/mimo-v2.6-flash-free`: the
initial design review and separate final reviews of ownership and start/stop
ordering. The focused ownership review found no lifetime, double-free or user
callback defect within the stated publication boundary; it explicitly withdrew
the initial conjecture that the waiter destroyed a still-blocked condition
variable. The ordering review found no counterexample within the live-owner
contract. Its note about unlocked worker-slot clearing is covered by the
`stopping` exclusion: other start/stop callers wait, and terminal destruction
requires their quiescence.

Review suggestions were checked against the implementation contract. A proposed
plain global store was rejected because other schedulers use different locks;
the distinct-scheduler regression covers that case. A proposed running-state
submission guard was rejected because stopped/pre-start enqueue is intentional
and such a guard cannot extend raw-pointer lifetime. One broader final review
exhausted its response limit with no answer; it is retained as a failed review,
not counted as completed. Model review supplements the deterministic tests and
source reasoning; it is not a concurrency proof.

Full project CTest passes **28/28** with local component overrides. Runtime CTest
passes **6/6**, including the new lifecycle and existing native-depth, coroutine,
I/O and work-queue regressions. ASan/UBSan/leak checking passes the same six runtime
suites. Fresh stage3/stage4 self-host fixed-point verification passes. The final
test-only CLI extension for isolated owned cleanup is rebuilt and retested.

The current ThreadSanitizer build succeeds, but its lifecycle binary exits 66 at
startup with `FATAL: ThreadSanitizer: unexpected memory mapping`. It produces no
usable race result and is not counted as a passing check. This environment limit
does not weaken the explicit ownership/quiescence preconditions above.

The runtime README and public header document external ownership, publication
quiescence, retained stop backlog and terminal-discard behavior. The two previous
native-depth lifecycle findings are fixed within that contract. Inactive Linux
CPU pinning, raw-pointer lifetime enforcement, very-large pending-count range
and general cancellation/lifecycle API design remain separate concerns; the
active project goal is not marked complete by these bounded checks.

## Reproduction and retained artifacts

Configure/build the runtime with explicit Release or sanitizer flags, then run
CTest. For the entire project use the existing explicit local runtime/stdlib
source overrides. The archive's `REPRODUCE.md` records exact commands, baseline
and candidate fingerprints, both patch boundaries and benchmark invocations.
The cumulative runtime patch applies to the immutable runtime base; the
incremental lifecycle patch applies to the retained prior local-depth snapshot.

Sources, frozen libraries/binaries, deterministic baseline/mutant failures,
normal and sanitizer logs, fixed leak fixture, before/after performance samples,
self-host output hashes and completed OMO requests/responses are retained.
`manifest.json` hashes every retained file. No unpublished revision is installed
as a new immutable dependency pin.

- [Raw source, tests, measurements and OMO records](scheduler-lifecycle-2026-10-15.raw.tar.gz)
- [Archive SHA-256](scheduler-lifecycle-2026-10-15.sha256)
