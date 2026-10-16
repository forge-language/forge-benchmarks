#!/usr/bin/env python3
"""Run the unchanged native harness against two immutable source snapshots."""
import argparse
import http.server
import importlib.util
import json
from pathlib import Path
import shlex
import statistics
import subprocess
import tempfile
import threading


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--current', type=Path, required=True, help='Current forge-web checkout')
    parser.add_argument('--baseline', required=True, help='Source snapshot (e.g. Git archive of 8ef1ce0)')
    parser.add_argument('--image', default='forge-platform-release:local')
    parser.add_argument('--output', default='/tmp/forge-web-performance.json')
    parser.add_argument('--rounds', type=int, default=5)
    args = parser.parse_args()
    source = args.current.resolve()
    harness = Path(__file__).resolve().parent
    baseline = Path(args.baseline).resolve()
    for required in ('src/bridge.c', 'tests/http_test.py'):
        if not (source / required).is_file():
            parser.error(f'--current must contain {required}')
    if not (baseline / 'src/bridge.c').is_file():
        parser.error('--baseline must contain src/bridge.c')
    if args.rounds < 1:
        parser.error('--rounds must be positive')
    with tempfile.TemporaryDirectory(prefix='forge-web-native-benchmark-') as temporary:
        compare(args, source, harness, baseline, Path(temporary))


def compare(args: argparse.Namespace, source: Path, harness: Path, baseline: Path, build: Path) -> None:
    mounts = ['-v', f'{harness}:/harness:ro', '-v', f'{source}:/src:ro',
              '-v', f'{baseline}:/baseline:ro', '-v', f'{build}:/build']
    base = ['docker', 'run', '--rm', '--cpus', '2', '--network', 'host', *mounts, args.image]
    flags = shlex.split(subprocess.check_output(base + ['pkg-config', '--cflags', '--libs',
        'libmicrohttpd', 'json-c', 'libcurl', 'openssl'], text=True))
    for name, prefix in [('before', '/baseline'), ('after', '/src')]:
        command = ['cc', '-O2', '-Wall', '-Wextra', '-Werror', '-I' + prefix + '/include',
                   '-DWEB_SOURCE="' + prefix + '/src/bridge.c"', '/harness/native.c',
                   *flags, '-pthread', '-o', '/build/' + name]
        subprocess.run(base + command, check=True)
    spec = importlib.util.spec_from_file_location('http_test', source / 'tests/http_test.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), module.Echo)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/echo'
    samples = {'before': [], 'after': []}
    try:
        for round in range(args.rounds):
            for variant in (['before', 'after'] if round % 2 == 0 else ['after', 'before']):
                sample = json.loads(subprocess.check_output(base + [f'/build/{variant}'], text=True))
                module.Echo.connections = {}
                sample.update(json.loads(subprocess.check_output(base + [f'/build/{variant}', url], text=True)))
                sample['http_connections'] = len(module.Echo.connections)
                samples[variant].append(sample)
                print(variant, json.dumps(sample), flush=True)
    finally:
        server.shutdown()
        server.server_close()
    metrics = ['buffer_seconds', 'ownership_seconds', 'rate_seconds', 'http_seconds', 'http_connections']
    medians = {variant: {key: statistics.median(row[key] for row in samples[variant]) for key in metrics}
               for variant in samples}
    result = {'baseline': str(baseline), 'current': str(source), 'conditions': {'image': args.image, 'compiler': 'GCC 11.4 -O2',
              'cpu_quota': 2, 'host': 'shared AMD BC-250', 'rounds': args.rounds, 'order': 'alternating',
              'limits': 'synthetic native microbenchmarks and sequential loopback HTTP; not application RPS'},
              'samples': samples, 'median': medians,
              'speedup': {key: medians['before'][key] / medians['after'][key] for key in metrics}}
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'median': medians, 'speedup': result['speedup']}, indent=2))

if __name__ == '__main__':
    main()
