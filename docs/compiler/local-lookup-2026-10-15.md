# Local binding lookup and cheap shape rejection

Semantic checking and native C emission now use a private, scope-aware binding
index, and two string-loop recognizers reject irrelevant initializer shapes before
searching local names. On this Linux machine, C emission for 8,192-local workloads
improved **13.38–17.49x**; repeatedly reading an early binding checks **3.61x** faster.
These are compiler workloads, not generated-program runtime speedups or a claim
that every program compiles faster.

## Behavior and resource ownership

[`compiler/local_index.h`](../../../forge/compiler/local_index.h) mirrors the owner's local
binding stack. Entries contain borrowed names and integer links, never pointers
into the owner's reallocating array or copies of its types, initialization or
ownership flags. Lookup returns a position; callers read the current binding.
An absent name is SIZE_MAX, keeping binding zero distinct from a miss.

Unpromoted stacks of at most 32 bindings stay linear. For larger unindexed stacks, costly reverse scans
accumulate a saturating probe count. A later lookup activates buckets only after
at least four times the current binding count has been spent on comparisons.
Cheap recent hits and declarations with no queries can remain linear. Activation
copies the current names; subsequent pushes insert at bucket heads, and reverse
scope pops restore previous heads. Ascending rebuild and head insertion preserve
latest-declaration lookup through collisions, shadowing, slot reuse and growth.
Links strictly decrease, bounding even a deliberately colliding chain by active
binding count. This is not a collision-resistance or constant worst-case lookup
claim; hashing also costs time proportional to the name prefix length.

Non-zero truncation keeps a promoted cache active. Truncating to zero disables
the cache and resets the probe history. Allocation
capacity is retained within the pass, but reactivation clears only the bucket
range needed for the new owner. Popped names may be freed; they are never rehashed
on reuse. Both buffers are freed at pass end. On this x86_64 build, entry storage
is 24 bytes per allocated slot plus two 8-byte bucket heads per slot, with
geometric capacity rounding. This is auxiliary storage, not a total peak-memory
measurement.

Every semantic/native count mutation is paired with push/truncate. Missing hooks
fail explicitly through the count/head invariants. Compile-time offsetof checks
pin the first-member ForgeStr layout used by the stride/memcpy interface. The
semantic facade still returns a short-lived Local pointer; expression checking
never declares bindings, so that borrow does not span an owner reallocation.
The index itself retains only positions and borrowed name views.

Initialization checks, move state, branch/loop joins and current types remain in
the owner array. Declaration timing is unchanged in each pass. Coroutine emission
keeps its existing flat preloaded-name behavior; this change does not establish
new coroutine lexical or ownership rules. The JS emitter's fixed local table is
unchanged, while its shared semantic checking benefits from the new index.

In addition, reserved-builder and view-append matching now checks the type and
initializer shape before asking whether the binding name already exists. Those
read-only predicates accept the same shapes, but ordinary integer declarations
avoid needless lookup work. Literal-only C emission benefits chiefly from these
cheap rejection checks. The comparison measures the combined changes; it does
not isolate each one's causal contribution.

This implements the [design principles](../../../forge/docs/design-principles.md): cache names as
routes to live state, make scope mutation explicit, retain key lifetimes and
charge setup to work actually performed. It does not complete the language's
ownership, alias or lifetime checker.

## Measurement

AMD BC-250, Linux 6.8.0-139-generic x86_64, glibc 2.39; Release GCC 13.3.0, LTO off.
Baseline is the previous function-index working tree, not clean HEAD `a750b60`.
Both compilers use the same SDK. Runtime/stdlib commits remain
`dcbb1929b17c2f1d11fd367ecf80c7c87c58a274` /
`6aa28667b83009a415ab2d7ac13ef6c675af7012`.

- Baseline compiler SHA-256: `1ec980faee8d23be2102ddc78d84f65198249f81d5de767f1fcab5e304d67de4`.
- Final compiler SHA-256: `680501c1724c0a2bdb0d2e8fdfab77a4f0bfb4e4d5e9be270f0bd97ef53fdf69`.

