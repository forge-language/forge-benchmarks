# Reusing UTF-8 storage for changing loop-index inputs

Keep the existing loop-index cache. A separate refill helper cut elapsed time by 49.7% on distinct strings with a shared prefix and 46.0% on alternating strings against the immediate development baseline. Repeated reads of one string slowed by 12.4% on the longer control. Two further layouts reproduced that slowdown. [Prior study and original +5.3% result](js-byte-index-2026-11-28.md)

The current baseline (archived as `len`) includes the in-progress length and substring work on Forge `b9fa8dd`. The historical baseline (`legacy`) comes from the earlier byte-index study at `ee88fa8f`. The isolated trial (`churn`) starts with a fresh encoding on the first late read. Subsequent changes encode into a private backing array with room for three bytes per UTF-16 unit and retain a view of the written bytes. Eligible strings have at most 65,536 UTF-16 units. The trial falls back to a fresh encoding when the encoder lacks `encodeInto`. [Exact C sources, emitted programs, harness and SHA-256 manifest](js-index-churn-2026-11-28.raw/replay.tar.xz)

All comparisons used fresh Node v24.15.0 processes pinned to logical CPU 2 on an Intel Core i5-13400F. The original runner warms each process twice, records the timed checksum, and requires equality with an independent Python UTF-8 oracle for every sample. Each figure gives the median of paired percentage changes in elapsed time, with alternating run order. Lower is faster. [Current baseline, eight pairs](js-index-churn-2026-11-28.raw/current.json) · [Historical baseline, eight pairs](js-index-churn-2026-11-28.raw/legacy.json)

| Workload | Against current baseline | Paired IQR | Against historical baseline |
| --- | ---: | ---: | ---: |
| `digest_valid` | -0.7% | -1.6% to +0.4% | -77.5% |
| `chars_4k` | +11.1% | -4.5% to +91.6% | -98.9% |
| `loop_distinct_4k_common_prefix_late` | -49.7% | -53.3% to -42.5% | -48.6% |
| `loop_alternating_4k_common_prefix_late` | -46.0% | -46.4% to -44.6% | -43.0% |
| `loop_repeated_4k_late` | +55.5% | -34.3% to +220.5% | -97.7% |
| `loop_over_limit_late` | +0.1% | -0.5% to +3.1% | +2.1% |

The original single-string sample took about 2 ms and produced a wide range of paired changes. We therefore increased the repeated-read count from 12,000 to 360,000 and both full scans from 8 to 128. Each control used 12 alternating pairs. The early-hit layout (`fast`) tests for a cached string before checking the string-length limits. The split layout (`split`) keeps the first full encoding inside the loop-index function, calling the refill helper only after the string changes. [Longer controls](js-index-churn-2026-11-28.raw/long-controls.json) · [Early hit](js-index-churn-2026-11-28.raw/fast-long.json) · [First fill inline](js-index-churn-2026-11-28.raw/split-long.json)

| Workload | Separate refill | Early hit | First fill inline |
| --- | ---: | ---: | ---: |
| `chars_4k` | -2.3% (-6.4% to +0.6%) | +2.2% (+1.1% to +6.9%) | +1.8% (-0.5% to +2.7%) |
| `brackets_4k` | +1.4% (-0.7% to +5.9%) | +0.8% (-6.3% to +3.6%) | -0.6% (-1.7% to +3.3%) |
| `loop_repeated_4k_late` | +12.4% (+10.8% to +14.1%) | +12.3% (+12.0% to +12.6%) | +11.4% (+7.4% to +14.1%) |

An earlier inline trial added a separate written-length field to the cache. An eight-pair replay on the original workload reduced distinct-stream time by 59.0% and increased the full character scan by 90.8%. [Inline replay](js-index-churn-2026-11-28.raw/inline.json) · [Original six-pair exploration](js-index-churn-2026-11-28.raw/inline-discovery.txt)

## Replay

From this benchmark checkout, use Linux with Node and a permitted logical CPU. The script verifies the archive manifest and supplies the saved generated output to the original runner. The original JSON files identify the compiled binaries by SHA-256. In a replay, the compiler hashes identify the small wrapper scripts. Compare the emitted JavaScript hashes for program identity. [Replay script](js-index-churn-2026-11-28.raw/replay.py) · [Longer control counts](js-index-churn-2026-11-28.raw/hot-controls.py)

```sh
raw=docs/compiler/js-index-churn-2026-11-28.raw
python3 "$raw/replay.py" len churn --cpu 2 --pairs 8 \
  --case digest_valid --case chars_4k --case loop_distinct_4k_common_prefix_late \
  --case loop_alternating_4k_common_prefix_late --case loop_repeated_4k_late \
  --case loop_over_limit_late --output /tmp/index-current.json
python3 "$raw/replay.py" len churn --long --cpu 2 --pairs 12 --output /tmp/index-long.json
```
