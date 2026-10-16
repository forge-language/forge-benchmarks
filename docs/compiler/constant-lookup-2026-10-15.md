# Deferred constant-name indexing

The semantic checker now resolves global constant declarations through a private,
pass-owned adaptive index. On this Linux host, repeatedly referencing the last
of 16,384 constants checks **24.34x** faster, emits C **17.88x** faster and emits
JavaScript **20.24x** faster. These are compiler CLI workloads, not generated
program runtime speedups or a claim about ordinary applications.

## The measured bottleneck

After the preceding function/local lookup work, every nonlocal identifier still
scanned `Program.consts` in declaration order. N late references among N constants
therefore performed N² comparisons. The baseline check took a median 0.297s at
8,192 constants and 1.150s at 16,384 in the initial three-run scaling probe.
A separate GCC `-pg` build attributed 65.38% of its sampled self time to semantic
`expression`; this is a coarse instrumented profile, not a timing comparison
against the Release compiler or a complete account of uninstrumented libc work.
The host rejects perf events (`perf_event_paranoid=4`); that global setting was
not changed. Raw scaling, build command and gprof records are retained.

## Identity and contextual checking

[`compiler/const_index.h`](../../../forge/compiler/const_index.h) borrows the final const
owner array and names after module loading. Owners of at most 16 declarations
stay linear. Larger owners spend at most 4*N name comparisons before allocating
an auxiliary (declaration pointer, ordinal) vector and sorting it. Unqueried
owners do not allocate; a single full scan and N first-entry hits remain linear.
The probe budget saturates instead of wrapping, and the shared allocator bounds
count × entry size and terminates on failure.

Sorting compares the existing length/strncmp name semantics, then declaration
ordinal. Lower-bound lookup preserves the first declaration, including duplicates,
without reordering the AST. Pre-promotion work is bounded by the comparison
budget; promoted lookup takes logarithmic name comparisons. String comparison
still costs bytes, and qsort's sorting/scratch costs belong to the platform
library: this is not a platform-independent worst-case sort bound. On this
x86_64 build, entries cost 16 bytes each (256KiB at 16,384 constants), plus a
32-byte descriptor and the platform sort's scratch storage. This is auxiliary
index storage, not peak compiler memory.

Lookup remains after the current local binding and before function references.
It returns the same `ConstDecl*` as the old scan, then recursively checks its
initializer **on every use in the current Check context**. No expression result,
type, initialization or ownership state is cached. In current stage0 behavior,
a referenced initializer can observe a local that shadows one of its names;
it can consequently produce a contextual type, uninitialized-value or moved-value
diagnostic. This change preserves that existing behavior and source range. It
does not certify or repair the language's constant semantics or backend support
for arbitrary initializers. For example, semantic forward-alias checking and C
literal-only constant emission retain their existing different capabilities.

The const owner does not grow during checking. The index is freed when the pass
ends, before `optimize_program` rewrites initializer expressions, and no index
is reused across passes. No public AST layout, runtime ABI, native/JS emitter or
scope mutation protocol changes. The implementation remains typed and separate
from the existing function index to avoid changing stable owners and callbacks
for this one additional table.

This implements the [design principle](../../../forge/docs/design-principles.md) that stable
identity and contextual analysis require separate proofs. A faster lookup alone
does not justify memoizing inferred types or changing the point at which flow
state is observed. Recursive initializer work, module-name discovery, struct
fields and unrelated compiler scans retain their existing costs.

## Paired measurements

AMD BC-250, Linux 6.8.0-139-generic x86_64, glibc 2.39, GCC 13.3.0 Release, LTO off.
Baseline is the previous local/function-index working tree, not clean HEAD
`a750b60923bcc71adda025596664dd9a0413f80b`:

- Baseline compiler SHA-256: `680501c1724c0a2bdb0d2e8fdfab77a4f0bfb4e4d5e9be270f0bd97ef53fdf69`
- Candidate compiler SHA-256: `b1165dd18d1367ee249e23f1a994120dfb9f525b2c8c5525042af542666f9c65`

Both use runtime revision `dcbb1929b17c2f1d11fd367ecf80c7c87c58a274` and the same
build SDK. The local stdlib is based on `6aa28667b83009a415ab2d7ac13ef6c675af7012`
plus the separately archived [HTTP startup candidate](http-startup-2026-10-15.md).
The compiler CLI measurements do not link the emitted programs against either
stdlib variant; SDK/component pins are unchanged by this compiler change.

[`tests/const_lookup_bench.py`](../../benchmark/compiler/const_lookup_bench.py) records 23 rows,
each with one excluded warmup pair and 24 alternating AB/BA measured pairs.
Timing includes process startup, parsing/checking/optimization and, when selected,
C/JS emission. The system C compiler and program execution are outside this
measurement. The controller and child compiler use CPU 2; the host is shared,
so affinity does not establish exclusive CPU isolation. Source hashes, compiler
hashes, exact commands, all samples and row-wise 95% bootstrap intervals are
retained. C and JS outputs must match byte for byte after every pair.

