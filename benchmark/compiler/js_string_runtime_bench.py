"""Time emitted JavaScript string operations in warmed Node processes on one Linux CPU."""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile

from function_lookup_bench import digest


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "js_string_runtime.fg"
BRIDGE = HERE / "js_string_runtime.cjs"


def cases():
    for tag, inputs, length_count, append_count in [
        ("short_ascii", ["INFO", " status=ok"], 120000, 90000),
        ("short_unicode", ["서울", "é😀"], 100000, 70000),
        ("late_unicode", ["x" * 63 + "é", "y" * 62 + "😀"], 80000, 40000),
        ("empty_nul", ["", "id\0suffix😀"], 100000, 90000),
        ("ascii_64", ["x" * 64, "Y" * 64], 90000, 40000),
        ("ascii_65", ["x" * 65, "Y" * 65], 90000, 40000),
        ("long", ["x" * 1024, "界😀" * 256], 35000, 6000),
        ("boxed", ["INFO", "ready"], 90000, 70000),
    ]:
        for operation, count in [("length", length_count), ("append", append_count)]:
            yield f"{operation}_{tag}", dict(operation=operation, iterations=count,
                                             inputs=inputs, boxed=tag == "boxed")
    yield "mixed_report", dict(operation="report", iterations=35000,
                               inputs=["INFO", "재시도😀"], boxed=False)


def oracle(config):
    a, b = config["inputs"]
    count = config["iterations"]
    if config["operation"] == "length":
        return str(count * (len(a.encode()) + len(b.encode())))
    if config["operation"] == "append":
        result = (a.partition("\0")[0] + b.partition("\0")[0]) * count
    else:
        rows = []
        for i in range(count):
            label = b if i % 4 == 0 else a
            rows.append(f"{i} {label} bytes={len(label.encode())}\n")
        result = "".join(rows)
    return hashlib.sha256(result.encode()).hexdigest()


def measure(js, config_file, node, expected):
    run = subprocess.run([node, "--require", BRIDGE, js, config_file],
                         capture_output=True, text=True, check=True, timeout=120)
    data = json.loads(run.stdout)
    if run.stderr or data["result"] != expected or data["ns"] <= 0:
        raise ValueError(f"{js.name} {config_file.name}: {data}, expected {expected}, {run.stderr}")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("baseline", "candidate", "root", "output"):
        parser.add_argument(f"--{key}", required=True, type=Path)
    parser.add_argument("--cpu", required=True, type=int)
    parser.add_argument("--pairs", type=int, default=12)
    parser.add_argument("--build-note", required=True, help="Source revisions and build flags")
    parser.add_argument("--case", action="append", choices=dict(cases()), help="Limit to named cases")
    args = parser.parse_args()
    if args.pairs < 2:
        parser.error("at least two pairs required")
    os.sched_setaffinity(0, {args.cpu})
    compilers = {label: getattr(args, label).resolve() for label in ("baseline", "candidate")}
    node = Path(shutil.which("node")).resolve()
    report = {
        "method": "Fresh Node per sample; warm up twice with one quarter of the iterations. "
                  "Time one Forge callback with hrtime.bigint, including builder finish and reset. "
                  "Hash full string outputs after timing. Python checks each result independently. "
                  "Alternate AB/BA by pair, stagger first order by case. Samples are chronological.",
        "command": sys.argv, "cwd": os.getcwd(), "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "build_note": args.build_note, "platform": platform.platform(),
        "cpu_model": next(line.split(':', 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                          if line.startswith("model name")),
        "affinity": sorted(os.sched_getaffinity(0)), "node": str(node),
        "node_version": subprocess.check_output([node, "--version"], text=True).strip(),
        "node_sha256": digest(node), "pairs": args.pairs,
        "compiler_sha256": {key: digest(path) for key, path in compilers.items()},
        "input_sha256": {path.name: digest(path) for path in (SOURCE, BRIDGE, Path(__file__))},
        "cases": {},
    }
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        js = {key: work / (key + ".js") for key in compilers}
        for key, compiler in compilers.items():
            subprocess.run([compiler, SOURCE, "--emit-js", "--forge-root", args.root.resolve(),
                            "-o", js[key]], check=True)
        report["emitted_js_sha256"] = {key: digest(path) for key, path in js.items()}
        for index, (name, config) in enumerate(cases()):
            if args.case and name not in args.case:
                continue
            config_file = work / (name + ".json")
            config_file.write_text(json.dumps(config))
            expected = oracle(config)
            pairs = []
            changes = []
            for pair in range(args.pairs):
                order = tuple(compilers) if (index + pair) % 2 == 0 else tuple(reversed(compilers))
                values = {key: measure(js[key], config_file, node, expected) for key in order}
                pairs.append({"order": order, "values": values})
                changes.append(100 * (values["candidate"]["ns"] / values["baseline"]["ns"] - 1))
            medians = {key: statistics.median(p["values"][key]["ns"] for p in pairs) / 1e6 for key in js}
            quartiles = statistics.quantiles(changes, n=4, method="inclusive")
            row = dict(config=config, expected=expected, pairs=pairs, median_ms=medians,
                       paired_change_pct=dict(median=statistics.median(changes), q1=quartiles[0], q3=quartiles[2],
                                              min=min(changes), max=max(changes)))
            report["cases"][name] = row
            print(f"{name}: {medians['baseline']:.2f} -> {medians['candidate']:.2f} ms; "
                  f"paired {statistics.median(changes):+.1f}%", flush=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
