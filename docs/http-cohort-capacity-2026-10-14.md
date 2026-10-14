# HTTP connected-cohort SLO capacity

The corrected V4.1 observer verifies **11,264 connected one-shot requests** for Forge and Rust: all eight balanced trials per implementation pass zero errors and p99 individual connection-start-to-validated-EOF latency at most one second. The next tested size, 12,288, fails the latency objective. This is the largest passing **tested burst cohort**, not an absolute maximum, accepted server population, sustained capacity or an application user count.

| Established cohort | Forge SLO pass | Forge p99 range (ms) | Forge median req/s | Rust SLO pass | Rust p99 range (ms) | Rust median req/s |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 11,264 | 8/8 | 911.83–937.18 | 11,374 | 8/8 | 905.42–988.62 | 11,415 |
| 12,288 | 1/8 | 996.38–1045.92 | 10,700 | 0/8 | 1006.66–1037.27 | 11,018 |
| 16,384 | 0/8 | No cohort released | 0 | 0/8 | No cohort released | 0 |

V4.1 has 48 recorded trials, no server-start failures, and 16 setup failures. The 16,384 lanes in each setup-failed trial are retained as errors; no partial cohort is released. Rows with errors are not accepted as passing capacity. In zero-error latency-failing trials, every response and EOF still validates. The 1,024-request gap between 11,264 and 12,288 is not searched exhaustively, and eight finite observations do not prove future reliability.

The experiment uses the committed `a750b60` Forge compiler, frozen SDK archive/header hashes, independent Rust server, four workers on physical cores 0/2/4/6, one Python selector on core 8, 32-byte bodies, eight source addresses, a two-second setup deadline and ten-second cohort I/O deadline. Python 3.12.3 and Linux 6.8.0 run on AMD BC-250. Kernel `somaxconn` is 4,096; each worker requests backlog 8,192, which the kernel may cap. These facts can constrain the setup boundary; this experiment does not isolate its cause.

All client TCP sockets connect before GET scheduling begins. A peek checks that each is open with no response bytes at the barrier; it is an observed client cohort, not an atomic server-side accepted-session census. Individual p99 includes socket creation/connect work after that lane starts, connection setup, barrier waiting, GET scheduling, matching response bytes and EOF observation. Request throughput uses the entire interval before the first connect through the last completion/failure, excluding later JSON logging and socket destruction. Failed-trial p99, when present, describes successful rows only and cannot satisfy the zero-error SLO.

The single Python observer and loopback TCP/kernel work are part of this metric. These burst rates cannot be pooled with [V3.3 continuous request-loop rates](http-v33-observed-128k-2026-10-13.md); neither comparison establishes a language-wide HTTP winner. TLS, keepalive, routing, database operations, application sessions and remote clients are unmeasured. HTTP was only tested on Linux. The [native five-workload CPU result](bounded-modpow-native-cross-os-2026-10-14.md) separately verifies the Rust 110% target on Linux, macOS and Windows.

An OMO read-only review process ran on spare logical CPU 11 during V4.1 and part of V4 boundary measurements. Its process/affinity record is archived. Shared-cache/kernel interference remains possible, and no samples are excluded for background load. The initial V4 grid ran before that server started.

The [initial V4 grid](http-cohort-grid-2026-10-14.json) contains all 56 trials. Its [finer V4 boundary](http-cohort-boundary-2026-10-14.json) retains all 112 trials, including 9 failed_no_claim server-readiness observations. A Rust stderr explicitly reports `AddrInUse`: V4 chose a port free on 127.0.0.1 while the server binds all addresses; TIME_WAIT on other source aliases can conflict. That mechanism is an inference from address scopes and stderr, not a captured per-socket proof of every failure. V4.1 selects a candidate with a wildcard bind. The reservation still closes before launch, so unrelated concurrent allocation can race; startup errors remain failures. V4 and V4.1 timings are separate and are not pooled. The corrected run is a new explicitly versioned experiment, not a hidden retry of failed rows.

Eight observer correctness tests cover byte mismatch, extra/short response, missing EOF, refused connect/no partial release, latency clock, nearest-rank p99 and alternate-alias port selection. Both frozen servers pass four independent normal/large/fragmented-header probes; every trial also performs a standalone exact-response probe. Raw row counts, IDs, barrier counters, nearest-rank p99 and SHA-256 hashes were independently checked before publication.

[V4.1 every trial and build metadata](http-cohort-v41-boundary-2026-10-14.json); [all three versions/runs, source, immutable build, request rows, failures, validation, environment and manifest](http-cohort-capacity-2026-10-14.raw.tar.gz), SHA-256 `1616cd676aee365d25e55c7600315d1ec395a1589ae39a5347b9ef56d79cb92a`.
