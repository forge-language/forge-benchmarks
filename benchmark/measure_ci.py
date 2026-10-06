#!/usr/bin/env python3
"""Run bounded, validated timing workloads and retain every raw observation."""
import argparse
import csv
import datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile

REPOSITORIES = ('forge', 'forge-runtime', 'forge-stdlib', 'forge-benchmarks')


def run(command, **kwargs):
    return subprocess.run(list(map(str, command)), check=True, capture_output=True, text=True,
                          timeout=120, **kwargs).stdout


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stats(values):
    if not values or any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError('Invalid timing observation')
    return {'median': statistics.median(values), 'min': min(values), 'max': max(values)}



def validate_strings(rows, repeats):
    expected = {(operation, size, mode, repeat)
        for operation, sizes, modes in [
            ('scan', [4096, 16384, 65536], ['legacy', 'view']),
            ('append', [4096, 16384], ['legacy', 'builder']),
            ('append_slice', [4096, 16384, 65536], ['substring', 'view']),
            ('match', [4096, 16384, 65536], ['substring', 'view'])]
        for size in sizes for mode in modes for repeat in range(1, repeats + 1)}
    actual = [(row.get('operation'), row.get('bytes'), row.get('implementation'), row.get('repeat')) for row in rows]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError('Incomplete or duplicate string workload observations')
    checksums = {}
    for row in rows:
        if not math.isfinite(row['seconds']) or row['seconds'] <= 0 or type(row['checksum']) is not int:
            raise ValueError('Invalid string timing or checksum')
        checksums.setdefault((row['operation'], row['bytes']), set()).add(row['checksum'])
    if any(len(values) != 1 for values in checksums.values()):
        raise ValueError('String algorithm checksums disagree')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    for name in REPOSITORIES:
        parser.add_argument('--' + name + '-root', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--allow-dirty', action='store_true', help='Local only; record dirty trees, never use in publishing workflow')
    args = parser.parse_args()
    if not 3 <= args.repeats <= 20:
        parser.error('repeats must be 3..20')
    roots = {name: getattr(args, name.replace('-', '_') + '_root').resolve() for name in REPOSITORIES}
    revisions, clean = {}, {}
    for name, root in roots.items():
        revisions[name] = run(['git', '-C', root, 'rev-parse', 'HEAD']).strip()
        clean[name] = not run(['git', '-C', root, 'status', '--porcelain', '--untracked-files=no']).strip()
        if not clean[name] and not args.allow_dirty:
            parser.error('Source tree has tracked modifications: ' + name)
    build = args.build.resolve()
    scheduler = build / 'bin/scheduler_bench'
    string = build / 'bin/string_bench'
    source = roots['forge-benchmarks'] / 'benchmark/parser_bench.c'
    compiler = roots['forge'] / 'compiler'
    commands = [('dispatch_10000_1', ['throughput', '10000', '1']),
                ('dispatch_10000_4', ['throughput', '10000', '4']), ('idle_50ms', ['50'])]
    rows = []
    for repeat in range(args.repeats):
        cases = commands if repeat % 2 == 0 else list(reversed(commands))
        for case, command in cases:
            raw = run([scheduler, *command])
            samples = list(csv.DictReader(io.StringIO(raw)))
            if len(samples) != 1:
                raise ValueError('Scheduler output did not contain exactly one observation')
            row = {key: float(value) for key, value in samples[0].items()}
            if any(not math.isfinite(value) or value < 0 for value in row.values()):
                raise ValueError('Scheduler invalid numeric observation')
            if case.startswith('dispatch') and (row['coroutines'] != 10000 or row['completed'] != 10000 or row['workers'] != int(command[-1])):
                raise ValueError('Scheduler coroutine completion mismatch')
            if case == 'idle_50ms' and (row['wait_ms'] != 50 or row['wall_ms'] < 45):
                raise ValueError('Scheduler I/O wait did not complete as requested')
            rows.append({'case': case, 'repeat': repeat + 1, **row, 'raw_csv': raw})
    with tempfile.TemporaryDirectory(prefix='forge-ci-timings-') as temporary:
        temp = Path(temporary)
        string_output = temp / 'strings.json'
        run(['python3', roots['forge-benchmarks'] / 'benchmark/string_measure.py', '--binary', string,
             '--output', string_output, '--repeats', args.repeats])
        strings = json.loads(string_output.read_text())
        validate_strings(strings['runs'], args.repeats)
        binary = temp / 'parser-bench'
        run([args.cc, '-std=c11', '-O3', '-DNDEBUG', '-I', compiler, source,
             compiler / 'lexer.c', compiler / 'parser.c', compiler / 'ast.c', '-Wl,--wrap=realloc', '-o', binary])
        parser_rows = []
        for repeat in range(args.repeats):
            raw = run([binary])
            data = dict(item.split('=', 1) for item in raw.strip().split())
            row = {'repeat': repeat + 1, 'declarations': int(data['declarations']),
                   'iterations': int(data['iterations']), 'parse_seconds': float(data['parse_seconds']),
                   'realloc_calls': int(data['realloc_calls']), 'raw_stdout': raw}
            if row['declarations'] != 100000 or row['iterations'] != 15:
                raise ValueError('Parser declaration validation mismatch')
            stats([row['parse_seconds']])
            parser_rows.append(row)
        scheduler_summary = [{'case': case, **{metric: stats([row[metric] for row in rows if row['case'] == case])
                              for metric in ['wall_ms', 'process_cpu_ms']}} for case, _ in commands]
        try:
            cpu = next(line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                       if line.startswith('model name'))
        except (OSError, StopIteration):
            cpu = platform.processor() or 'unavailable'
        run_id = os.environ.get('GITHUB_RUN_ID')
        report = {'schema_version': 1, 'measured_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'source_revisions': revisions, 'source_tree_clean': clean,
                  'run_url': f'https://github.com/forge-language/forge-benchmarks/actions/runs/{run_id}' if run_id else '',
                  'environment': {'os': platform.platform(), 'cpu': cpu, 'logical_cpus': os.cpu_count(),
                                  'compiler': run([args.cc, '--version']).splitlines()[0], 'python': platform.python_version(),
                                  'runner': os.environ.get('RUNNER_NAME', 'local'), 'runner_os': os.environ.get('RUNNER_OS', platform.system())},
                  'scope': 'Shared host; bounded CPU/parser/scheduler API workloads, not application request throughput. '
                           'Parser timing excludes fixture construction/free; scheduler timing excludes task creation; '
                           'string legacy/new algorithms execute in fixed order. CI hosts vary; compare matching environments.',
                  'repeats': args.repeats, 'summary': {'scheduler': scheduler_summary, 'strings': strings['summary'],
                      'parser': {'parse_seconds': stats([row['parse_seconds'] for row in parser_rows]),
                                 'realloc_calls': stats([row['realloc_calls'] for row in parser_rows])}},
                  'runs': {'scheduler': rows, 'strings': strings['runs'], 'parser': parser_rows},
                  'checks': {'scheduler_completed': True, 'string_checksums': True, 'parser_declarations': True},
                  'sha256': {'scheduler_binary': digest(scheduler), 'string_binary': digest(string),
                             'parser_binary': digest(binary), 'parser_harness': digest(source),
                             'measurement_script': digest(__file__), 'scheduler_source': digest(roots['forge-benchmarks'] / 'benchmark/scheduler_bench.c'),
                             'string_source': digest(roots['forge-benchmarks'] / 'benchmark/string_bench.c')}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('Validated timing report:', args.output)


if __name__ == '__main__':
    main()
