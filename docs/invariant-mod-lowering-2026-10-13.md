# Invariant integer remainder lowering

The native compiler now prepares an exact reciprocal once for an immutable
integer parameter used as a divisor in a loop. The emitter rejects any
assignment or shadow binding anywhere in the function, including before and
after the loop; move/receive/yield/await paths and exhausted scan budgets fail
closed. A separate 65,536-visit budget bounds the analysis, with at most eight
descriptors per function. Generated local names are checked against parameters,
function symbols and body references/bindings. Unknown operand types keep the
existing checked remainder. Native, library and file-module functions share
this rule; coroutine storage/resume paths do not use it.

The optimization preserves wrapping multiply/add, signed remainder, single
operand evaluation and the existing zero / INT64_MIN%-1 error contract. It
changes arithmetic lowering, without adding a prime algorithm to the runtime
or changing the matched Forge/Rust fixture algorithms.

## Exact arithmetic and guard

For 0 <= n <= INT64_MAX and 1 < d <= INT64_MAX, prepare
`m = UINT64_MAX / d + 1 = ceil(2^64/d)`. Let `q = floor(n*m/2^64)` using the
high half of an unsigned 128-bit product. Because the reciprocal error is less
than one, q is floor(n/d) or one larger. The product q*d fits uint64:
`q*d <= n+d <= 2^64-2`. If q*d exceeds n, subtract d once. The resulting
`n-product` is exactly n%d and is smaller than d, so its signed conversion
is representable. n=0 gives q=0 directly.

The preparation itself keeps its `divisor > 1` guard, even when a loop runs
zero times. It cannot evaluate a zero-divisor division speculatively. Negative
dividends or divisors <=1 use the original checked signed helper. Targets
without `__SIZEOF_INT128__` use that helper throughout; this is a portability
fallback, not proof of equal performance on those targets. GCC documents
128-bit integers as a target-dependent extension in its [primary manual](https://gcc.gnu.org/onlinedocs/gcc-12.1.0/gcc/_005f_005fint128.html).

An OMO Sisyphus-Junior mathematical audit confirmed the quotient/correction
bound and stressed the dominating guard requirement. Its special-case claim
that q is always zero for n<INT64_MAX when d=INT64_MAX was wrong: n=INT64_MAX-1
gives q=1, and the correction still returns the correct n. That review error
is explicitly recorded and corrected in [the saved audit](invariant-mod-omo-review-2026-10-12.md). The audit does not replace the implementation regressions.

## Validation

The arithmetic suite checks full-width positive/negative inputs, divisor
mutation before/during/after a loop, nested shadowing and for-initializer
shadowing, zero-trip loops with exceptional divisors, private-name collisions,
and single evaluation through a counting FFI call. Native tests use UBSan at
-O0 and -O3, with JavaScript comparisons and an explicit no-int128 fallback.
The actual emitted helper additionally passes 100,000 random oracle cases
at each optimization level. The standalone prototype passes 301,169 signed-%
oracle cases in each of three builds (-O0, -O3 and no-int128 fallback), plus
exception checks. All 22 CTest suites are covered, including 28 arithmetic
unit tests. Logs and exact inputs are archived with the snapshots.

## Matched compiler comparison

Both Forge and Rust use the same 3/5 small-prime prefilter and the same
Miller–Rabin/fallback algorithm. Compiler variants share identical SDK archives,
installed headers, Forge/Rust source fixtures and clock implementation. The
baseline is Forge 9f70e9d. No Forge-specific algorithm change weakens the Rust
control. The first full comparison uses 60 position-balanced groups; the
independent-seed repeat uses 120 groups with the same frozen binaries.

| Workload | Candidate / Rust | Row-wise paired 95% interval | Candidate / baseline Forge | Paired 95% interval |
| --- | ---: | --- | ---: | --- |
| LCG | 1.5024 | 1.4996–1.5061 | 0.9984 | 0.9968–0.9994 |
| primes | 1.5616 | 1.5408–1.5752 | 1.5272 | 1.4848–1.5344 |
| scan | 2.2639 | 2.2523–2.2712 | 1.1634 | 1.1606–1.1727 |
| builder | 1.2148 | 1.1358–1.2764 | 1.0725 | 1.0481–1.1063 |
| immutable | 13.1377 | 11.3787–17.1067 | 1.0009 | 0.9733–1.0227 |

Every row's 95% lower bound exceeds 1.10 in this 120-group run. The prior
60-group builder interval was 1.0185–1.1568 and crossed the threshold, so
stable cross-run builder support remains to be established. Intervals are
per row, not simultaneous family-wise guarantees. LCG has a small ~0.16%
measured regression; immutable's direct baseline comparison includes no
change. The generated bodies of LCG/pattern/weighted/scan/builder/immutable
are unchanged, while the compiled whole binary changes. Do not attribute
all incidental code-layout or inlining effects to a direct modulo rewrite
in those other functions; the timing cause has not been isolated.

The 120-group run retains 99 correctness checks, 1,800 prewarms and 1,800
measurements, all matching the independent reference. [60-group report](invariant-mod-compiler-full-2026-10-12.md), [120-group report](invariant-mod-compiler-full-120-2026-10-12.md), and [prototype screening](invariant-mod-reciprocal-prime-probe-2026-10-12.md) preserve the raw paired observations.

This is Linux evidence for finite CPU/string fixtures. Immutable append still
compares different allocation/lifetime policies, and these runs do not establish
a language-wide ratio, HTTP capacity or performance on another OS. The active
objective retains cross-run validation and the requested macOS/Windows
measurements.

The implementation is committed as Forge `9e6bf6f`. Its current compiler
binary matches the frozen benchmark compiler byte-for-byte; re-emitting the
fixture also matches the measured generated-C hash. [Frozen binaries, SDK
inputs, runner versions and test logs](invariant-mod-compiler-2026-10-13.raw.tar.gz)
are preserved with SHA-256
`fdf5775056ac4071787c66fab5663c3f05f14347f73dc407bc75232726868dc3`.

## Throughput units

Each rate is n × rounds divided by the implementation's median kernel elapsed time. These are completed workload input units, not instructions per second or concurrent-user capacity. Builder includes construction and checksum scanning; immutable counts final output bytes and includes append/snapshot behavior. Ratios of separate medians differ from the paired ratio medians above.

| Workload | Unit | Forge / second | Rust / second |
| --- | --- | ---: | ---: |
| lcg | LCG updates/s | 394,140,496 | 262,204,918 |
| primes | Primality decisions/s | 24,493,935 | 15,679,787 |
| scan | Input bytes scanned/s | 1,762,271,371 | 778,834,623 |
| builder | Finished input bytes/s | 420,558,846 | 353,614,591 |
| immutable | Final output bytes/s | 273,211,366 | 21,202,001 |
