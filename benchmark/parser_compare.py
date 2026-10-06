#!/usr/bin/env python3
"""Compare parser allocation counts on two explicit compiler source checkouts."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--before-root', required=True, type=Path)
parser.add_argument('--after-root', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--cc', default='cc')
args = parser.parse_args()
harness = Path(__file__).resolve().parent / 'parser_bench.c'
report = {'scope': '100000 extern declarations, 15 parser iterations per variant; GNU linker realloc wrapping; same host',
          'harness_sha256': hashlib.sha256(harness.read_bytes()).hexdigest(), 'variants': {}}
with tempfile.TemporaryDirectory(prefix='forge-parser-compare-') as directory:
    for variant, root in [('before', args.before_root), ('after', args.after_root)]:
        root = root.resolve()
        compiler = root / 'compiler'
        sources = [compiler / name for name in ['lexer.c', 'parser.c', 'ast.c']]
        binary = Path(directory) / variant
        subprocess.run([args.cc, '-std=c11', '-O3', '-DNDEBUG', '-I', str(compiler),
                        str(harness), *map(str, sources), '-Wl,--wrap=realloc', '-o', str(binary)], check=True)
        result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
        observations = dict(item.split('=', 1) for item in result.stdout.strip().split())
        report['variants'][variant] = {'root': str(root), 'observations': observations,
                                      'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
