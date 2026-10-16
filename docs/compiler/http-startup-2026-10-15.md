# HTTP worker startup retains queued connections

This is a local **forge-stdlib candidate**, based on
`6aa28667b83009a415ab2d7ac13ef6c675af7012`, tested through Forge's explicit local
SDK override. The compiler repository's immutable stdlib pin is unchanged. A
clean default dependency fetch does **not** contain this fix; integrating a
published, tested stdlib revision remains necessary.

## Defect and ownership transition

The previous `fr_http_spawn_workers` closed the original listening socket before
allocating contexts and creating replacement reuseport listeners. Connections
already established in its listening queue reset. Allocation and all-worker
failure also passed the closed, potentially reused descriptor to the fallback.
A successful TCP connection therefore did not establish that worker startup
would preserve that connection.

The candidate retains the original socket as worker zero. Context allocation or
first-thread failure serves on that socket in the caller, with no detached worker
holding freed contexts. Reuseport is enabled only after the first thread starts,
so these early inline fallbacks also retain exclusive binding. Later failures close only newly owned sockets and reuse
the unused context slot. Successful detached-worker contexts retain their
existing process lifetime. No request parsing, response, timeout, readiness,
accept-batch, scheduler-pool or cooperative-yield path is removed.

Before multi-worker serving, `http_listen` retains its exclusive bind behavior.
At worker startup, Linux/macOS try enabling reuseport on the existing listener
and binding additional listeners. The documented portable ordering is to enable
reuseport **before bind**; this best-effort late enable is deliberately not a
portable guarantee ([Linux socket manual](https://man7.org/linux/man-pages/man7/socket.7.html)).
The independent socket probe on this Linux 6.8 kernel demonstrates that late
enable and subsequent binding succeed here. If either operation prevents a new
bind, Linux/macOS workers share the original nonblocking listener. Other
platforms stop adding workers after bind failure, retaining the original worker
without multiplying the generic polling loop. Shared-listener fallback may
increase wakeups and contention; it carries no cross-platform throughput claim.

Port zero now records the actual bound port with `getsockname`, so additional
workers join that port instead of opening unrelated ephemeral ports. Failure to
resolve it closes the socket and reports listen failure. No public ABI changes.
This is not a graceful shutdown implementation; detached workers and their
listener/context resources remain process scoped. Event-loop creation failure,
concurrent server close and complete server lifecycle remain separate concerns.

This applies the [resource ownership principle](../../../forge/docs/design-principles.md): worker
startup must preserve queued work and leave a valid fallback resource. It also
preserves the existing multi-worker reuseport exposure after serving begins,
without enabling sharing for ordinary single-worker users at listen time.

## Correctness evidence

The standalone fixture prints readiness after `listen`/prepare and waits on a
pipe. The client establishes and sends eight complete requests before allowing
worker startup. No response is retried. Across five runs per mode:

| Mode | Baseline successful queued requests | Candidate |
|---|---:|---:|
| Single event loop control | 40 / 40 | 40 / 40 |
| mt, two accept workers | 0 / 40 | 40 / 40 |
| hybrid, two accept and two pool workers | 0 / 40 | 40 / 40 |
| uring API, epoll fallback on this build | 0 / 40 | 40 / 40 |

The fixture caps CPU discovery at two via GNU linker wrapping; it does not
change production code. Native io_uring is unavailable on this machine and is
not credited as tested.

The Linux CTest regression uses real sockets and fork synchronization with GNU
linker failure injection. It covers explicit and ephemeral ports, one and three
workers, context allocation failure, first/later thread failure, all/partial
additional-listener bind failure, failure to enable the original listener's reuseport option, and a failed
additional bind combined with later thread failure on the shared original. Pipes confirm that the intended fault actually occurred and
that multi-worker startup completed. Each case checks eight prequeued and 32
new requests after startup without connection/response retries. New connections
also detect sockets left open after failed worker creation. Three repetitions
cover 54 cases and 2,160 exact response checks. A separate getsockname-failure
injection checks that the rejected port-zero listener really closes its fd.
Caller-loop entry markers prove that allocation/first-thread faults reach the
intended inline fallback, where exclusive binding is rechecked. The parent closes its inherited
listener copy, so it cannot accidentally keep the defective child's queue alive.

A first extension of the test to post-start connections once timed out in its
single-worker control before diagnostics were added; later runs passed. This
failure is retained in the experiment notes and is not counted as a pass.

## Steady-state measurement

AMD BC-250, Linux 6.8.0-139-generic x86_64, GCC 13.3.0 Release, LTO off.
Runtime revision is `dcbb1929b17c2f1d11fd367ecf80c7c87c58a274`. The before/after
static libraries differ by the retained local stdlib patch. The final candidate
fixture was rebuilt from the final production source before this measurement.

For each of mt and hybrid, 24 paired AB/BA comparisons use four native blocking
clients, two accept workers and, for hybrid, two scheduler-pool workers. Each
sample has 200ms warmup then 1s measurement. Server affinity is CPUs 0/1; clients
use CPUs 8/9/10/11. These masks split the workload, but the host runs other work;
this is not exclusive CPU isolation. Each request opens a connection, sends the
complete GET, verifies the exact status/body and waits for close. Timing includes
client work and finishing outstanding requests, rather than a server-only CPU
kernel. Port 50321 is fixed across variants. Listener inode inspection confirms
two listeners on the actual service port in every measured sample.

| Mode | Baseline median req/s | Candidate median req/s | Median paired candidate/baseline | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| mt | 7,370.69 | 7,379.06 | 1.001x | 0.808–1.219x |
| hybrid | 4,613.08 | 5,266.82 | 1.094x | 0.561–2.300x |

Ratios are medians of per-pair ratios, not ratios of the two marginal medians.
Intervals use 10,000 resamples of the 24 pairs with a recorded random seed.
The intervals are wide: **neither a speedup nor absence of a regression is
established**. This change is accepted as a startup correctness candidate;
stronger performance conclusions require a less variable measurement setting.

Median per-sample p50/p95/p99 latencies (microseconds) are 133/423/578 →
127.5/404.5/557.5 for mt and 153.5/504.5/733.5 → 148/519.5/759.5 for hybrid.
Median server CPU seconds per sample are 0.625 → 0.625 and 0.475 → 0.505,
respectively. Per-client request counts are retained, not summarized as a
fairness guarantee. Across all 96 measured samples, **766,104 responses were
verified with zero measured errors**. The separate startup-ready probe retried
one baseline connection error and zero candidate errors before warmup. Measured
requests are never retried; the warmup probe is excluded from throughput.

Two initial random-port attempts are retained in full as partial datasets/logs,
not silently discarded successes: the first stopped after a candidate sample
had four timeouts, and the second recorded four baseline connect/send timeouts
then stopped on a later baseline warmup connection timeout. An earlier complete
fixed-port run before the final startup-order adjustment is also retained. The
cause of the random-port failures remains unresolved; zero errors in the final
fixed-port run does not explain or erase them. No general network-reliability
or service-capacity claim follows from this small cached-response workload.

The independent fanout probe also checks that successful late enable here does
more than permit binding: over 2,000 connections, the two late-enabled listeners
accepted 1,032/968, compared with 986/1,014 with reuseport enabled before bind.
This demonstrates fanout on this kernel, without asserting another kernel's
behavior or replacing the shared-listener fallback proof.

## Independent OMO review

Three focused OMO requests and their actual completed responses are retained.
The design review challenged changing `http_listen` to enable sharing before
bind; that proposal was rejected. Its claim that Linux categorically rejects
late enable was checked against the independent socket probe, not accepted as
proof. The implementation review confirmed context/fd ownership and shared
nonblocking accept, and found port-zero rebinding and incomplete failure-case
coverage. Both were addressed. It also identified shared-listener wakeup costs
and generic polling amplification; the latter is bounded by retaining one
worker when extra binds fail outside Linux/macOS. Its suggestion that serving
previously remained exclusive is contradicted by the old code's reuseport
replacement listeners. Agent findings are evaluated against source and tests.

The final review identified an untested bind-fallback plus later-thread-failure
combination, weak evidence that faults hit the intended caller fallback,
sharing enabled before allocation/thread success, and a missing getsockname
failure check. The final code/tests address each: mixed failure coverage,
caller-loop markers, sharing only after successful first-thread creation with
exclusive-fallback checks, and an explicit closed-fd assertion. The test marker
extension initially disabled its own observation flag after injected allocation
failure; its failed log is retained and the harness now tracks fault firing
separately. The final release and sanitizer runs below use the corrected harness.
Windows/macOS and the generic-platform branch remain untested.

## Reproduction and retained artifacts

Final validation: **25/25 CTest suites passed** with the local SDK override;
the final 54-case startup regression also passed ASan, UBSan and leak checking.
The old library fails the pre-final-review regression with a queued-request
connection reset. The final standalone fixture again passes all 160 responses,
including 120 requests in the three formerly failing multi-worker modes.
The compiler repository's existing self-host regression passed in the full run;
no new claim about bootstrap/runtime equivalence is inferred.

From the archive directory, see `REPRODUCE.md` for exact build and measurement
commands. `stdlib.patch` was applied to an archived clean pinned stdlib and all
four changed files matched the candidate byte for byte. `manifest.json` hashes
every retained artifact; `patch-check.json`, `validation.json`, the test logs
and all three completed OMO exports make the review boundary inspectable.

- [Raw sources, measurements and OMO records](http-startup-2026-10-15.raw.tar.gz)
- [Archive SHA-256](http-startup-2026-10-15.sha256)

The archive retains baseline/candidate source and libraries, fixture and native
load-generator source, commands/scripts, paired samples, failed attempts, build
and test logs, OMO exports, environment metadata and a patch against the pinned
stdlib. The checksum file covers the archive. Explicit local dependencies are
required until the candidate has a published revision and the compiler's pin is
updated. No clean-install or release-integration claim is made.
