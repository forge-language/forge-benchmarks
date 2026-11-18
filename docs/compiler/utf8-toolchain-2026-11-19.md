# Using one Forge log filter in native code and JavaScript

The [example](https://github.com/forge-language/forge/blob/ac2e9cde0aa21489bc6cdbba06ce73ff2d115863/examples/log_alerts.fg) scans a UTF-8 buffer by byte offset and counts records starting with `WARN ` or `오류 `. On a generated 100,000-record, 1,400,000-byte corpus, both native compilers and the JavaScript program counted exactly 60,000 alerts. The Node program took **114.3 ms**, down from **220.1 ms** on this host. This measures process startup, building the buffer, scanning, output and exit.

## Measurements

All times below are medians in milliseconds. Each pair used identical inputs. The runner alternated compiler or program order by pair. The host ran Linux x86-64 on an Intel Core i5-13400F with GCC 15.2.0 and Node 24.15.0. These are shared-host observations. The raw samples include variation for each input.

| Workload | Pairs | Baseline | Candidate |
| --- | ---: | ---: | ---: |
| Stage0 emits C for the 88,550-byte baseline compiler | 41 | 5.787 | 5.006 |
| Stage0 emits C for 3,000 literal updates | 41 | 4.680 | 4.082 |
| Stage2 emits C for the baseline compiler | 41 | 75.233 | 7.691 |
| Stage2 emits C for 160 constants and 160 functions | 41 | 17.066 | 4.591 |
| Stage2 emits C for 512 unused literal constants | 41 | 3.433 | 3.146 |
| Stage2 emits C for a tiny print program | 41 | 0.511 | 0.505 |
| Stage2 emits C for the log example | 41 | 0.587 | 0.578 |
| Node scans the 100,000-record corpus | 25 | 220.096 | 114.281 |

The compiler measurements include validation, code generation and writing C to disk. Baseline and candidate emitted byte-identical C for every compiler timing fixture. The timer stops before a downstream C compiler would run.

The JavaScript prefix microbenchmark builds both programs before timing. Each sample starts Node, performs 120,000 calls and checks the exact count. The 2,048-byte ASCII case uses 16,000 calls. Short ASCII hits went from 168.6 to 32.7 ms and mixed ASCII/Korean hits from 169.1 to 39.7 ms. A 160-character Korean prefix took 210.7 and 210.6 ms. The longer ASCII case took 84.2 and 73.4 ms. Short views and early mismatches are included in the archive. Each microbenchmark has 17 pairs.

## What changed and where the gains end

- Stage0 selects keyword candidates by token length. Decimal integers of up to 18 digits fit in int64, so their lexer path accumulates digits directly. Longer integers and floats use the existing checked conversion.
- The Forge-written compiler records each constant name and its source position while validating top-level structure. A reference finds that record and checks the original initializer in global scope. The constant table is absent on sources with no constants. Queries still scan records linearly. Local lookups search from the latest declaration, and duplicate constants keep their original diagnostic order.
- Generated JavaScript compares ASCII prefix bytes directly. Short Unicode suffixes share a lazily allocated 192-byte workspace. Longer suffixes use the previous encoder path. The second improvement converts a BigInt byte offset once. Every in-bounds typed-array offset is exactly representable as a Number. Other incoming JS types keep the original checks. The prefix change alone took 137.2 ms on the corpus.
- A subsequent 256-entry BigInt byte cache increased corpus time from 115.4 to 120.6 ms in a separate 25-pair run. We discarded it. We also inspected a 32-arm integer dispatch compiled by stage0. GCC already lowered the native code to a bounds check and a 32-byte result table. We kept the existing native lowering.

Stage2 and stage3 generated the same C when compiling the final bootstrap source. The installed compiler checks its documented subset with `forge-fg --check`. The fixed point and timings cover that subset and the measured workloads. Complete ownership checking and full stage0 parity remain open.

## Reproduce

Use Forge commits `642aea4c8f474246bc06beb38d236155f5b460ab` and `ac2e9cde0aa21489bc6cdbba06ce73ff2d115863` in two checkouts. Configure each with `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release` and run `cmake --build build -j4`. Both use the pinned runtime `dcbb1929` and stdlib `6aa28667`, with LTO off. Run these commands from this benchmark repository with `before` and `after` set to the absolute checkout paths.

```sh
(cd docs/compiler && sha256sum -c utf8-toolchain-2026-11-19.sha256)
tar -xzf docs/compiler/utf8-toolchain-2026-11-19.raw.tar.gz
python3 benchmark/selfhost_compare.py \
  --stage2 baseline "$before/build/bin/forge-stage2" \
  --stage2 candidate "$after/build/bin/forge-stage2" \
  --source utf8-toolchain/inputs/compiler.fg --source utf8-toolchain/inputs/constants.fg \
  --source utf8-toolchain/inputs/unused.fg --source utf8-toolchain/inputs/tiny.fg \
  --source utf8-toolchain/inputs/log_alerts.fg --repeats 41 --output stage2.json
python3 benchmark/selfhost_compare.py \
  --stage0 baseline "$before/build/bin/forge" --stage0 candidate "$after/build/bin/forge" \
  --source utf8-toolchain/inputs/compiler.fg --source utf8-toolchain/inputs/literals.fg \
  --source utf8-toolchain/inputs/tiny.fg --source utf8-toolchain/inputs/unused.fg \
  --repeats 41 --output stage0.json
python3 utf8-toolchain/js-study.py "$before/build/bin/forge" "$after/build/bin/forge" prefix.json
"$before/build/bin/forge" utf8-toolchain/inputs/corpus.fg --emit-js -o before.js
"$after/build/bin/forge" utf8-toolchain/inputs/corpus.fg --emit-js -o after.js
python3 utf8-toolchain/corpus_bench.py corpus.json before.js after.js
```

The compiler and prefix tables were measured at `dca7d9d`. The final `ac2e9cd` adds the view-index change exercised by the corpus. Stage2 is byte-identical across those revisions. The archive includes binary and source hashes, chronological trial samples, fixtures, independent review findings and the fixed-point digest. The early `first` prototype in the trial data used first-match function signatures. The shipped compiler preserves latest-signature lookup for later imports. [Download the raw study](utf8-toolchain-2026-11-19.raw.tar.gz).
