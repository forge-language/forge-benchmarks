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
