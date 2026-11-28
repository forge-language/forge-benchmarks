"""Replay a paired comparison using the exact generated programs in replay.tar.xz."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("baseline", choices=["legacy", "len"])
parser.add_argument("candidate", choices=["churn", "fast", "split", "inline"])
parser.add_argument("--long", action="store_true")
args, remainder = parser.parse_known_args()
directory = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as temp:
    work = Path(temp)
    with tarfile.open(directory / "replay.tar.xz") as archive:
        archive.extractall(work, filter="data")
    subprocess.run(["sha256sum", "--quiet", "-c", "SHA256SUMS"], cwd=work, check=True)
    # The original runner asks each compiler to emit a fixture. Supply its saved output.
    for name in [args.baseline, args.candidate]:
        wrapper = work / name
        wrapper.write_text('#!/bin/sh\ncp "$0.js" "$6"\n')
        wrapper.chmod(0o755)
    script = directory / "hot-controls.py" if args.long else work / "js_byte_index_bench.py"
    subprocess.run([sys.executable, script, "--baseline", work / args.baseline,
                    "--candidate", work / args.candidate, "--root", work, "--build-note",
                    "Archived emitted JavaScript replay (compiler hashes identify wrappers)",
                    *remainder], check=True, env={**os.environ, "PYTHONPATH": str(work)})
