"""Measure paired end-to-end Forge --emit-js times and verify the emitted programs."""
import argparse
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time

from function_lookup_bench import digest


def cases(source_root):
    yield "tiny", {"main.fg": "native main{println(3);return 0;}"}, "3\n"
    example = (source_root / "examples/log_alerts.fg").read_text(encoding="utf-8")
    yield "log_alerts", {"main.fg": example}, "alerts=3\n"

    locals_ = "".join(f"let slot{i:03d}:int=1;\n" for i in range(900))
    repeats = 1800
    updates = "sum=advance(sum)+slot899;\n" * repeats
    for name, statements, result, expected in [
        ("late_and_call", updates, "sum", 2 * repeats),
        ("first", "sum=slot000;\n" * repeats, "sum", 1),
        ("sparse", "", "slot899", 1),
        ("unused", "", "0", 0),
    ]:
        functions = ("fn advance(x:int):int{return x+1;}\n"
                     "fn work():int{\n" + locals_ + "let sum:int=0;\n"
                     + statements + "return " + result + ";}\n")
        if name == "late_and_call":
            yield "root_" + name, {"main.fg": functions + "native main{println(work());return 0;}"}, f"{expected}\n"
        yield "module_" + name, {
            "main.fg": "import helpers;native main{println(helpers.work());return 0;}",
            "helpers.fg": functions,
        }, f"{expected}\n"


def measure(work, sources, expected, compilers, root, pairs):
    for name, contents in sources.items():
        (work / name).write_text(contents, encoding="utf-8")
    outputs = {label: work / (label + ".js") for label in compilers}
    commands = {label: [compiler, "main.fg", "--emit-js", "--forge-root", root, "-o", outputs[label]]
                for label, compiler in compilers.items()}
    times = {label: [] for label in compilers}
    for pair in range(-1, pairs):
        order = compilers if pair % 2 == 0 else reversed(compilers)
        for label in order:
            start = time.perf_counter_ns()
            subprocess.run(commands[label], cwd=work, check=True, capture_output=True, timeout=60)
            elapsed = time.perf_counter_ns() - start
            if pair >= 0:
                times[label].append(elapsed)
        if outputs["baseline"].read_bytes() != outputs["candidate"].read_bytes():
            raise ValueError(f"{work.name}: generated JavaScript changed")
        if pair == -1:
            result = subprocess.run(["node", outputs["candidate"]], cwd=work, text=True,
                                    check=True, capture_output=True, timeout=60)
            if result.stdout != expected or result.stderr:
                raise ValueError(f"{work.name}: unexpected Node output {result.stdout!r} {result.stderr!r}")
    return {"source_sha256": {name: digest(work / name) for name in sources},
            "emitted_js_sha256": digest(outputs["candidate"]), "node_stdout": expected,
            "median_ms": {label: statistics.median(raw) / 1e6 for label, raw in times.items()},
            "samples_ns": times}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("baseline", "candidate", "root", "source-root", "output"):
        parser.add_argument("--" + arg, type=Path, required=True)
    parser.add_argument("--pairs", type=int, default=40)
    parser.add_argument("--cpu", type=int, help="Pin to this logical CPU on Linux")
    parser.add_argument("--build-note", help="Describe the compared revisions, toolchain and flags")
    args = parser.parse_args()
    if args.pairs < 2:
        parser.error("at least two pairs required")
    if args.cpu is not None:
        os.sched_setaffinity(0, {args.cpu})
    compilers = {label: getattr(args, label).resolve() for label in ("baseline", "candidate")}
    report = {
        "method": "One warmup pair, followed by alternating pairs, starting with baseline. "
                  "Samples include the entire --emit-js invocation and file output. "
                  "Each pair is checked for byte equality. The warmup is executed under Node.",
        "pairs": args.pairs, "system": platform.platform(), "cpu": args.cpu,
        "node": subprocess.check_output(["node", "--version"], text=True).strip(),
        "build_note": args.build_note, "compiler_sha256": {k: digest(v) for k, v in compilers.items()},
        "candidate_codegen_js_sha256": digest(args.source_root / "compiler/codegen_js.c"),
        "runner_sha256": digest(__file__), "cases": {},
    }
    with tempfile.TemporaryDirectory() as tmp:
        for name, sources, expected in cases(args.source_root):
            work = Path(tmp) / name
            work.mkdir()
            row = measure(work, sources, expected, compilers, args.root.resolve(), args.pairs)
            report["cases"][name] = row
            print(name, row["median_ms"], flush=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