| Workload | Baseline median | Candidate median | Paired geometric speedup | 95% interval |
|---|---:|---:|---:|---:|
| last_1024_check | 9.54ms | 5.17ms | 1.89x | 1.84–1.95x |
| last_8192_check | 296.32ms | 24.64ms | 12.07x | 11.96–12.19x |
| last_16384_check | 1159.50ms | 47.04ms | 24.34x | 23.88–24.69x |
| last_16384_emit_c | 1178.07ms | 65.71ms | 17.88x | 17.75–18.04x |
| last_16384_emit_js | 1163.12ms | 57.46ms | 20.24x | 20.08–20.38x |
| spread_16384_check | 598.29ms | 51.99ms | 11.59x | 11.45–11.77x |
| imported_8192_check | 299.39ms | 25.77ms | 11.64x | 11.55–11.72x |
| imported_8192_emit_js | 310.20ms | 33.74ms | 9.18x | 9.07–9.26x |

`last` has N functions each reading the last of N literal constants. `spread`
visits varied declaration positions; imported cases place the owner in a source
module merged before checking. All declarations/functions remain in the output.

The 16/17/128-declaration rows, hello, bootstrap check/emission, and large
first-entry, unqueried and single-query rows do not establish a gain. Their
recorded 95% intervals all include 1. These controls are part of the result,
not discarded exceptions. The candidate adds 1,792 bytes of ELF text on this
build (254,720 → 256,512); data/bss sizes are unchanged. The final explicit
standard-header includes and allocator comment leave the compiler binary hash
identical to the measured candidate.

## Correctness and validation

- An independent forward-scan oracle checks 40,000 generated queries over empty,
  tiny, threshold and larger owners. It covers duplicate declarations with
  distinct payloads, empty names, long shared prefixes, nonterminated slices,
  length differences, interior-NUL strncmp equality, unchanged owner order,
  independent owners and promotion midway through an unfinished search.
- Public native/JS tests exercise promoted lookup and lexical shadows. Native
  tests also distinguish an unqualified constant value from a same-named function
  call. Exact diagnostics cover first duplicates, unknown values and contextual
  alias type/uninitialized/moved state. Forward checks and cyclic-depth errors
  retain their existing behavior.
- An independent differential corpus has **74 programs × 3 CLI modes = 222
  comparisons**. All baseline/candidate statuses, stdout and stderr match exactly,
  and successful C/JS outputs match byte for byte. Of the programs, 55 pass check
  and 19 reject it. C emission can still reject some semantically accepted alias
  forms as before; it is compared rather than reinterpreted as a successful build.
- **26/26 full CTest suites passed**, including the local stdlib startup regression.
  Fresh stage1/stage2 regeneration and stage3/stage4 fixed-point verification
  passed. The final expanded const-index unit was rerun after review changes.
- The final const-index oracle passes AddressSanitizer, UndefinedBehaviorSanitizer
  and leak checking. The sanitizer-built compiler also passes all 20 diagnostic
  test methods, including the new promoted/contextual cases. Sanitizer success
  is limited to these exercised paths.

## Independent OMO review

Two completed read-only OMO requests and actual responses are retained. The
design review supported the typed index and identified the contextual-memoization
trap, first-duplicate ordering and mid-probe promotion cases. Its suggestion that
ConstDecl was private was a concatenated-excerpt misreading: the declaration
already lives in `ast.h`, so no public AST relocation was needed.

The implementation review found no lookup/order defect, and its assumptions
were checked against actual source. `forge_calloc_array` checks overflow and
aborts on NULL in `common.h`; no extra unchecked-allocation path was added.
Identifier characters in `lexer.c` exclude NUL; artificial NUL slices in the unit
retain the existing `forge_str_eq` semantics instead of silently switching to
memcmp. Explicit standard headers were added. Small-owner duplicate and empty-key
coverage was expanded. Budget/threshold expectations remain independent test
assertions so an unintended policy change fails rather than updating its own
oracle. Neither agent agreement nor the supplied excerpts replace source and
executable verification.

## Reproduction and artifacts

```
python3 tests/const_lookup_bench.py \
  --baseline /absolute/forge-baseline \
  --candidate /absolute/forge-candidate \
  --root /absolute/build-sdk \
  --output /absolute/new-measurement-directory --cpu 2 --pairs 24
```

Build with explicit local dependency overrides as documented in README. A before-change compiler/CMake
snapshot, incremental compiler patch and full final public-test sources
are retained. The incremental patch reconstructs the affected compiler/CMake/new
unit/benchmark files against the baseline snapshot byte for byte. Independent standalone builds
from both complete compiler-source snapshots also reconstruct the two measured
ELF binaries byte for byte, with commands and hashes in `reconstruction.json`.
The archive
includes the benchmark/statistics scripts, generated source/output, compiler
binaries, profile records, differential fixtures/results, sanitizer and full test
logs, self-host evidence and both OMO exports. `manifest.json` hashes retained
files; this report does not imply that local changes have been merged or released.

- [Raw sources, measurements and OMO records](constant-lookup-2026-10-15.raw.tar.gz)
- [Archive SHA-256](constant-lookup-2026-10-15.sha256)
