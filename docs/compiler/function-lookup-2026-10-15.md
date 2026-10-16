# Compiler function lookup: deferred per-owner indexes

The stage0 semantic checker and JavaScript emitter now share a pass-owned function
index instead of rescanning an entire owner array for every name. On this Linux
machine, a 16,000-function source checks **7.69x** faster and emits C **6.00x** faster;
a module of that size emits JavaScript **10.11x** faster. These are compilation
workloads, not generated-program runtime improvements or language-wide guarantees.

## Implementation and preserved behavior

[`compiler/function_index.h`](../../../forge/compiler/function_index.h) borrows the final
loaded declaration arrays. Owners of at most 16 functions retain linear lookup.
Larger owners initially use the same first-match scan, charging each comparison
against a saturating budget of 4 times the owner count. Repeated early hits and
sparse queries can finish without ever allocating an auxiliary array. When an
unfinished query exhausts the budget, the index sorts auxiliary entries by name
and declaration ordinal, then answers with lower-bound binary search.

This preserves the original first declaration, including duplicate names. It never
sorts the AST or changes declaration order. Bounded string comparisons work on
non-NUL-terminated name slices; they agree with the existing length-plus-strncmp
equality. Capacity multiplication is checked by `forge_calloc_array`. On this
x86_64 build an allocated entry takes 16 bytes per function, excluding temporary
sort-library storage; each owner descriptor takes 32 bytes. Unqueried owners have
no entry allocation. Descriptors and entries are private to one caller/pass and
freed on its normal return. They are not a shared concurrent cache.

The semantic checker retains its original module-name scan and its early return
on the first matching module, even when that module lacks the requested function.
An empty file module still blocks a same-named library. Unqualified top-level
functions still precede library functions. Existing module/global fallbacks,
stdlib and callback priority remain unchanged. The JS emitter retains its own
outer-loop behavior rather than replacing it with the semantic resolver.

The change does not complete ownership/type checking or alter their rules. Module
name, local binding and constant searches still have their existing costs. The
logarithmic bound applies to lookup within a promoted owner; it is not a claim
about the entire compiler or the platform's qsort implementation.

## Why sorting is deferred

An initial eager version delivered the large-owner gains but was about **0.936x**
as fast as baseline on 16,000 literal-returning functions with no name queries.
Its median check time was 27.94ms versus 26.10ms. That exploratory AB/BA experiment
is retained, along with the eager source and compiler.

The final probe budget removes that unnecessary setup and also avoids building an
index for a single late query or repeated cheap early hits. This follows the
[design principles](../../../forge/docs/design-principles.md): charge setup to actual work, preserve
source meaning and measure the paths that do not benefit from a fast path.

## Measurements

AMD BC-250, Linux 6.8.0-139-generic x86_64, glibc 2.39. Compiler binaries are Release
builds with GCC 13.3.0. The baseline is the previous mask-lowering working tree,
not clean HEAD `a750b60`; its exact binary is included. Runtime
`dcbb1929b17c2f1d11fd367ecf80c7c87c58a274` and stdlib
`6aa28667b83009a415ab2d7ac13ef6c675af7012` are unchanged.

- Baseline compiler SHA-256: `b1ce9f632e293176893b32cc6e677ec804c29a39b967badf1e2744d78861d22b`.
- Final compiler SHA-256: `1ec980faee8d23be2102ddc78d84f65198249f81d5de767f1fcab5e304d67de4`.

Each main row has 24 alternating AB/BA pairs after one warmup per executable,
using identical source files and SDK paths. Time includes CLI process startup.
Every measured C/JS emission pair must be byte-identical; no generated output is
patched or normalized. Large fixtures form a ring of forward function calls,
exercising all declarations; they are checked/emitted, not recursively executed.
Hello and the actual 67-function bootstrap source provide smaller real fixtures.
The final three rows exercise absent, sparse and cheap lookup workloads instead
of the expensive ring.

| Workload | Baseline median ms | Final median ms | Paired geometric speedup | Individual 95% bootstrap interval |
| --- | ---: | ---: | ---: | --- |
| Hello, check | 1.252 | 1.340 | 0.899x | 0.761–1.065x |
| Bootstrap, check | 7.898 | 7.722 | 1.003x | 0.974–1.028x |
| Bootstrap, emit C | 9.322 | 9.312 | 0.998x | 0.983–1.014x |
| 16 functions, check | 1.186 | 1.219 | 0.984x | 0.887–1.098x |
| 16-function module, emit JS | 1.466 | 1.476 | 0.959x | 0.868–1.054x |
| 17 functions, check | 1.304 | 1.330 | 0.935x | 0.851–1.031x |
| 17-function module, emit JS | 1.517 | 1.584 | 0.929x | 0.828–1.042x |
| 1,000 functions, check | 7.160 | 5.307 | 1.337x | 1.316–1.359x |
| 1,000-function module, emit JS | 9.630 | 6.421 | 1.517x | 1.492–1.548x |
| 4,000 functions, check | 37.451 | 14.032 | 2.663x | 2.640–2.686x |
| 4,000-function module, emit JS | 62.016 | 18.731 | 3.313x | 3.245–3.378x |
| 16,000 functions, check | 389.071 | 50.572 | 7.693x | 7.622–7.760x |
| 16,000-function module, emit JS | 718.383 | 70.375 | 10.107x | 9.913–10.265x |
| 16,000 functions, emit C | 410.332 | 67.707 | 5.996x | 5.875–6.112x |
| 16,000-function module, check | 380.190 | 52.918 | 7.168x | 7.111–7.227x |
| 16,000 unused functions, check | 27.044 | 26.740 | 1.016x | 0.996–1.038x |
| 16,000 functions, one late query | 27.857 | 27.281 | 1.019x | 0.980–1.059x |
| 16,000 functions, repeated early hits | 50.744 | 50.050 | 1.008x | 0.983–1.031x |

