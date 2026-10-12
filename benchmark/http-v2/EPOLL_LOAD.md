# Epoll observer (separate protocol)

`http-load-epoll` is a separately versioned Linux client for controlled
correctness and future load experiments. It uses one epoll reactor and at most
`CONCURRENCY` simultaneous sockets, with one new TCP connection per request.
The existing `http-load` binary and its runner remain unchanged. Do not combine
their timing samples: this client uses nonblocking socket progress in one
reactor rather than blocking OS threads per lane.

```text
http-load-epoll PORT CONCURRENCY REQUESTS SEED RESPONSE_FILE ROWS_FILE CONNECT_TIMEOUT_MS [IO_TIMEOUT_MS]
```

The optional I/O timeout defaults to 10 seconds and is exposed to allow bounded
local correctness tests. A request succeeds only after every response byte
matches the supplied expected file and a separate receive observes EOF. A
short response, wrong byte, extra byte, connect timeout, or I/O timeout records
its stage and fails the trial. The first failure stops new work; already active
connections are drained or timed out. Each completed request is immediately
written as one TSV row, including failures. As in the V2 observer, rows reach
the page cache without an `fsync` power-loss durability guarantee.

Build and exercise only the observer correctness suite; this file makes no
throughput or server-capacity claim:

```sh
cargo build --manifest-path benchmark/http-v2/Cargo.toml --bin http-load-epoll
python3 benchmark/http-v2/test_load_epoll.py \
  --binary benchmark/http-v2/target/debug/http-load-epoll
```

For a separately versioned V3 server/client validation run, use
`benchmark/http_compare_epoll_v3.py --validate-only`. It creates an immutable
build snapshot, records compiler/dependency/source/binary hashes and full
commands, runs the existing independent server probes, then exercises this
observer against both prepared servers. The runner stores its own source and
report protocol ID and does not change the V2 runner or observer. Omit
`--validate-only` only when intentionally starting a paired performance run;
never combine V3 timings with V1/V2 observations.
