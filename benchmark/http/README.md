# Prepared HTTP backend fixture

This compares the current Forge public `http_listen`, `http_prepare` and
`http_serve_mt` path with an owned Rust/socket2 implementation of the same
prepared-response backend policy. It does **not** compare Axum routing or a
general HTTP parser, and does not support a language-wide 110% claim.

The Forge fixture contains actual FG API calls; its generated C links the
snapshotted SDK stdlib/runtime archives. The shared C file implements CPU
configuration only. `--wrap=fr_thread_pin_cpu` maps Forge's existing worker IDs
to explicitly selected physical cores, preventing the runtime's absolute
`0..N-1` pin requests from escaping inherited affinity. Rust calls the same
configuration helper. The runner checks every server thread's affinity/count
before and after every sample; clients occupy separate physical cores.

The Rust control owns listening sockets, accepted streams, epoll descriptors and
the shared response. It uses pinned socket2 0.6.4/libc 0.2.186, Rust `Read` and
`Write::write_all`, and Linux epoll/accept4 FFI. Both backends use level-triggered
epoll, SO_REUSEPORT listeners per worker, at most 256 accepts per readiness
visit, 8,191-byte complete-header consumption, 5-second receive/send timeouts,
an 8,192 listen backlog and requested 65,536-byte listener buffers. Neither
backend parses the request method/path/body. They return exactly:

```text
HTTP/1.1 200 OK\r\nContent-Length: <ASCII body length>\r\nConnection: close\r\n\r\n<body>
```

Every body comes from a reproducible runtime seed. Each request opens a new
loopback TCP connection, varies its seeded path and 32..543-byte header padding,
then checks every response byte and EOF against a packet independently built in
Python. The same shared Rust observer drives both servers. It records every
request ID, latency, received byte count and error in a TSV; no failed request or
outlier is dropped. A trial failure aborts claims and retains partial report,
attempt metadata, logs and earlier samples. Processes are cleaned up by their
specific process groups, including on failures.

Independent Python packet checks cover small/large headers, complete response
bytes, body lengths and the case where the final two header-terminator bytes
arrive later. Responding prematurely fails validation. The validation mode also
runs bounded load-observer smoke checks with all request IDs verified; its
timings are diagnostics only and it emits no performance summary.

Use an immutable SDK prefix containing `bin/forge`, `include/`, and
`lib/libforge_runtime.a`/`lib/libforge_std.a`. Paths must be fresh; reports and
builds are preserved by default.

```sh
python3 benchmark/http_compare.py --sdk /path/to/validated-sdk \
  --build-dir /tmp/http-build --output /tmp/http-validation.json --build-only
python3 benchmark/http_compare.py --sdk /path/to/validated-sdk \
  --build-dir /tmp/http-build --reuse-build \
  --output /tmp/http-validation.json --validate-only
```

Run throughput measurements only after coordinating exclusive benchmark timing:

```sh
python3 benchmark/http_compare.py --sdk /path/to/validated-sdk \
  --build-dir /tmp/http-build --reuse-build --output docs/http-run.json \
  --workers 1 2 4 --concurrency 16 64 --body-bytes 32 4096 \
  --requests 12000 --pairs 16 --client-cores 2
```

Every configuration has independently balanced Forge-first/Rust-first orders,
shuffled using a recorded seed. Each sample immediately follows a complete,
same-input checked prewarm. Ratio = Rust elapsed / Forge elapsed for an equal
fixed request count; 1.10 means 110% of Rust throughput for that configuration.
The confidence interval is a 10,000-resample percentile bootstrap of paired
ratio medians. It is not family-wise and applies only to this run/environment.

The timed interval begins at the observer's release barrier and ends after all
requests and client worker joins. Server startup/probes, response preparation
and client thread creation are excluded. Timed server CPU counters and separate
whole-process CPU/RSS are retained. Client generation/checking, finite bursts,
kernel loopback work, ephemeral ports/TIME_WAIT, scheduling, response size,
frequency and shared-host load can limit measured throughput. The benchmark
reports complete connection-per-request behavior rather than isolated maximum
server capacity. It does not cover keepalive, semantic parser correctness,
request bodies, malicious timeout traffic, TLS, routing, database work, async I/O
or coroutine scheduling. A separately optimized prepared backend can use a
different policy; that requires a separate clearly labeled comparison rather
than silently changing this fixture.

The build freezes every compiler/archive/header/fixture input, generated C,
dependency lock, dependency manifest/checksum identities, command and output.
Each run freezes its executed Python runner source, environment and raw attempts.
SDK binary hashes identify actual measured inputs; sibling source observations
may differ from those SDK builds and are labeled as observations.