Each row has 24 alternating AB/BA pairs after one warmup per executable. Time
includes CLI startup; inputs/output live on /dev/shm. CPU 2 affinity is not an
exclusive core reservation (its SMT sibling is CPU 3); background load and serial
correlation remain possible. Every C emission pair must be byte-identical, with
no generated-C editing or normalization. Intervals are individual 95% percentile
bootstrap intervals from 10,000 fixed-seed resamples of paired log ratios.

Oldest workloads repeatedly read seed; newest workloads read the preceding
binding; literal workloads have no local reads in initializers. Counts in labels
are generated declarations, in addition to seed. Mixed has one 8,192-declaration
function followed by 128 functions with 48 declarations each, exercising reused
capacity and function resets. Hello and the actual 67-function bootstrap are
controls. Short CLI timings have wide intervals: those do not prove regression
absence, and no general small-program/bootstrap speedup is established.

| Workload | Baseline median ms | Final median ms | Paired geometric speedup | Individual 95% interval |
| --- | ---: | ---: | ---: | --- |
| hello_check | 1.407 | 1.487 | 0.986x | 0.895–1.091x |
| bootstrap_check | 8.136 | 8.154 | 0.987x | 0.955–1.018x |
| bootstrap_emit_c | 10.102 | 10.031 | 0.989x | 0.952–1.024x |
| oldest_16_check | 1.501 | 1.493 | 0.934x | 0.809–1.075x |
| oldest_16_emit_c | 1.891 | 1.857 | 0.991x | 0.910–1.065x |
| oldest_32_check | 1.692 | 1.716 | 1.014x | 0.919–1.119x |
| oldest_32_emit_c | 1.698 | 1.653 | 1.031x | 0.925–1.147x |
| oldest_33_check | 1.381 | 1.241 | 1.177x | 1.057–1.324x |
| oldest_33_emit_c | 1.533 | 1.538 | 1.020x | 0.881–1.168x |
| oldest_128_check | 1.603 | 1.576 | 0.994x | 0.875–1.127x |
| oldest_128_emit_c | 2.149 | 2.021 | 1.012x | 0.930–1.098x |
| newest_128_check | 1.521 | 1.507 | 1.004x | 0.881–1.140x |
| newest_128_emit_c | 2.006 | 1.958 | 1.042x | 0.931–1.165x |
| literal_128_check | 1.652 | 1.625 | 1.024x | 0.910–1.158x |
| literal_128_emit_c | 1.841 | 1.774 | 1.008x | 0.907–1.118x |
| oldest_1024_check | 6.681 | 3.479 | 1.765x | 1.632–1.897x |
| oldest_1024_emit_c | 11.265 | 5.507 | 2.139x | 2.014–2.285x |
| newest_1024_check | 4.504 | 4.542 | 1.002x | 0.906–1.108x |
| newest_1024_emit_c | 11.140 | 5.084 | 2.161x | 2.069–2.263x |
| literal_1024_check | 3.293 | 2.811 | 1.107x | 1.016–1.208x |
| literal_1024_emit_c | 8.304 | 3.114 | 2.644x | 2.520–2.777x |
| oldest_8192_check | 73.052 | 19.748 | 3.606x | 3.466–3.738x |
| oldest_8192_emit_c | 335.844 | 25.366 | 13.375x | 13.198–13.556x |
| newest_8192_check | 18.567 | 18.607 | 0.998x | 0.984–1.013x |
| newest_8192_emit_c | 407.517 | 23.707 | 16.688x | 16.016–17.303x |
| literal_8192_check | 12.633 | 12.625 | 0.986x | 0.957–1.011x |
| literal_8192_emit_c | 271.517 | 15.735 | 17.490x | 17.167–17.818x |
| mixed_check | 83.009 | 31.820 | 2.612x | 2.559–2.669x |
| mixed_emit_c | 349.452 | 40.428 | 8.653x | 8.551–8.748x |

