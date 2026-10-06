# Forge benchmarks

Independent compiler, scheduler, queue, string and HTTP fixtures, comparison scripts, and measured reports. Fixtures for C, Python, Phoenix and Rust Axum remain in `benchmark/`. Published observations are retained in `docs/`; they describe the dated revisions and machines in their metadata.

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

`selfhost_compare.py` accepts explicit compiler binaries and inputs. `continuation_bench.py` accepts separate compiler checkout/build pairs, `--before-sdk` and `--after-sdk` installed prefixes, and optional `--source` for the shared bootstrap input; no fixture is read from the compiler checkout.

Portfolio comparison scripts reproduce the historical disposable Docker application snapshots recorded in `docs/`. They require `--project-root` and before/after snapshots with the original compiler/include/runtime/stdlib layout; for split source checkouts supply `--before-runtime-root`, `--before-stdlib-root`, `--after-runtime-root`, and `--after-stdlib-root`. The application snapshot's build adapter defines the legacy toolchain layout inside the disposable image. Profiling scripts consume those prepared snapshots and do not modify active application deployments.

Apache 2.0; see [LICENSE](LICENSE) and [PROVENANCE.md](PROVENANCE.md). Original raw console measurements are retained alongside structured reports.
