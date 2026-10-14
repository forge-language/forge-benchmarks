# Connected cohort protocol

`benchmark/http_cohort_compare.py` is a separate V4.1 finite burst-capacity
experiment. Its single Python selector establishes every TCP connection before
sending any GET. A nonblocking peek rejects a socket already closed or carrying
unexpected bytes at the barrier. The cohort is then released together; all
write scheduling, response validation and EOF observation remain measured.

The default service objective is zero errors and nearest-rank p99 **individual
connection-start to validated EOF** latency at most one second. This includes
each request's connection setup and barrier wait. Throughput divides successful
requests by the interval from before the first connection attempt through the
last completion/failure. JSON logging and socket destruction happen afterwards.
The two-second setup deadline precedes the prepared servers' five-second socket
deadline. A setup failure releases no partial cohort; every requested lane,
including unattempted lanes, is retained as a failure. There are no retries or
outlier exclusions. A response succeeds only when all expected bytes match and
EOF is observed; correct bytes without EOF still time out.

V4.1 chooses the candidate server port with a wildcard bind, matching the
server's address scope. V4's loopback-only selector could choose a port occupied
by TIME_WAIT on another source alias. Old failed runs remain recorded; timing
samples are not pooled across these versions. The reservation closes before
server launch, so an unrelated concurrent process can still win the port race;
startup failure remains a retained failed observation without a trial retry.

The server fixture, independent byte probe, immutable compiler/SDK build,
four-core worker pinning and Rust implementation are shared with V2. Order is
balanced and seeded. This measures the prepared 32-byte loopback HTTP response,
TCP backlog and a single Python client together. It does not count server
accepted sockets or application users and does not measure sustained arrival
rates, TLS, keepalive, routing or database work. Report the largest **tested**
cohort passing every trial and the next failed tested cohort; a finite grid
cannot prove an absolute maximum or future reliability. Do not pool V4 timings
with V2/V3 timings.

```sh
python3 benchmark/test_http_cohort.py
python3 benchmark/http_cohort_compare.py \
  --sdk /path/to/sdk --forge /path/to/compiler \
  --build-dir /fresh/immutable/build --output /fresh/report.json
```

Default grid: 256, 512, 1,024, 2,048, 4,096, 8,192 and 16,384 established
connections; four balanced pairs at each size. Every result, row file, command,
hash, server affinity, passive kernel snapshot and failure is retained. Python
observer cost can determine the boundary; it is an end-to-end local test limit,
not an isolated server limit or a Forge/Rust language-wide comparison.
