#!/usr/bin/env python3
"""Paired A/B benchmark for the Linux blocking-accept HTTP optimization."""
import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import random
import resource
import statistics
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import http_compare_v2 as v2
from cpu_compare import confidence, sha
from thread_compare import physical_cpus


def stamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def save(path, report):
    path.write_text(json.dumps(report, indent=2) + '\n')


def binary(build, name):
    path = build / name
    if not path.is_file():
        raise RuntimeError('Missing benchmark executable: ' + str(path))
    return path


def markdown(report):
    lines = [
        '# HTTP accept4 blocking-client A/B benchmark', '',
        'The candidate keeps each Linux listener nonblocking for epoll and accepts '
        'client sockets as blocking with `SOCK_CLOEXEC`, removing the per-client '
        '`F_GETFL`/`F_SETFL` conversion. The Rust control and the baseline Forge '
        'binary are unchanged. Ratios are candidate throughput divided by the '
        'paired comparison arm; 1.10 means 110% throughput.', '',
        '| Comparison | Baseline median req/s | Candidate median req/s | Paired ratio | Bootstrap 95% interval | 1.10 target |',
        '| --- | ---: | ---: | ---: | --- | --- |',
    ]
    for key, name in [('baseline', 'baseline Forge'), ('rust', 'Rust control')]:
        row = report['summary'][key]
        lo, hi = row['ci95']
        lines.append(f"| candidate / {name} | {row['reference_median_rps']:.1f} | "
                     f"{row['candidate_median_rps']:.1f} | {row['paired_ratio_median']:.4f} | "
                     f"[{lo:.4f}, {hi:.4f}] | {row['target_status']} |")
    lines += [
        '',
        f"Protocol: `{report['method']['protocol']}`; {report['method']['pairs']} "
        f"balanced triplets, {report['method']['requests_per_sample']} requests per "
        f"sample, {report['method']['concurrency']} client lanes, "
        f"{report['method']['workers']} workers, {report['method']['body_bytes']} byte body. "
        'Each measured sample followed a complete checked prewarm. Every response '
        'was compared byte-for-byte and checked through EOF; failed trials are '
        'retained and invalidate the comparison rather than being excluded or retried.', '',
        f"Candidate build: `{report['builds']['candidate']['path']}` "
        f"(Forge binary SHA-256 `{report['builds']['candidate']['forge_sha256']}`).",
        f"Baseline build: `{report['builds']['baseline']['path']}` "
        f"(Forge binary SHA-256 `{report['builds']['baseline']['forge_sha256']}`).",
        f"Rust control SHA-256 `{report['builds']['rust_sha256']}`. Raw attempts and "
        f"executed runner: `{report['raw_directory']}`.", '',
        'This is a single-host loopback prepared-response test. It does not establish '
        'general HTTP framework, TLS, routing, keepalive, or cross-machine performance.', ''
    ]
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-build', type=Path, required=True)
    parser.add_argument('--candidate-build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--concurrency', type=int, default=64)
    parser.add_argument('--body-bytes', type=int, default=32)
    parser.add_argument('--requests', type=int, default=4096)
    parser.add_argument('--pairs', type=int, default=12)
    parser.add_argument('--seed', type=int, default=20261012)
    parser.add_argument('--connect-timeout-ms', type=int, default=5000)
    args = parser.parse_args()
    if args.pairs < 6 or args.pairs % 6 or args.workers not in (1, 2, 4):
        parser.error('Use >=6 pairs divisible by 6 and 1, 2 or 4 workers')
    if args.concurrency < 1 or args.concurrency > 512 or args.requests < args.concurrency:
        parser.error('Invalid concurrency/request count')
    if args.body_bytes < 1 or args.body_bytes > 65536:
        parser.error('Invalid body size')
    output = args.output.resolve()
    if output.exists() or output.with_suffix('.md').exists():
        parser.error('Choose a fresh immutable report path')
    baseline = args.baseline_build.resolve()
    candidate = args.candidate_build.resolve()
    base_meta = json.loads((baseline / 'build.json').read_text())
    cand_meta = json.loads((candidate / 'build.json').read_text())
    for name in ('runtime', 'compiler'):
        if base_meta['artifacts'][name]['sha256'] != cand_meta['artifacts'][name]['sha256']:
            raise RuntimeError('Build arms do not share the same ' + name)
    binaries = {
        'baseline': binary(baseline, 'forge-http'),
        'candidate': binary(candidate, 'forge-http'),
        'rust': binary(baseline, 'rust-http'),
    }
    load = binary(baseline, 'http-load')
    if sha(load) != sha(binary(candidate, 'http-load')) or \
       sha(binaries['rust']) != sha(binary(candidate, 'rust-http')):
        raise RuntimeError('Build arms do not share byte-identical Rust and load controls')
    if sha(binaries['baseline']) == sha(binaries['candidate']):
        raise RuntimeError('Baseline and candidate Forge binaries are identical')
    cpus = physical_cpus()
    if args.workers + 2 > len(cpus):
        parser.error('Not enough disjoint physical CPUs')
    server_cpus = cpus[:args.workers]
    client_cpus = cpus[args.workers:args.workers + 2]
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = output.with_suffix('.raw')
    raw.mkdir()
    source = Path(__file__).read_bytes()
    (raw / 'executed-runner.py').write_bytes(source)
    report = {
        'status': 'running', 'protocol': 'prepared-http-v2-three-arm-paired-accept4',
        'started_at_utc': stamp(), 'raw_directory': str(raw),
        'runner_sha256': hashlib.sha256(source).hexdigest(),
        'builds': {
            'baseline': {'path': str(baseline), 'forge_sha256': sha(binaries['baseline']),
                         'build_metadata_sha256': sha(baseline / 'build.json'),
                         'stdlib_archive_sha256': base_meta['artifacts']['stdlib']['sha256']},
            'candidate': {'path': str(candidate), 'forge_sha256': sha(binaries['candidate']),
                          'build_metadata_sha256': sha(candidate / 'build.json'),
                          'stdlib_archive_sha256': cand_meta['artifacts']['stdlib']['sha256']},
            'rust_sha256': sha(binaries['rust']), 'load_sha256': sha(load),
        },
        'environment': {'platform': platform.platform(), 'lscpu': v2.capture(['lscpu']),
                        'physical_cpu_candidates': cpus, 'server_cpus': server_cpus,
                        'client_cpus': client_cpus, 'load_average_start': os.getloadavg(),
                        'rlimits': {name: resource.getrlimit(getattr(resource, name))
                                    for name in ('RLIMIT_NOFILE', 'RLIMIT_MEMLOCK')}},
        'method': {'protocol': 'prepared-http-v2-bounded-connect-stage-observer',
                   'workers': args.workers, 'concurrency': args.concurrency,
                   'body_bytes': args.body_bytes, 'requests_per_sample': args.requests,
                   'pairs': args.pairs, 'seed': args.seed,
                   'connect_timeout_ms': args.connect_timeout_ms,
                   'ordering': 'each of six arm permutations repeated equally; order shuffled',
                   'warmup': 'one complete checked sample immediately before each measurement',
                   'failure_policy': 'retain all rows; stop without retry; any failed trial invalidates the performance claim',
                   'scope': 'closed-loop loopback connection-per-request prepared-response endpoint'},
        'measurements': [], 'warmups': [], 'summary': {},
    }
    save(output, report)
    arms = ['baseline', 'candidate', 'rust']
    permutations = list(itertools.permutations(arms)) * (args.pairs // 6)
    rng = random.Random(args.seed)
    rng.shuffle(permutations)
    try:
        for pair, order in enumerate(permutations):
            sample_seed = rng.randrange(1, 1_000_000_000)
            for position, arm in enumerate(order):
                for kind in ('warmup', 'measurement'):
                    prefix = raw / f'p{pair:02d}-{position}-{arm}-{kind}'
                    result = v2.trial(binaries[arm], load, args.workers,
                                      args.concurrency, args.requests, sample_seed,
                                      args.body_bytes, server_cpus, client_cpus, prefix,
                                      args.connect_timeout_ms)
                    record = {'pair': pair, 'position': position, 'arm': arm,
                              'kind': kind, **result}
                    report['warmups' if kind == 'warmup' else 'measurements'].append(record)
                    save(output, report)
            print(f'Completed balanced HTTP triplet {pair + 1}/{args.pairs}', flush=True)
        measured = {arm: [row for row in report['measurements'] if row['arm'] == arm]
                    for arm in arms}
        if any(len(rows) != args.pairs or any(row['status'] != 'passed' for row in rows)
               for rows in measured.values()):
            raise RuntimeError('Incomplete or failed HTTP measurement; no performance claim')
        for reference in ('baseline', 'rust'):
            ratios = []
            for pair in range(args.pairs):
                pair_rows = {row['arm']: row for row in report['measurements']
                             if row['pair'] == pair}
                ratios.append(pair_rows['candidate']['requests_per_second'] /
                              pair_rows[reference]['requests_per_second'])
            interval = confidence(ratios, args.seed + len(reference))
            median = statistics.median(ratios)
            report['summary'][reference] = {
                'reference_median_rps': statistics.median(
                    row['requests_per_second'] for row in measured[reference]),
                'candidate_median_rps': statistics.median(
                    row['requests_per_second'] for row in measured['candidate']),
                'paired_ratios': ratios, 'paired_ratio_median': median, 'ci95': interval,
                'target_status': 'supported for this configuration' if interval[0] >= 1.10
                                 else 'below target' if interval[1] < 1.10 else 'inconclusive',
            }
        report['status'] = 'completed'
        output.with_suffix('.md').write_text(markdown(report))
    except BaseException as error:
        report.update(status='failed_no_claim', error=repr(error))
        raise
    finally:
        report['finished_at_utc'] = stamp()
        report['environment']['load_average_end'] = os.getloadavg()
        save(output, report)


if __name__ == '__main__':
    main()
