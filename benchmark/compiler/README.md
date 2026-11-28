# Compiler benchmarks

These standalone runners moved from forge/tests. Run them from this checkout
against explicit compiler binaries and an assembled SDK. The lookup runners also
need the Forge source checkout for hello/bootstrap inputs; `--root` names the SDK.

```bash
python3 benchmark/compiler/function_lookup_bench.py \
  --baseline /path/to/forge-before --candidate ../forge/build/bin/forge \
  --source-root ../forge --root ../forge/build --output /tmp/function-lookup
python3 benchmark/compiler/local_lookup_bench.py \
  --baseline /path/to/forge-before --candidate ../forge/build/bin/forge \
  --source-root ../forge --root ../forge/build --output /tmp/local-lookup --cpu 2
python3 benchmark/compiler/const_lookup_bench.py \
  --baseline /path/to/forge-before --candidate ../forge/build/bin/forge \
  --source-root ../forge --root ../forge/build --output /tmp/const-lookup --cpu 2
python3 benchmark/compiler/modular_power_bench.py \
  --baseline /path/to/forge-before --candidate ../forge/build/bin/forge \
  --root ../forge/build --output /tmp/modular-power
```

Use a CPU allowed by the current affinity mask and a new output directory.
Measured trials alternate order, retain raw samples and validate generated output
or checksums. `--pairs 2` is a runner smoke check, not a performance conclusion.

Self-hosted compiler comparisons use the existing
[`../selfhost_compare.py`](../selfhost_compare.py), replacing the removed
forge/tests/selfhost_bench.py. Use `--help` for its named `--stage2` variants.
Its schema/method differs from the historical runner; archived historical source
and results establish the original observations.

To compare stage0 JavaScript emission on local-variable workloads, pass two
Release compilers and the candidate source checkout. The runner executes the
generated programs with Node and writes raw paired timings to a JSON file.

```bash
python3 benchmark/compiler/js_local_lookup_bench.py \
  --baseline /path/to/forge-before --candidate ../forge/build/bin/forge \
  --source-root ../forge --root ../forge/build --pairs 60 --cpu 4 \
  --output /tmp/js-local-lookup.json
```

The [2026-11-28 run](../../docs/compiler/js-local-lookup-2026-11-28.json)
records all seven inputs and 60 pairs per input. With 900 locals and 1,800
updates, median emission time fell from 15.46 to 4.57 ms in a top-level
function and from 15.65 to 4.80 ms in an imported module. Repeated reads
of the first module binding took 3.17 and 3.20 ms respectively. The small
`log_alerts` example took 1.62 ms with both builds.

Independent review checked module and local name precedence, scope restoration,
storage growth and lookup costs. Root functions still need to track bindings
when source modules are present because a local can shadow the module name in
a field expression. The Forge regression exercises index growth beyond 1,024
bindings and calls a shadowed module callback after both block and loop scopes
end.

The [UTF-8 string runtime study](../../docs/compiler/js-string-runtime-2026-11-28.md)
compares generated JavaScript for byte length and builder append. It includes
paired timings for three candidates and the emitted programs for replay.
