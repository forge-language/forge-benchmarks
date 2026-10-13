# OMO range-kernel proof audit and corrections

Same delegated Sisyphus-Junior worker `ses_ecce1af5bffelUJqkHCnD5cHJ5`, model `opencode/mimo-v2.6-flash-free`; bounded read-only arithmetic specification review, no file reads, execution or edits. Its conclusion supports the guarded equivalence but includes incorrect examples/wording, corrected below. This review supplies no speed evidence and is not a compiler implementation audit.

Corrections:
- The masked low part of an LCG product is at most M (not M-1), so folded<=M+48270<2M. One conditional subtraction is still sufficient.
- n<=0 with rounds>0 still executes the original outer loop; only inner work is zero and the returned seed is unchanged. Each outer increment remains guarded by r<rounds<=INT64_MAX.
- Modular decomposition stops at a positive odd d, not necessarily 1 (value=7 gives d=3 after one shift).
- Forge's checked zero-divisor fallback exits with its division diagnostic; it does not intentionally execute undefined C modulo or promise SIGFPE.
- value=0,base=1 returns 1 at base>=value, rather than trapping. A retained trap example is value=0,base=-1, which reaches the checked initial modulo. The original value=1,base=0 nontermination is excluded from executable cases and remains outside the prefix guard.

The independent Python/UBSan test checks 311 cases in each of four original/candidate optimization configurations. The guarded mathematical equivalence does not depend on the incorrect illustrative sentences above. All target ranges/products remain valid; no implementation is adopted on this proof alone.

## Recorded worker response

**1. LCG — holds.** With `0<=seed<M` and inductively `v∈[0,M)`: product `v*48271 ≤ (M-1)*48271 < 2^47`, so the uint64 product is exact (no 2^64 wrap) and the original signed product never overflows int64 — `wrap_i64` is the identity there. Writing `p = q·2^31 + r`, since `2^31 ≡ 1 (mod M)`, `p mod M ≡ q+r (mod M)`. Bounds: `q ≤ 48270`, `r ≤ M-1`, so `q+r ≤ 2147531917 < 2M`: one conditional subtraction is necessary and sufficient, and the result lands in `[0,M)`. Small check: v=1 → q=0, r=48271 < M → 48271, matching `48271%M`. Guard-failing seeds (e.g. seed=−1, where C truncation yields a *negative* remainder, or seed≥M) take the exact old body, so that behavior is retained verbatim. Nonpositive `n`/`rounds`: condition false at r=0/i=0, increments never execute — no UB, matching the original while-loops. When the loop does run, increments occur only for `i<n≤INT64_MAX`, so `i+1 ≤ n` fits. Caveat: equivalence assumes identical iteration counts and initial `v=seed`, as the specification states.

**2. Modular power — holds.** `3037000499² = 9223372030926249001 < 2^63−1` (3037000499 = ⌊√2^63⌋), and under the guard `result,factor ≤ modulus−1 ≤ 3037000498`, so both `result*factor` and `factor*factor` are ≤ that square: **no wrap occurs**, original `wrap` is identity, and uint64/signed products agree exactly. Nonnegative operands make truncating `%` and unsigned `%` equal, and `power/2` ≡ `power>>=1`, `power%2==1` ≡ `power&1` for `power≥0`. `exponent=0`: both compute `base%modulus` (defined: `base≥0`, `modulus>1`) and return `1`. Guard failures — `modulus≤1` (0 → original SIGFPE on `%`, preserved by fallback), negative base/exponent/modulus, `modulus>3037000499` (where signed square can wrap) — all take the exact old body.

**3. Miller–Rabin — holds.** `value∈(1,3037000499]` gives `d = value−1 ∈ [1, 3037000498]`, always positive; halving stops at odd 1, never reaching 0, and `d>>=1` equals `d/2` on even positives. `s ≤ 31` (value−1 < 2^32), so `s+1`/`r++` are overflow-free, and `for r=1;r<s` runs ≤30 times. `x∈[0,value−1]` from the guarded modpow (its guard is implied: `base<value`, `d≥0`, `1<value≤3037000499`); squares satisfy `x² ≤ 3037000498² < 2^63`, so wrap is identity and unsigned squares match. `x=0`: `0≠1`, `0≠value−1≥1`, squares stay 0 → `return 0`, identical in both. `value=2`, `base=0` works out the same. Guard failures retain original pathologies exactly: `value=1, base=0` → infinite `d/2` loop; `value=0, base=0` → passes `base≥value` (0≥0) actually returns 1; `value=0, base=1` → `%0` trap in original modpow — fallback preserves both.

**4. Weighted scan — no gap.** Unroll hints are non-semantic; with no independence assertion the compiler must preserve loop-carried dependencies. No vectorization, throughput, or trip-count-multiple claim is made or implied.

**Verdict: no mathematical or semantic gaps; no counterexamples.** All shared arithmetic is defined (uint64 or proven-overflow-free signed), and every guard-failing class executes the byte-identical original body.
