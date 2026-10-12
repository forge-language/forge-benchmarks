# Prepared HTTP observer protocol v2

This is a separately versioned diagnostic observer for the prepared HTTP
backends documented in `../http/README.md`. The Forge server, Rust server and
CPU configuration helper are copied unchanged from V1; their file hashes permit
checking that identity. The crate/runner are separately named so V1 snapshots,
executed sources, reports and long-latency samples remain intact.

V1's blocking connect happens before its read/write timeouts. During the first
16-pair run, passive observation found all client lanes waiting in SYN-SENT while
the server's accept queue was empty. Both Forge and Rust had complete, correct
attempts affected by long delays. Their cause is unproven; see
`../../docs/http-prepared-handshake-diagnostic-2026-10-12.md`.

V2 changes the shared observer, without changing either server's HTTP algorithm:

- `TcpStream::connect_timeout` explicitly bounds connection establishment;
  `--connect-timeout-ms` defaults to 10,000 and is recorded in every attempt.
- Every request records total, connect, socket setup, request write, response
  read and final EOF wait durations. Extra bytes or early EOF fail validation.
- Every completed attempt, including failures, is immediately written as one
  TSV row under a mutex to an unbuffered file. These writes reach the OS page
  cache; they do not promise power-loss durability and do not call fsync.
- The first failed request stops later unattempted requests. All already
  in-flight requests complete or time out and are recorded. A partial/failed
  trial fails the entire comparison without retry or a throughput claim.
- Passive before/after `/proc` snapshots retain per-port socket states,
  retransmission/queue metadata, global TCP counters, conntrack counts, socket
  counts and kernel limits. A deadline/error also snapshots live state before
  killing only the owned process groups.

Global counters belong to the shared network namespace and do not prove that
the benchmark caused any change. Passive observations transmit no packets,
change no sysctls and attach no tracing. Listener options/handshake root cause
remain subject to investigation; the timeout only bounds observation.

V2 adds observer timing, per-request writes and mutex contention; the aggregate
interval includes those costs. Its response read and EOF are separate calls,
and its connect implementation uses the standard timeout path. These are
material protocol differences. Do not merge V1/V2 timing samples or declare V2
performance better solely because connection stalls become bounded failures.
A timeout is retained evidence that prevents a target claim.

Build and validate only after the active V1 measurement has stopped and the
benchmark coordinator authorizes those jobs. This source has not yet been
compiled or tested.

```sh
python3 benchmark/http_compare_v2.py --sdk /path/to/validated-sdk \
  --build-dir /tmp/http-v2-build --output /tmp/http-v2-validation.json --build-only
python3 benchmark/http_compare_v2.py --sdk /path/to/validated-sdk \
  --build-dir /tmp/http-v2-build --reuse-build \
  --output /tmp/http-v2-validation.json --validate-only --connect-timeout-ms 10000
```

Subsequent performance measurements also require coordinated exclusive timing,
fresh output paths and the same balanced paired protocol documented for V1.
All rows, failures, warmups and source/artifact/runner hashes are preserved.
