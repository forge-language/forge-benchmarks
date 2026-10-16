# Signed wrapping modular power: mask lowering

Stage0 now lowers a proven pure binary-exponentiation function with a positive
power-of-two divisor through signed wrapping mask reductions. On this Linux
machine, five focused power-of-two workloads improved by **2.11–2.96x** over
compiler `a750b60923bcc71adda025596664dd9a0413f80b`. These are kernel measurements,
not a language-wide or cross-platform speed claim.

## Implementation and equivalence

The existing AST/binding matcher remains responsible for recognizing the entire
pure function: three integer bindings, the exact bit/product/square/halving loop
and a return of its result. Calls, observers, extra statements, live final factor
or exponent, and suspended-coroutine bodies remain excluded. Matching is
independent of function and parameter names. The new `mask` temporary participates
in the same bounded collision search as the other generated names.

The mask path runs before the existing reciprocal path. Its guard requires
`d > 1`, `d & (d-1) == 0` and a positive exponent. The first condition makes the
guard's signed `d-1` safe through C short-circuiting. A positive int64 power of two
is at most 2^62, so it divides 2^64. Negative bases are supported, and this path
does not require int128. Zero/negative exponents and invalid divisors retain the
original paths, including the trapping initializer for zero or `INT64_MIN / -1`.

For a wrapped signed value with unsigned bits `u`, let `r = u & (d-1)`.
Because d divides 2^64, r is its nonnegative mathematical residue. Forge's
truncating remainder is r when the signed value is nonnegative or r is zero;
otherwise it is `r-d`. The implementation stores those bits with unsigned
subtraction and converts only the final result with `__forge_i64_bits`.
Each product uses uint64 multiplication, preserving the low 64 bits before
reduction. Induction therefore preserves both recurrence states, including
negative remainders after overflow. For example, with `a=2^62-1`, exponent 2 and
`d=2^62`, the source returns `-2^62+1`; an unsigned-only mask would incorrectly
return 1.

The initial odd-bit multiply by one is redundant because the initial factor is already a
remainder. The last square is dead and cannot trap: this guard excludes both
invalid divisors, and wrapping multiplication itself cannot trap. The matcher
excludes observers of those intermediate operations. The existing small-modulus
reciprocal algorithm and the original checked fallback are retained.

## Measurement

CPU: AMD BC-250, Linux 6.8.0-139-generic, x86_64, glibc 2.39, GCC 13.3.0.
Both compilers emit unmodified C for the same exported Forge function. Its object
is compiled separately from the C driver at `-std=c11 -O3`, without LTO, so the
driver cannot propagate constant inputs into the function. Both link the same
SDK: runtime `dcbb1929b17c2f1d11fd367ecf80c7c87c58a274`, stdlib
`6aa28667b83009a415ab2d7ac13ef6c675af7012`.

Each sample makes 1,048,576 calls over 64 deterministic input triples with odd
positive 31-bit exponents. Each row has 24 alternating AB/BA pairs after one
warmup per executable. Processes inherit affinity to CPU 2; this is affinity,
not exclusive reservation of that CPU. Elapsed time includes process startup.
Every run's checksum is checked against an independent Python oracle that uses
signed division and explicit wrapping. Exact per-input checking is provided by
the arithmetic regression suite below.

| Workload | Baseline median ms | Candidate median ms | Paired geometric speedup | Individual 95% bootstrap interval |
| --- | ---: | ---: | ---: | --- |
| Existing mixed small divisors | 116.082 | 106.619 | 1.089x | 1.086–1.093x |
| Small powers of two | 117.462 | 55.940 | 2.110x | 2.082–2.138x |
| Small powers, negative bases | 146.658 | 59.224 | 2.460x | 2.443–2.474x |
| Large odd divisor fallback | 133.249 | 133.002 | 0.997x | 0.990–1.004x |
| Powers 2^22 through 2^31 | 133.022 | 53.106 | 2.498x | 2.481–2.514x |
| Powers 2^32 through 2^62 | 160.839 | 53.904 | 2.957x | 2.919–2.992x |
| Wide powers, negative bases | 154.595 | 58.623 | 2.602x | 2.558–2.636x |
| Large wrapping divisor fallback | 138.095 | 138.295 | 0.998x | 0.994–1.001x |

