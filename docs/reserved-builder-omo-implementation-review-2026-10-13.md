# OMO implementation review: reserved builder lowering

Delegated worker: `ses_ecce1af5bffelUJqkHCnD5cHJ5`, agent `Sisyphus-Junior`, model `opencode/mimo-v2.6-flash-free`. Read-only inspection of compiler patch `d4c632b` and the current SDK `forge-stdlib/src/string.c` / `include/forge/detail/string_views.h`; no edits or test execution. The completed worker found no correctness/security blockers in the narrow matcher/emitter contract. Runtime checks and performance measurements are independently recorded in the lowering report.

A CLI continuation selected the primary agent and repeatedly inspected an obsolete `build/_deps` checkout. That continuation was stopped for the evidenced wrong source path. The same delegated worker was resumed via the OMO server with exact current SDK paths and completed the implementation inspection as Sisyphus-Junior. Its full captured message history is [preserved here](reserved-builder-omo-implementation-review-2026-10-13.json), including the incomplete continuation; no second worker was created.

## Audit corrections and limits

The initial abstract review incorrectly suggested shared undefined overflow could be acceptable and that a per-append terminator would not fit cap>=n+1. Defined Forge wrapping is mandatory, and that terminator would fit. These corrections were supplied before implementation review. The final review's practical statement that an n=INT64_MAX allocation must fail is not a proof assumption: if a valid allocation did exist, guard cap>n and the integer-loop bounds would still prove all stores, the terminator and the last increment safe. The implementation retains the checked path if allocation fails.

The review assumes valid standard API handles and the existing arena lifetime contract. It does not prove arbitrary foreign code interposition, forged handles, concurrent mutation, other compiler backends, all CPU models or speed. Original tests and paired native reports provide the stated validation evidence; the worker itself ran none.

## Recorded worker conclusion

**Verdict: no correctness or security blockers in the reserved-builder matcher/emitter (patch d4c632b).** Verified against `forge-stdlib/src/string.c` and `detail/string_views.h`.

**Why equivalence holds.** `with_capacity(n)` (n≥1) sets `cap = n+1`, `len=0`, fresh buffer (`string.c:79-90`); allocation failure returns 0, caught by the source `if(b==0)` guard. The emitted runtime guard (`data && len==0 && cap > (uint64_t)bound`, short-circuit ordering puts `bound>0` before the cast, and `descriptor` first) therefore implies `cap ≥ n+1`, `len=0`, `data` live. Under that:

- In-bounds: writes touch `data[0..n-1]`, `finish_take` needs `len < cap` for the terminator byte — `n < n+1` holds, so both paths produce byte-identical output, neither writes NUL mid-loop, `finish_take` writes it identically.
- No allocation/failure divergence: per-append reserve needs `len+2 ≤ n+1 ≤ cap` (and the inline `cap-len>1` test holds at every `len≤n-1`), so original `builder_char` never fails, never grows — dropping the per-iteration `==0 → return ""` is exact. Bytes are proved in 1..127 ⊂ [1,255], so the API's `ch<=0||ch>255` rejection is unreachable; range proof fails closed on ADD overflow and on any MOD/dividend (`|rem|<26` holds for wrapped `FORGE_ADD` dividends).
- n≤0: `with_capacity(n<0)` returns 0 (early return); n=0 gives `bound>0` false; fallback runs zero iterations — identical. n=INT64_MAX: 2^63-byte allocation fails → early return, loop unreachable. Increment `i+1` is C-defined (`i<n≤INT64_MAX`), matching `FORGE_ADD` where no wrap occurs; fallback and fast path emit the same statement (`safe_increment=step`).

**Aliasing/scope.** The AST shape is strict: construction → optional single `return ""` guard → `i=0` → `while(i<n)` with body exactly [`builder_char(b,expr)==0 → return`, `i=i+1`], bound ident *is* the capacity argument. Any `let alias=b`, reassignment of `n`, extra call, break, or shadowing decl breaks the shape and falls back (tests cover these). The byte expr admits only INT/IDENT/BINARY (no calls), so nothing can read `builder->data`/`len` or mutate state inside the fast block; descriptor/data are cached in an inner block after the window in which `b` could change (there is none). Layout `{data,len,cap}` matches ABI `str_builder_t` (`string_views.h:13-17`). Synthesized names use `label_seq` uniqueness and are checked against locals and functions (collision test covers the before-declaration case; later outer-scope decls cannot conflict with the closed inner block).

**Exclusions/bounds.** `!in_coro && !state_prefix` gates matching; coroutine state emission and `yield` bodies cannot enter. Depth≤64 and `loop_scan_left` budget fail closed (exhaustion only loses the optimization).

**Scope limits (not blockers):** native backend only (JS untouched); read-only audit — tests/builds not run; assumes `forge_std_c_name` cannot map a user function onto the stdlib C symbols with different semantics (a trust assumption shared with the pre-existing view-append path); assumes the single-threaded, arena-valid-until-reset handle contract (no concurrent mutation/signals — none exist in the language model); relies on builder-struct ABI stability noted in the header comment.