Intervals use 10,000 fixed-seed resamples of paired log ratios and apply to each
row individually. CPU 2 affinity is not exclusive core reservation; its SMT
sibling is CPU 3, and background activity/serial correlation remain possible.
Do not interpret the wide intervals for approximately 1ms CLI runs as proof of
non-regression. A separate 100-pair followup with 16/17-function fixtures found
intervals spanning 1 for all its rows (raw results retained); no speedup is
established for those cases or the actual bootstrap. The no-query, sparse-query
and early-hit rows likewise do not establish a speedup; their measured intervals
include 1 after removing the eager setup cost.

Reproduce the main run with:

```sh
python3 tests/function_lookup_bench.py \
  --baseline /dev/shm/forge-semantic-20261015/forge-baseline \
  --candidate build/bin/forge --root build \
  --output /dev/shm/forge-semantic-20261015/adaptive-benchmark \
  --cpu 2 --pairs 24
```

Choose a new output directory for a rerun. The archive contains both compiler
snapshots, emitted output, generated source, timings and exact commands. The
previous [mask report](modular-power-mask-2026-10-15.md) supplies the baseline's
source overlay on `a750b60`. The current source snapshot and incremental patch
separate this change from that earlier work.

## Verification

All 23 CTest suites pass, including the new function-index unit test. Release
test assertions are enabled with `-UNDEBUG`; the binary references `__assert_fail`.
The index test checks pointer identity against a linear oracle, duplicate first
winners, threshold boundaries, missing/prefix/slice keys, unchanged AST storage
and owner isolation across cleanup. Public native/JS tests exercise owner and
library precedence, constant-initializer references, callbacks and local shadowing.
An exact source-range diagnostic test now fails at the intended bad call after
promotion, retaining the first duplicate signature.

A deterministic 126-case differential corpus covers cold and promoted lookup,
accepted/rejected arguments, top/module/library owners, 0/1/16/17/64/257 functions,
duplicates and long common prefixes. All 39 accepted and 87 rejected cases agree
with baseline on exit status and exact JSON diagnostics. This preserves existing
checker behavior; it does not promise duplicate declarations can be emitted.

ASan, UBSan and leak detection pass 15 commands over the index unit, large owners,
source modules, no-query declarations and bootstrap checking/emission. The current
self-host chain rebuilds stage1/stage2, regenerates stage3/stage4 and reaches the
same fixed point. These are local Linux checks; native cross-OS/real ARM/WASM
performance was not measured for this compiler change.

An early manual test command used `--cc cc`; two fault-injection fixtures require
an absolute path for `os.execv` and failed to find that relative executable. This
invocation failure is retained. The final CTest run uses `/usr/bin/cc` and passes.

## OMO review

Independent design session `ses_ec2726364ffeYWfbMsvtDcse8r` completed a resolution
precedence/lifetime assessment and identified the empty-module, first-winner and
build-before-const risks. Those informed the implementation and tests. It saw an
in-flight eager version and is not counted as a final adaptive implementation audit.

Session `ses_ec26d1e52ffeB3swFh57awFJRr` first failed after repeatedly requesting an
unavailable glob tool; the CLI auto-rejected its doom-loop permission request.
The retry supplied the exact source attachments and requested no tool calls,
without overriding permissions. It completed the eager index review, then a
separate completed review of the final bounded-probe delta with `common.h` supplied.
No lookup-equivalence counterexample was found. The final review checked exact
and partial budget exhaustion, late hits, sparse/early queries, saturation,
allocation guards, borrowed pointers and normal cleanup. These are two review
sessions with multiple completed responses, not multiple delegated child agents
or machine-checked proofs.

The final review confirms comparator, ordinal/lower-bound, namespace and lifetime
arguments continue to apply. Fatal compiler error exits retain the existing
process-termination cleanup boundary; this change does not add in-process recovery.
The complete requests, failed attempt and finished responses are retained.

[Raw source, measurements and review records](function-lookup-2026-10-15.raw.tar.gz), [checksum](function-lookup-2026-10-15.sha256):

`3b3fd4b8c28fd38c4e8ff058a130f6f9e44817c4248abc8860ca0432b122a831`.