Intervals resample paired log speed ratios 10,000 times with a fixed seed. They
are row-wise intervals, not simultaneous guarantees, and do not remove host
interference or possible serial correlation. No speedup is established for the
guard-miss rows. The emitted function object's `.text` grew from 731 to 963 bytes
on this toolchain; the new dispatch and code size are costs of the optimization.

The compiler binaries used for these measurements have SHA-256:

- Baseline: `ce64344f51b2d7c0018a9565c372ec5a3820d0c3537e6497c921fc58575442c1`.
- Candidate: `b1ce9f632e293176893b32cc6e677ec804c29a39b967badf1e2744d78861d22b`.

Actual command, after copying the original compiler before editing:

```sh
python3 tests/modular_power_bench.py \
  --baseline /tmp/forge-perf-20261015/forge-baseline \
  --candidate build/bin/forge --root build \
  --output build/modpow-mask-final-20261015 --cpu 2 --pairs 24
```

Use a new output directory for a rerun. To rebuild the baseline independently,
extract commit `a750b60` into a separate source directory and build its `forge`
target in Release mode against the same runtime and stdlib checkouts. The script
retains compiler snapshots, generated C, drivers, commands, hashes and raw samples.

## Rejected experiments

A wider reciprocal kernel with one quotient correction was correct on its test
vectors but measured about 0.984x in its 22-bit group, with no useful benefit in
the other wider groups. It was removed.

A handwritten Montgomery prototype initially appeared faster on mixed groups
that also included powers of two. Odd-only comparisons exposed 0.934–0.938x
speed ratios. That prototype was also rejected; its source and observations are
retained as prototype evidence. Only the mask transformation was adopted. This
distinction follows the [design principles](../../../forge/docs/design-principles.md).

## Correctness and build verification

All 22 CTest suites pass, including 40 compiler and 38 arithmetic test methods.
The modular-power coverage includes 1,632 full-width/guard-boundary vectors,
189 additional bounded vectors and 866 signed/wrapping power-of-two vectors.
They compare native output at O0/O3 with UBSan and JavaScript against independent
Python arithmetic. Native no-int128 builds cover all three matrices; the full-width
matrix also runs with the ARM macro forced. These are local semantic checks,
not measurements on real ARM hardware. Existing initial-trap tests, module and
exported-library entry points, coroutine rejection, observer rejection and bounded
name-collision tests remain in the suite. Exported-library cases now include
negative wide power-of-two results, and a live mask-name collision is tested.

Verification also exposed an existing CMake dependency gap: custom target names
ordered stage1/stage2/verification without invalidating their output files when
the upstream compiler changed. Stage1 was current while stage2 still dated from
October 13. File dependencies now connect both stages, self-hosted examples and
the fixed-point check; intermediate generated files are declared as byproducts.

The current stage2 was rebuilt, stage3/stage4 regenerated and their C output
compared successfully. A real incremental build experiment touched stage1 and
verified that stage2, both examples and the fixed-point output regenerated; touching
stage2 regenerated its consumers. An unchanged followup build regenerated nothing.
The self-host regression suite was rerun against the rebuilt stage2. Earlier
successful checks against stale artifacts are not used as current-stage evidence.

## Independent review and raw evidence

OMO session `ses_ec28066a1ffe43dbLKj5gzp1YG` completed a read-only review of the
final mask implementation. It independently derived the signed-remainder lemma,
recurrence equivalence, unsigned subtraction safety, guarded `d-1` safety and
trap preservation. It found no counterexample for the final implementation.
This is an independent mathematical code review, not a machine-checked proof.

The initial coordinator failed because its selected model was unregistered.
An attempted final-mask review on another provider encountered repeated API
connection failures and was stopped, then retried on the working provider.
Two older OMO reviews requested for the discarded reciprocal proposal were
stopped after the focused final-mask review completed. Their partial work is
retained but is not counted as completed review. The CLI also fell back from a
requested subagent name to a primary agent for those older requests; the record
does not claim completed delegated children.

Source snapshots, exact commands, executable measurements, rejected prototypes,
validation logs and actual OMO requests/outcomes are retained in the raw evidence
archive linked below. The benchmark is reproducible with
[`tests/modular_power_bench.py`](../../benchmark/compiler/modular_power_bench.py).

[Raw evidence archive](modular-power-mask-2026-10-15.raw.tar.gz), [checksum](modular-power-mask-2026-10-15.sha256):

`88ce63c282d40d625566a2baaf804c71043268082fcad93f004e8431edf0d1ce`.
