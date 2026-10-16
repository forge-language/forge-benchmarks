# Forge benchmarks

Independent compiler, scheduler, queue, string and HTTP fixtures, comparison scripts, and measured reports. Fixtures for C, Python, Phoenix and Rust Axum remain in `benchmark/`. Published observations are retained in `docs/`; they describe the dated revisions and machines in their metadata.

Standalone tools have one home here: [compiler runners](benchmark/compiler/README.md),
[platform runners](benchmark/platform/README.md), and [web bridge runners](benchmark/web/README.md).
Compiler/runtime studies are in [docs/compiler](docs/compiler/README.md), with
platform studies in `docs/platform/`. Source-dependent runners take an explicit
checkout; no benchmark submodule is required to build the compiler or components.
Public website report snapshots are served assets and remain with forge-platform.

Install the compiler, runtime and standard library into one SDK prefix. Then build independently:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$FORGE_ROOT" -DFORGE_ROOT="$FORGE_ROOT"
cmake --build build -j2
cmake --build build --target benchmarks -j2
./build/bin/scheduler_bench throughput 10000 1
python3 benchmark/string_measure.py --binary build/bin/string_bench --output build/string.json
REQUESTS=1000 CONCURRENCY=16 bash benchmark/run_benchmark.sh
```

`FORGE_ROOT` is an installed SDK prefix, including `bin/forge`, `include/`, and `lib/`. `BENCH_BUILD_DIR` overrides the shell runners' default `build/`. HTTP fixtures require the relevant SDK dependencies (curl, TLS, microhttpd, etc.); use `-DFORGE_BUILD_HTTP_BENCHMARKS=OFF` for the scheduler-only fixture. The HTTP scripts default to large loads; set requests and concurrency explicitly for a short local run.

The private work queue benchmark requires `-DFORGE_RUNTIME_SOURCE_DIR=/path/to/forge-runtime`; it deliberately uses that checkout's `src/work_queue.h` and must match the installed runtime revision. Internal queue structs are not a public SDK contract.

`parser_compare.py` compares the same 100000-declaration fixture on explicit compiler checkouts and records source hashes, wall time and `realloc` counts. It requires a GNU-compatible linker for allocation wrapping:

```sh
python3 benchmark/parser_compare.py --before-root /path/to/before-forge --after-root /path/to/forge --output build/parser.json
```

`native_depth_bench` and `benchmark/native_depth_compare.py` compare frozen runtime
archives through the public queued-depth API. Build the same C fixture against
each archive, then pass the two executables with `--baseline`, `--candidate` and
an unused `--output` directory. The Linux fixture uses producer CPU 10 and explicit
worker masks drawn from CPUs 0–9; adapt both fixture and controller consistently
on another host. It checks observed thread masks, independent LCG checksums,
per-worker work counts and per-job completion latency. Query-only rows and
no-query native-job controls are separate measurements; no HTTP or general
scheduler fairness guarantee follows from these finite batches.

`affinity_bench` and `benchmark/affinity_compare.py` compare automatic pool sizing
with explicit worker-count controls under singleton, sparse and full Linux CPU
masks. Build the identical C fixture against baseline/candidate runtime archives;
pass the two binaries with `--baseline`, `--candidate`, `--pairs 24` and an unused
`--output` directory. The fixture requires CPUs 0–11 on this host and verifies
every live thread's actual mask, per-item exact-once execution, an independent
affine checksum and completion latency. A warmup gate runs a callback on every
worker before timing. The controller expects the older
baseline to size automatic pools from online CPUs and the candidate from the
inherited mask. Producer and workers share the selected CPUs. The kernel timing
includes stop/join; the additional total timing includes lifecycle, warmup and
affinity inspection. This is a finite shared-host workload, not a CPU entitlement,
HTTP throughput or universal pool-size recommendation.

`dispatch_bench` and `benchmark/dispatch_compare.py` compare explicit equal-size
pools with native jobs, native jobs beside 32 parked receivers, yielded coroutine
controls, and half-native/half-coroutine work. The Linux controller requires CPUs
0–11, uses verified inherited masks and defaults to 24 AB/BA pairs per row. An
all-worker gate fixes the start boundary; every result is checked exactly once
against an independent affine oracle. Coroutine publication is outside kernel
timing, native publication is inside; total timing includes setup and receiver
cleanup. These are before/after comparisons within each workload, not cross-mode
throughput rankings. Raw latency and per-worker counts accompany wall/process CPU
time. Optional GNU-wrapper instrumentation counts queue probes separately and
must not be used for the timing claim.

`selfhost_compare.py` accepts explicit compiler binaries and inputs. `continuation_bench.py` accepts separate compiler checkout/build pairs, `--before-sdk` and `--after-sdk` installed prefixes, and optional `--source` for the shared bootstrap input; no fixture is read from the compiler checkout.

Portfolio comparison scripts reproduce the historical disposable Docker application snapshots recorded in `docs/`. They require `--project-root` and before/after snapshots with the original compiler/include/runtime/stdlib layout; for split source checkouts supply `--before-runtime-root`, `--before-stdlib-root`, `--after-runtime-root`, and `--after-stdlib-root`. The application snapshot's build adapter defines the legacy toolchain layout inside the disposable image. Profiling scripts consume those prepared snapshots and do not modify active application deployments.

Apache 2.0; see [LICENSE](LICENSE) and [PROVENANCE.md](PROVENANCE.md). Original raw console measurements are retained alongside structured reports.
