# OMO periodic scan and positive remainder review

Same delegated Sisyphus-Junior worker ses_ecce1af5bffelUJqkHCnD5cHJ5, read-only bounded mathematical specification audit; no files, executions or edits. It supports the reciprocal/cyclic-weight proof under the explicit guards. This is not a compiler implementation or performance review.

The worker flags that original n must equal view.len. That obligation holds in the actual fixture: weighted sets n=fr_str_view_len(view), and the current standard API/header returns the cached view length. The prefix admits only len<=INT64_MAX, so conversion is exact and count=n. It rejects null handles/data and larger lengths to the unchanged body. Borrowed data remains immutable/live; neither loop contains a reset/callback.

The product proof should use the conservative non-strict bound q*d<=n+d<2^64; the worker's intermediate strict inequality does not follow directly when n mod d=0. This does not weaken the nonwrapping proof or exact one-correction result. Private helper calls are guarded to nonzero d and n<=INT64_MAX.

The scan sum equivalence is modulo 2^64, even for an enormous valid input; that proof is algebraic, while executable tests cover feasible block/tail boundaries and full-byte data. No unsupported claim of a throughput improvement follows from the audit.

## Recorded worker response

**1. Reciprocal remainder helper — correct under the stated guards.**

Let `m = ceil(2^64/d)` (for `d=2`: `floor(UINT64_MAX/2)+1 = 2^63`). Since `n ≤ 2^63−1` and `m < 2^64/d + 1`:

- `n·m ≥ n·2^64/d`, so `q = ⌊n·m/2^64⌋ ≥ ⌊n/d⌋`.
- `n·m/2^64 < n/d + n/2^64 < n/d + 0.5`, so `q ≤ ⌊n/d⌋ + 1`. Hence **q is exact or one high**; never two.
- The 128-bit product itself: `m ≤ 2^63+1`, `n ≤ 2^63−1`, so `n·m < 2^126 + 2^63 < 2^128` — no 128-bit wrap.
- `product = q·d ≤ (⌊n/d⌋+1)·d = n − (n mod d) + d < n + d ≤ 2^63 + 3.04e9 < 2^64` — **never wraps**.
- One correction suffices: if `q` exact, `product ≤ n`, no subtract. If `q = ⌊n/d⌋+1`, then `product = n − (n mod d) + d > n` (since `n mod d ≤ d−1 < d`), the subtract fires, and `product − d = ⌊n/d⌋·d ≤ n` — **final remainder exact**, `n − product = n mod d ≥ 0`.

Boundaries: `n=0` → `q=0`, `product=0 ≤ n`, returns 0 ✓. `n=MAX, d=2` → `m=2^63`, `n·m = 2^126 − 2^63`, `q = 2^62 − 1 = ⌊n/2⌋`, `product = 2^63−2 ≤ n`, result 1 ✓. `n=MAX, d=3037000499` is covered by the general bounds. Negative/zero `d` and negative `n` cannot enter (guard), removing div-by-zero and signed-UB; excluded classes take the exact original checked body. The `n%d` fallback needs only `d ≥ 2` (nonzero) — same value.

**2. Weighted byte sum — correct, with one required precondition.**

Weight evolution has period 13: original weight at index `i` is `((w−1+i) mod 13)+1`. Under the guard `w>0`: `w = offset%13+1`; if `offset ≥ 0`, `w ∈ [1,13]`; if `offset < 0`, `offset%13 ∈ [−12,0]` gives `w ≤ 0` **except** `13 | offset` where `w = 1`. So guard-passing implies `w ∈ [1,13]` exactly. (E.g. `offset=−13` passes with `w=1` — still in range, so no false accept.)

Precompute: `w+j ≤ 25 < 26`, so one conditional subtraction yields `((w+j−1) mod 13)+1 ∈ [1,13]` — valid weight. Phase continuity: outer loop keeps `i ≡ 0 (mod 13)`, inner index `13k+j` uses `weights[j] = ((w−1+13k+j) mod 13)+1` ✓; after `i+=13` the invariant holds. Tail starts at `i = 13k`, `j=0`, `weights[0]=w` matches position `13k`; `j` advances with `i`, so `weights[j]` matches position `13k+j`.

Bounds: `count−i ≥ 13` (evaluated with `i ≤ count`, no uint64 underflow) gives `i+12 ≤ count−1` — all accesses in-view; tail entered only when `count−i < 13`, so `j ≤ 11 < 13`, indices and `weights[12]` never exceeded. Multiplication: `byte ≤ 255`, weight `≤ 13`, product `≤ 3315` — no wrap. Sum: both paths add identical nonneg terms modulo 2^64 (`wrap_i64` ≡ mod 2^64), so for arbitrarily large valid `n` the bit patterns coincide step-by-step; `memcpy` reinterpretation equals `wrap_i64`. Guard failures (null data, `len > MAX`, `w ≤ 0` from negative `offset` like `offset=−1`) take the exact original body.

**Flag — one precondition, not yet in the stated guard:** equivalence requires the original loop bound `n` to equal `len`. The new path uses `count=len`; if `n < len` the fast path sums extra terms (concrete: `n=2, len=3` → 2 vs 3 addends), and if `n > len` the original itself reads out of bounds (shared UB — never acceptable). If `n ≡ len` structurally in this prototype, there is **no counterexample**.

Prior-audit corrections (fold `< 2M`, `n≤0` returns seed, value 7 stops at 3, checked-exit1 traps, `value=0, base=1 → 1`, `value=0, base=−1 → original trap) are consistent with my earlier bounds.