Reproduce with a new output directory:

```sh
python3 tests/local_lookup_bench.py \
  --baseline /dev/shm/forge-locals-20261015/forge-baseline \
  --candidate build/bin/forge --root build \
  --output /dev/shm/forge-locals-20261015/benchmark \
  --cpu 2 --pairs 24
```

The benchmark uses the existing statistical helper from function_lookup_bench.py;
both script hashes are recorded. The archive contains measured compiler copies,
source, emitted output, commands, samples and an incremental source patch against
the exact pre-change files. The [previous report](function-lookup-2026-10-15.md)
records the baseline's earlier source changes.

## Correctness and verification

The final whole CTest run passes **24/24 suites**. New coverage includes an index
unit with 40,000 deterministic stack operations checked against an independent
reverse scan, deliberate hash collisions, shadowed heads through growth/pop,
forced owner-array movement, freed key buffers before pooled reuse and embedded
NUL equality. Public tests cover promoted shadow types, for-scope restoration,
current initialization/move state, owned-string reinitialization and a suspended
coroutine with many locals.

A separate 60-case corpus compares baseline/current exact JSON diagnostics and
exit status across 0/16/32/33/64/128 padding declarations. All 36 accepted cases
also emit byte-identical C. It includes if/match initialization joins, loop move
reanalysis, moved reads, returning move branches, shadowed ownership, initializer
type errors and a following small function with reused local names.

ASan, UBSan and leak detection pass 14 commands over the unit, check/C-emission
workloads and bootstrap. Owned mailbox payload tests additionally compile and
execute generated C with ASan/UBSan, including an initialized→moved→reinitialized
binding. The current stage1/stage2 chain rebuilds, regenerates stage3/stage4 and
reaches its fixed point. Native cross-OS/real ARM/WASM performance was not measured
for this change.

## Observed failures retained

The first whole CTest run passed 23/24 suites: HTTP hybrid integration observed
ConnectionResetError. An isolated recheck passed, as did the final whole run.
The existing compiler passed 12 repetitions of the serving-modes test; this does
not prove the reset cannot occur there. All five HTTP fixture modes produce
identical C and native binary bytes with either compiler when CC uses the same
source path (different input basenames otherwise change ELF file-symbol metadata).
No generated-code difference explains the observed reset. Its exact root cause
remains unconfirmed, and no blanket HTTP startup-reliability claim follows from
the later passing runs. The failure and rechecks are preserved rather than removed.

An ASan build initially requested a newly added target in the same make invocation
that regenerated its old Makefile; it reported no rule for local_index_test. A
fresh invocation built it and all sanitizer checks passed. This failed build log
is retained and is not counted as a successful check.

## OMO review

Completed design session `ses_ec24ecb1affe9uIsVfAU4At3QW` is identified by the full session
record in the archive. It enumerated every semantic/native stack mutation and
reviewed initializer ordering, snapshots and coroutine preloads. Its initial
codegraph view was stale; it switched to current on-disk source and is labeled an
in-flight design review. Its layout/borrow findings prompted offsetof assertions
and documentation of the short-lived semantic pointer facade.

The broad final request in `ses_ec2457b1affe5HoYo2h66c1Ws0` ended at the reasoning
length limit without a final answer. It is **not** a completed review. A separate,
focused core review in `ses_ec0ec1ce2ffeRRogQAy6g7lO5Q` of the actual local_index.h/common.h finished with no
counterexample under the stated owner/mutation preconditions. It checked bounds,
decreasing links, latest-shadow order, collision rollback, capacity reuse,
activation copies, NUL-compatible hashing and overflow checks. These are
mathematical code reviews, not machine-checked proofs or full language safety
certification. Actual requests, finished findings and the failed attempt are retained.

[Source, measurements and review records](local-lookup-2026-10-15.raw.tar.gz), [checksum](local-lookup-2026-10-15.sha256):

`c9c1ba11025772f692f1634f0891e88f4fcf54d688a2891dc287a5f3261e138d`.
