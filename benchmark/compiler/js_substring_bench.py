"""Time Forge-emitted substring operations in alternating fresh Node processes on one CPU."""
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
import tempfile

from function_lookup_bench import digest


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "js_substring.fg"
BRIDGE = HERE / "js_substring.cjs"


def cases():
    urls = [f"HTTPS://Git.Example/{group}/Pkg{i}{suffix}"
            for i in range(4) for group in ("Team", "Téam") for suffix in (".GIT", ".git", "", ".gitx")]
    yield "repository", "repository", [(url, 0, 0) for url in urls], 24000
    ascii_text = [f"pkg{i:04d}/stdlib/io.fg" for i in range(32)]
    yield "short_ascii", "slice", [(s, 3 + i % 4, 7) for i, s in enumerate(ascii_text)], 48000
    mixed = [f"{i:02x}aé界😀\0z" for i in range(32)]
    yield "short_utf8", "slice", [(s, 3, 10) for s in mixed], 48000
    yield "short_late_utf8", "slice", [(s + "a" * 40 + "é", 0, 8) for s in ascii_text], 48000
    # Every long string has 65536 bytes. Each 16-byte block has aligned scalar boundaries.
    blocks = [f"{i:02x}" + "aé界😀/123" for i in range(16)]
    long_utf8 = [block * 4096 for block in blocks]
    long_ascii = [(f"package/{i:04d}/io/") * 4096 for i in range(16)]
    for name, strings, start, length, count in [
        ("long_prefix", long_utf8, 0, 12, 600),
        ("long_ascii_prefix", long_ascii, 0, 12, 1800),
        ("long_suffix", long_utf8, 65520, 16, 600),
        ("long_span", long_utf8, 1024, 57344, 300),
        ("long_ascii_span", long_ascii, 1024, 57344, 600),
        ("empty", long_utf8, 4, 0, 700),
        ("out_of_bounds", long_utf8, 1 << 20, 12, 700),
    ]:
        yield name, "slice", [(s, start, length) for s in strings], count
    yield "ffi_numbers", "slice", [(123450 + i, 1, 4) for i in range(32)], 36000


def expected(operation, inputs, count):
    def result(value, start, length):
        if operation == "repository":
            value = value.lower()
            return value.removesuffix(".git") if len(value.encode()) > 4 else value
        return str(value).encode("utf-8")[start:start + length].decode("utf-8-sig")

    outputs = [result(*row) for row in inputs]
    serialized = json.dumps(outputs, ensure_ascii=False, separators=(",", ":")).encode()
    terms = []
    for output in outputs:
        units = output.encode("utf-16-le")
        terms.append(31 * (len(units) // 2) + int.from_bytes(units[:2], "little")
                     + int.from_bytes(units[-2:], "little"))
    return hashlib.sha256(serialized).hexdigest(), sum(terms[i % len(terms)] for i in range(count))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--emitted", action="store_true", help="Inputs are already emitted JS programs")
    parser.add_argument("--pairs", type=int, default=8)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--case", action="append")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.emitted and not args.root:
        parser.error("--root SDK is required for compiler inputs")
    if args.candidate and args.pairs < 2:
        parser.error("at least two pairs are required")
    available = list(cases())
    if args.case and set(args.case) - {row[0] for row in available}:
        parser.error("unknown --case")
    os.sched_setaffinity(0, {args.cpu})
    node = Path(shutil.which("node")).resolve()
    programs = {"baseline": args.baseline.resolve()}
    if args.candidate:
        programs["candidate"] = args.candidate.resolve()
    report = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  platform=platform.platform(), affinity=sorted(os.sched_getaffinity(0)),
                  cpu_model=next(s.split(":", 1)[1].strip() for s in Path("/proc/cpuinfo").read_text().splitlines()
                                 if s.startswith("model name")), python=platform.python_version(),
                  node=subprocess.check_output([node, "--version"], text=True).strip(), node_sha256=digest(node),
                  source_sha256={p.name: digest(p) for p in (SOURCE, BRIDGE, Path(__file__),
                                                             HERE / "function_lookup_bench.py")}, cases={})
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        if not args.emitted:
            report["compiler_sha256"] = {k: digest(v) for k, v in programs.items()}
            for label, compiler in programs.items():
                emitted = work / (label + ".js")
                subprocess.run([compiler, SOURCE, "--emit-js", "--forge-root", args.root.resolve(),
                                "-o", emitted], check=True)
                programs[label] = emitted
        report["emitted_sha256"] = {k: digest(v) for k, v in programs.items()}
        for index, (name, operation, inputs, count) in enumerate(available):
            if args.case and name not in args.case:
                continue
            config = work / "input.json"
            config.write_text(json.dumps(dict(operation=operation, inputs=inputs, count=count)))
            checksum_digest, checksum = expected(operation, inputs, count)
            rows = []
            for pair in range(args.pairs if args.candidate else 1):
                order = list(programs) if (pair + index) % 2 == 0 else list(reversed(programs))
                values = {}
                for label in order:
                    run = subprocess.run([node, "--require", BRIDGE, programs[label], config],
                                         text=True, capture_output=True, check=True, timeout=60)
                    result = json.loads(run.stdout)
                    if (run.stderr or result["ns"] <= 0 or result["digest"] != checksum_digest
                            or result["checksum"] != checksum):
                        raise ValueError(f"{name} {label}: {result} {run.stderr}, expected {checksum_digest} {checksum}")
                    values[label] = result
                rows.append(dict(order=order, values=values))
            item = dict(count=count, inputs=len(inputs), config_sha256=digest(config), checksum=checksum,
                        output_sha256=checksum_digest, samples=rows)
            if args.candidate:
                changes = [100 * (r["values"]["candidate"]["ns"] / r["values"]["baseline"]["ns"] - 1) for r in rows]
                q1, _, q3 = statistics.quantiles(changes, method="inclusive")
                item["paired_elapsed_pct"] = dict(median=statistics.median(changes), q1=q1, q3=q3)
            print(name, item.get("paired_elapsed_pct", {}), flush=True)
            report["cases"][name] = item
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
