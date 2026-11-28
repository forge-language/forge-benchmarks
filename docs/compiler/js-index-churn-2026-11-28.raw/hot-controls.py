"""Run longer steady-state samples through the archived byte-index runner."""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[3] / "benchmark" / "compiler"))
import js_byte_index_bench as bench

original = bench.cases

def controls():
    counts = {"chars_4k": 128, "loop_repeated_4k_late": 360000, "brackets_4k": 128}
    for name, operation, values, offset, count in original():
        if name in counts:
            yield name, operation, values, offset, counts[name]

bench.cases = controls
bench.main()
