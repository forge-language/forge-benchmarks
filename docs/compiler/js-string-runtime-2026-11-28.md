# UTF-8 string length and builder append in Forge-generated JavaScript

The fixture calls both standard-library operations from compiled Forge loops. JavaScript supplies two input values and an iteration count at runtime. Each length iteration sums the UTF-8 lengths of both values. Each append iteration writes both values to a growing builder. The report fixture builds 35,000 numbered records with severity labels and their UTF-8 byte counts. One in four records has a Korean label and an emoji.

## Measurement

Each compiler emitted JavaScript from the same Forge source once per study. Each sample started a fresh Node process pinned to logical CPU 4 on an Intel Core i5-13400F. Two calls with one quarter of the iterations warmed the generated function. Node's monotonic clock then timed one complete Forge call, including builder allocation, growth, conversion to a string and arena reset where applicable. Process startup, compilation and output verification happened outside the timed interval. The runner alternated baseline and candidate order across ten pairs per case and reversed the initial order for adjacent cases.

Python independently calculated the expected UTF-8 byte counts and SHA-256 digests of complete builder outputs. Length counts bytes after embedded NUL, while append stops at the first NUL in each input. The boxed controls passed JavaScript `String` objects across the FFI. Each JSON records the exact inputs, iteration counts, expected and observed outputs, chronological samples, paired quartiles, binary identities and environment.

## Results

The scalar ASCII scan (V1) and regular-expression ASCII test (V2) both fell back to encoding after checking strings with a late non-ASCII character. For builder append, those inputs increased median elapsed time by 30.9% and 21.0%, respectively. V3 encoded short primitive strings into a reusable 192-byte scratch buffer. It reduced elapsed time on those inputs by 49.8% and on the mixed report by 71.6%. The long length control took 4.6% more time with V3.

Each percentage is the median of the paired change in elapsed time, calculated as 100 × (candidate / baseline − 1). Lower values are faster. The absolute times are separate medians from the V3 comparison. Each candidate had its own same-session baseline measurements. The long case combines 1,024 ASCII units with 256 repetitions of a CJK character and an emoji. The late-Unicode case ends a 64-unit string with a non-ASCII scalar or surrogate pair.

| Workload | V1 | V2 | V3 | Baseline → V3 (ms) | V3 paired IQR (%) |
| --- | ---: | ---: | ---: | ---: | ---: |
| length short ascii | -93.5% | -93.4% | -85.9% | 76.40 → 10.79 | -86.2 to -85.5 |
| append short ascii | -86.7% | -84.7% | -70.3% | 65.13 → 19.11 | -70.8 to -70.0 |
| length short unicode | +2.0% | +7.2% | -85.5% | 65.53 → 9.52 | -86.1 to -85.4 |
| append short unicode | +3.8% | +11.7% | -69.1% | 52.77 → 16.45 | -69.4 to -69.0 |
| length late unicode | +22.8% | +15.7% | -76.7% | 64.52 → 14.93 | -76.9 to -76.7 |
| append late unicode | +30.9% | +21.0% | -49.8% | 44.74 → 22.42 | -50.1 to -49.3 |
| length empty nul | -35.7% | -32.2% | -84.3% | 60.85 → 9.58 | -84.4 to -84.2 |
| append empty nul | -92.8% | -31.0% | -68.8% | 58.21 → 18.02 | -69.0 to -68.7 |
| length ascii 64 | -74.8% | -85.7% | -78.6% | 64.05 → 13.69 | -79.0 to -78.5 |
| append ascii 64 | -40.6% | -48.5% | -56.2% | 36.38 → 16.13 | -56.6 to -55.8 |
| length ascii 65 | -0.1% | +1.6% | +1.4% | 65.11 → 66.03 | -0.1 to +3.4 |
| append ascii 65 | +10.2% | +11.0% | +0.6% | 37.09 → 37.05 | -1.5 to +1.1 |
| length long | -0.5% | +3.2% | +4.6% | 128.32 → 134.65 | +3.7 to +5.2 |
| append long | -2.9% | -2.0% | -3.7% | 58.51 → 56.42 | -3.9 to -0.8 |
| length boxed | +0.1% | -0.0% | -0.4% | 62.75 → 63.17 | -0.8 to +2.0 |
| append boxed | +3.6% | +3.1% | -2.6% | 58.19 → 56.65 | -5.6 to -2.0 |
| mixed report | -78.0% | -73.3% | -71.6% | 91.55 → 26.08 | -72.2 to -70.9 |

The raw observations include all ten pairs for every row. [Scalar ASCII scan](js-string-runtime-2026-11-28-v1.json) · [ASCII regular expression](js-string-runtime-2026-11-28-v2.json) · [Bounded UTF-8 encoding](js-string-runtime-2026-11-28-v3.json)

The archive contains the exact four emitted programs, with SHA-256 identities in the raw reports. [Emitted JavaScript](js-string-runtime-2026-11-28-emitted.tar.xz)

## Reproduce

The baseline and selected V3 Release binaries were rebuilt from their published revisions and matched the SHA-256 digests in the measurements. [Baseline compiler](https://github.com/forge-language/forge/commit/294b297e7a59db89223714de603c194f5c68475e) · [V3 compiler](https://github.com/forge-language/forge/commit/ee88fa8f262c70e81ede274c096a07ae0097dc3c)

From the benchmark repository, pass two Release compiler binaries, a Forge SDK build directory and an available Linux CPU. The published measurements used Node v24.15.0, GCC via `/usr/bin/cc`, CMake Release flags `-O3 -DNDEBUG`, and the Forge working tree based on `451c281dfb73955803aeb9e75c2c917f242cbbc6`. The JSON records the exact binary hashes. The published working-directory and Node paths use `~` for the home directory.

```bash
python3 -B benchmark/compiler/js_string_runtime_bench.py \
  --baseline /path/to/baseline/forge --candidate /path/to/candidate/forge \
  --root ../forge/build --cpu 4 --pairs 10 \
  --build-note 'Source revisions and build flags for this comparison' \
  --output /tmp/js-string-runtime.json
```

To run an archived emitted program directly, extract the JavaScript and select a case from its recorded configuration. The following command runs the mixed report and checks its complete output digest.

```bash
study_dir=$(mktemp -d)
archive=docs/compiler/js-string-runtime-2026-11-28-emitted.tar.xz
tar -xf "$archive" -C "$study_dir"
run=docs/compiler/js-string-runtime-2026-11-28-v3.json
python3 - "$run" "$study_dir/case.json" <<'PY'
import json, pathlib, sys
case = json.loads(pathlib.Path(sys.argv[1]).read_text())["cases"]["mixed_report"]
pathlib.Path(sys.argv[2]).write_text(json.dumps(case["config"]))
PY
taskset -c 4 node --require "$PWD/benchmark/compiler/js_string_runtime.cjs" \
  "$study_dir/v3.cjs" "$study_dir/case.json" > "$study_dir/sample.json"
python3 - "$run" "$study_dir/sample.json" <<'PY'
import json, pathlib, sys
report, sample = (json.loads(pathlib.Path(path).read_text()) for path in sys.argv[1:])
assert sample["result"] == report["cases"]["mixed_report"]["expected"]
print(sample)
PY
```
