"""Exercise generated Forge substring calls at scratch-buffer boundaries in fresh Node processes."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import tempfile

import js_substring_bench as original

HERE = Path(__file__).resolve().parent
BRIDGE = HERE / "js_suffix_controls.cjs"


def cases():
    block = "00aé界😀/123"  # 16 UTF-8 bytes
    # Every generated source has a 16-byte ASCII suffix identifying its input.
    def sliced(block, repeats, start, length, count, **options):
        return dict(block=block, repeats=repeats, start=start, length=length, count=count, **options)

    yield "distinct_suffix", sliced(block, 4095, 65520, 16, 256, distinct=True)
    yield "early", sliced(block, 4095, 192, 16, 800)
    yield "early_after_large", sliced(block, 4095, 192, 16, 800, prime=True)
    yield "small_190", sliced("A", 240, 174, 16, 48000)
    yield "cap_fit", sliced("A", 196592, 196589, 16, 600)
    yield "cap_miss", sliced("A", 196592, 196590, 16, 600)
    yield "over_cap_suffix", sliced(block, 16383, 262128, 16, 180)
    yield "no_encode_into", sliced(block, 4095, 65520, 16, 600, disable_encode_into=True)
    yield "out_of_bounds_hot", sliced(block, 4095, 1 << 20, 12, 160000)
    _, _, urls, _ = next(original.cases())
    yield "repository_hot", dict(urls=[url for url, _, _ in urls], start=0, length=0, count=192000)


def oracle(config):
    if "urls" in config:
        values = config["urls"]
        operation = "repository"
    else:
        operation = "slice"
        count = config["count"]
        indices = range(16)
        if config.get("distinct"):
            offset = 2 * (count // 4)
            indices = range(offset, offset + count)
        prefix = config["block"] * config["repeats"]
        values = [f"{prefix}case-id-{index:08d}" for index in indices]
    inputs = [(s, config["start"], config["length"]) for s in values]
    digest, checksum = original.expected(operation, inputs, config["count"])
    sizes = sorted({len(s.encode("utf8")) for s in values})
    return digest, checksum, sizes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path, help="Emitted baseline JS")
    parser.add_argument("--candidate", required=True, type=Path, help="Emitted candidate JS")
    parser.add_argument("--cpu", required=True, type=int)
    parser.add_argument("--pairs", type=int, default=8)
    parser.add_argument("--case", action="append", choices=dict(cases()))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.pairs < 2:
        parser.error("at least two pairs required")
    os.sched_setaffinity(0, {args.cpu})
    node = Path(shutil.which("node")).resolve()
    programs = {"baseline": args.baseline.resolve(), "candidate": args.candidate.resolve()}
    report = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  affinity=sorted(os.sched_getaffinity(0)), platform=platform.platform(),
                  python=platform.python_version(), node=subprocess.check_output([node, "-v"], text=True).strip(),
                  node_sha256=original.digest(node), emitted_sha256={k: original.digest(v) for k, v in programs.items()},
                  source_sha256={p.name: original.digest(p) for p in (BRIDGE, Path(__file__), Path(original.__file__),
                                                                     original.SOURCE, original.HERE / "function_lookup_bench.py")},
                  cases={})
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / "config.json"
        for index, (name, config) in enumerate(cases()):
            if args.case and name not in args.case:
                continue
            digest, checksum, sizes = oracle(config)
            config_path.write_text(json.dumps(config))
            samples = []
            changes = []
            for pair in range(args.pairs):
                order = list(programs) if (index + pair) % 2 == 0 else list(reversed(programs))
                values = {}
                for label in order:
                    run = subprocess.run([node, "--require", BRIDGE, programs[label], config_path],
                                         text=True, capture_output=True, check=True, timeout=60)
                    result = json.loads(run.stdout)
                    if run.stderr or result["ns"] <= 0 or (result["digest"], result["checksum"]) != (digest, checksum):
                        raise ValueError(f"{name} {label}: {result} expected {digest} {checksum}: {run.stderr}")
                    values[label] = result
                samples.append(dict(order=order, values=values))
                changes.append(100 * (values["candidate"]["ns"] / values["baseline"]["ns"] - 1))
            q1, median, q3 = statistics.quantiles(changes, method="inclusive")
            elapsed = dict(median=median, q1=q1, q3=q3)
            report["cases"][name] = dict(config=config, utf8_bytes=sizes, checksum=checksum, output_sha256=digest,
                                         samples=samples, paired_elapsed_pct=elapsed)
            print(name, elapsed, flush=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
