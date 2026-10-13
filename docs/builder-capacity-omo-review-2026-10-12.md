# OMO builder capacity review

Subagent session: `ses_ecd853c54ffeEKpeykawESlipX`. The source was edited and restored during the audit; snapshot hashes in the benchmark report define the measured candidate and baseline. The mathematical proof is valid over API-created builder states; timing was established independently and the candidate was rejected.

Audit complete. All facts verified against the on-disk sources (`test -r` passed for both files; no edits, builds, or benchmarks run).

**Files readable:** yes — `forge-stdlib/include/forge/string.h` (128 lines) and `forge-benchmarks/benchmark/cpu/kernels.fg` (58 lines). Fallback expression not needed.

**Current expressions found**

- [string.h:94](/home/helloworld0822/coding/forge-stdlib/include/forge/string.h:94) in `fr_detail_str_builder_char` (lines 88–99): `if (builder->cap - builder->len > 1) {` — the live source already uses the short form; the redundant two-conjunct form `builder->cap > builder->len && builder->cap - builder->len > 1` exists only in the task's fallback text, not in the file.
- [kernels.fg:22](/home/helloworld0822/coding/forge-benchmarks/benchmark/cpu/kernels.fg:22) in `pattern`: `while(i<n){if(str_builder_char(builder,65+(i+seed)%26)==0){return "";}i=i+1;}`.

**Verified types:** `cap` and `len` are `size_t` (unsigned) per [string_views.h:17](/home/helloworld0822/coding/forge-stdlib/include/forge/detail/string_views.h:17) (`typedef struct { char *data; size_t len, cap; } fr_detail_str_builder;`; `str_builder_t` is an alias, [string.c:18](/home/helloworld0822/coding/forge-stdlib/src/string.c:18)). `handle` and `ch` are `int64_t` ([string.h:88](/home/helloworld0822/coding/forge-stdlib/include/forge/string.h:88)). Forge `%` is C truncated-toward-zero remainder: `__forge_mod_i64` is `return a % b;` on `int64_t` after zero/overflow checks ([codegen.c:2149](/home/helloworld0822/coding/forge/compiler/codegen.c:2149)).

**The one proposed optimization** (spare-capacity check; verbatim replacement):

```
if (builder->cap - builder->len > 1) {
```

replacing

```
if (builder->cap > builder->len && builder->cap - builder->len > 1) {
```

**Correctness proof, invariant by invariant**

- Byte rejection, null-builder rejection, growth path, arena lifetimes, immutable snapshots, NUL reservation: the proposal changes only the capacity predicate; the `!builder || ch <= 0 || ch > 255` → 0 check, the store `builder->data[builder->len++] = (char)ch` (single in-place write through the existing pointer, before the increment, never past committed bytes), the `return handle`, and the slow-path `fr_str_builder_char(handle, ch)` call are textually untouched, so every listed invariant is preserved verbatim.
- Redundancy evaluation: with `size_t` arithmetic and the API invariant `len <= cap` (documented at [string.h:91–93](/home/helloworld0822/coding/forge-stdlib/include/forge/string.h:91); maintained by `fr_str_builder`/`with_capacity`/`builder_reserve`/`finish_take`, which zero both fields together), `cap - len` is in `[0, cap]` and cannot wrap. If `cap == len`, `cap - len == 0`, not `> 1`, so the second conjunct alone already rejects exactly when the first conjunct is false; when `cap > len`, the first conjunct is true and the outcome is decided entirely by the second. The first conjunct is therefore fully redundant — no unsigned-underflow concern arises for the short form *because* of the invariant (if `len > cap` ever occurred, unsigned wrap would make `cap - len` huge and wrongly pass, which is precisely why the invariant is load-bearing; it holds for all API-created builders).
- Why faster: one fewer compare-and-branch per capacity check. Honest status: this reduction is **already applied in the live tree** — [string.h:94](/home/helloworld0822/coding/forge-stdlib/include/forge/string.h:94) is already exactly the proposed expression, so against the real source this is a no-op (the compiler sees identical code); it is a real one-branch win only relative to the long fallback form.

**Generated arithmetic in `pattern` — evaluated, no second proposal**

The textbook strength reduction (precompute `ch = 65 + seed%26`, then `ch = ch + 1; if (ch > 90) ch = 65;`) is **not** semantics-preserving and is rejected. The valid-but-slower rewrite `let a: int=seed; ... 65+a%26 ... a=a+1` is exact for all seeds (the induction variable tracks `i+seed` identically, same checked `__forge_add_i64` overflow points) but is **not a real win**: the C compiler's induction-variable reassociation already canonicalizes `i+seed` to a running register, and the `%26` remains either way — so I propose nothing for `kernels.fg` rather than ship a no-op.

**Counterexample section**

- Counterexample to the (rejected) `ch`-accumulator strength reduction: `seed = -30`, `n = 6`. Original bytes: `(i+seed)%26` for i=0..5 = −4,−3,−2,−1,0,−25 → chars 61,62,63,64,65,**40**. Accumulator: 61,62,63,64,65,**66** — diverges at i=5, where truncated remainder jumps at a negative multiple of 26. Root cause: value 65 is ambiguous (arises from `a=0`, next 66, and from `a=−26`, next 40), so no accumulator driven by `ch` alone can be exact for all `int64_t` seeds; a sign-tracking variant would trade one modulo for two compares plus a flag — not a win.
- Invariants tried to break on the proposal: underflow (`len > cap` — excluded by the documented invariant; the proposal is correct exactly and only under it, same as the current source); `cap == 0` (then `len == 0`, predicate false, slow path grows — unchanged); `cap == len` nonzero (predicate false — unchanged); NUL reservation (`> 1` retained, so byte at `len` writable only with room for NUL at `cap-1`); rejection paths and arena ordering (untouched textually). No counterexample found against the proposal under the stated invariants.
