# OMO invariant modulo review

Subagent session `ses_ecd7948b3ffeUG2Jk1mdbumLiQ`, Sisyphus-Junior. This is a mathematical review, not an audit of the completed scanner implementation.

The general quotient bound/correction proof is valid. One edge-case sentence is wrong: for d=INT64_MAX, q need not be zero whenever n<d. For example n=9223372036854775806, d=9223372036854775807 gives m=3, q=1. The correction subtracts d from product and returns n, the correct remainder. The implementation retains that correction, so this error in the review does not invalidate the algorithm. Eager preparation is guarded by divisor > 1 in the emitted helper; empty-loop regressions check that zero divisors do not trap without an actual remainder operation.

## Original subagent response

**Verdict: the algorithm is exact on the full stated range; no counterexample exists.**

**(a) m = ⌈2⁶⁴/d⌉.** For integers X,d>0, ⌊(X−1)/d⌋+1 = ⌈X/d⌉ (split on X mod d = 0 vs >0). With X = 2⁶⁴: if d = 2^k divides 2⁶⁴, ⌊(2⁶⁴−1)/d⌋ = 2⁶⁴/d − 1, so m = 2⁶⁴/d = ⌈2⁶⁴/d⌉ exactly. Hence 2⁶⁴/d ≤ m < 2⁶⁴/d + 1, and d ≥ 2 gives m ≤ 2⁶³, so m fits uint64.

**(d) No overflow.** n·m ≤ (2⁶³−1)·2⁶³ = 2¹²⁶ − 2⁶³ < 2¹²⁸, so the uint128 product is exact. From 2⁶⁴/d ≤ m < 2⁶⁴/d + 1: n/d ≤ n·m/2⁶⁴ < n/d + n/2⁶⁴ < n/d + 1 (since n ≤ 2⁶³−1 < 2⁶⁴).

**(b) q ∈ {⌊n/d⌋, ⌊n/d⌋+1}.** Writing x = n·m/2⁶⁴, floor(x) ≥ ⌊n/d⌋ from x ≥ n/d, and x < n/d + 1 forces floor(x) ≤ ⌊n/d⌋ + 1. Bounds for product: with n = ⌊n/d⌋d + s, 0 ≤ s < d, q·d ≤ (⌊n/d⌋+1)d = n − s + d ≤ n + d ≤ (2⁶³−1)+(2⁶³−1) = 2⁶⁴ − 2 < 2⁶⁴. So product = q·d exactly, never wraps.

**(c) Correction.** If q = ⌊n/d⌋: product = n − s ≤ n (also when s = 0), guard false, return n − (n − s) = s = n%d. If q = ⌊n/d⌋+1: product = n − s + d > n (because s < d), guard fires, product = n − s, return s. Guard fires iff q = ⌊n/d⌋+1 (product ∈ {n−s, n−s+d} and only the latter exceeds n); one subtraction suffices since the next value n − s ≤ n.

**(e)** n ≥ 0, so conversion of signed n to uint64 under usual arithmetic conversions is value-preserving; `product > n` is well-defined unsigned comparison.

**(f) Edges.** n=0: q=0, product=0, return 0. n=d: n/d=1 and q ≤ 2 would need m > 2·2⁶⁴/d, impossible since m < 2⁶⁴/d + 1 ≤ 2·2⁶⁴/d for d ≤ 2⁶⁴; so q=1, product=d=n, return 0. n = 2⁶³−1, d=2: m=2⁶³, q = 2⁶²−1 = ⌊n/d⌋, return 1. d = 2⁶³−1: m = ⌈2 + 2/(2⁶³−1)⌉ = 3; 3n < 2⁶⁴ for all n < 2⁶⁴/3, so q=0 for n<d (return n); n=d gives q=1, return 0. Powers of two covered by (a).

**Precondition review.** The caching rule (parameter never assigned nor shadowed ⇒ may be cached) guarantees only *value invariance* of d; it does not make the guarded division speculatable. Trap-safety comes solely from the `d > 1` guard: if m is computed with d=0 that is unsigned division by zero (trap); negative d would not trap (converts to a huge uint64) but yields a wrong m. The precondition is therefore coherent and sufficient **only under the reading that the guard control-flow-dominates the hoisted computation** (guard and computation hoisted together, or prep placed inside `if (d > 1)`). Hole: if "guarded" means merely a per-iteration loop condition while m is prepared before the first test, a zero-trip run evaluates `UINT64_MAX/d` with d=0 and traps — the caching rule does not prevent this. As written it states the guard exists, so it is acceptable, but the caching rule alone is insufficient; sufficiency rests entirely on the dominating-guard clause.
