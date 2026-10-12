#!/usr/bin/env python3
"""Measure tested concurrent-client capacity and throughput for prepared HTTP.

Uses the separately versioned V2 bounded observer. All trials, including
overload failures and their completed rows, are retained. A failed trial is a
capacity observation and never enters the error-free throughput ratio.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import random
import statistics
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import http_compare_v2 as v2
from cpu_compare import confidence, sha
from thread_compare import physical_cpus

MAX_TESTED_CONCURRENCY = 32768


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def display_number(value, digits=1):
    return 'n/a' if value is None else f'{value:.{digits}f}'


def read_sample(binary, load, workers, concurrency, requests, seed, body_bytes,
                server_cpus, client_cpus, prefix, connect_timeout_ms):
    status, exception = 'passed', None
    try:
        result = v2.trial(binary, load, workers, concurrency, requests, seed,
                          body_bytes, server_cpus, client_cpus, prefix,
                          connect_timeout_ms)
    except BaseException as error:
        status, exception = 'failed', repr(error)
        result = json.loads(prefix.with_suffix('.json').read_text())
    samples = prefix.with_name(prefix.name + '-requests.tsv')
    with samples.open(newline='') as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    successes = [row for row in rows if not row['error'] and not row['failed_stage']
                 and int(row['response_bytes']) == result['expected_response_bytes']]
    failures = [row for row in rows if row not in successes]
    elapsed = result.get('elapsed_ns') or result.get('observer_wall_ns') or 0
    success_count = len(successes)
    response_bytes = sum(int(row['response_bytes']) for row in successes)
    latencies = [int(row['latency_ns']) for row in successes]
    result.update({
        'status': status,
        'trial_exception': exception,
        'attempted_rows': len(rows),
        'successful_rows': success_count,
        'error_rows': len(failures),
        'error_rate': len(failures) / len(rows) if rows else None,
        'successful_requests_per_second': success_count * 1e9 / elapsed if elapsed else None,
        'successful_response_bytes': response_bytes,
        'successful_response_bytes_per_second': response_bytes * 1e9 / elapsed if elapsed else None,
        'successful_latency_median_ns': statistics.median(latencies) if latencies else None,
        'successful_latency_p95_ns': percentile(latencies, .95),
        'successful_latency_p99_ns': percentile(latencies, .99),
        'errors_by_stage': {},
        'request_samples_sha256': sha(samples) if samples.exists() else None,
    })
    for row in failures:
        key = row['failed_stage'] or 'response_validation'
        result['errors_by_stage'][key] = result['errors_by_stage'].get(key, 0) + 1
    return result


def markdown(report, output):
    lines = [
        '# Prepared HTTP capacity and throughput — observer protocol V2', '',
        'This reports the largest tested concurrency level with all requests '
        'successful in every measured repeat. Each client lane holds at most '
        'one connection at a time; concurrency therefore means simultaneous '
        'in-flight loopback clients for this connection-per-request workload. '
        'It is not a general internet-facing user limit.', '',
        '| Body bytes | Workers | Concurrent clients | Forge clean repeats | Rust clean repeats | '
        'Forge successful req/s (median) | Rust successful req/s (median) | '
        'Forge response MB/s | Rust response MB/s | Error-free max observed |',
        '| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |',
    ]
    for row in report['summary']:
        lines.append(
            f"| {row['body_bytes']} | {row['workers']} | {row['concurrency']} | "
            f"{row['forge_clean_repeats']}/{row['repeats']} | "
            f"{row['rust_clean_repeats']}/{row['repeats']} | "
            f"{display_number(row['forge_median_success_rps'])} | "
            f"{display_number(row['rust_median_success_rps'])} | "
            f"{display_number(row['forge_median_response_bytes_per_second']/1e6 if row['forge_median_response_bytes_per_second'] is not None else None, 3)} | "
            f"{display_number(row['rust_median_response_bytes_per_second']/1e6 if row['rust_median_response_bytes_per_second'] is not None else None, 3)} | "
            f"{row['error_free_max_observed']} |"
        )
    lines += [
        '',
        'Every response is byte-compared with an independently generated expected '
        'packet and checked through EOF. A failed trial retains every completed '
        'row and its error stage; failed and partial trials are excluded from the '
        'error-free throughput medians. No outlier trimming or retry is used. '
        'The V2 observer bounds connect at the configured timeout, separates '
        'connect/setup/write/read/EOF time, and writes each completed attempt '
        'immediately. Its logging and loopback client work are included in the '
        'observer interval.', '',
        'Capacity is a tested bound: if the highest tested level passes, the '
        'result is “at least N”; it does not claim the absolute maximum. '
        'Throughput reports successful requests/s and successful response '
        'payload bytes/s. Latency medians and p95/p99 are retained per trial in '
        'the JSON and raw TSV files. These are prepared-response endpoints, not '
        'full HTTP framework, TLS, routing, database or keepalive results.', '',
        f"Protocol: `{report['method']['protocol']}`. Raw JSON and TSV attempts: "
        f"`{report['raw_directory']}`. Build provenance: `{report['build_directory']}`.",
        f"Executed runner SHA-256: `{report['runner_sha256']}`.", '',
    ]
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--concurrency', type=int, nargs='+', default=[16, 64, 128, 256, 512])
    parser.add_argument('--body-bytes', type=int, nargs='+', default=[32, 4096])
    parser.add_argument('--requests', type=int, default=4096)
    parser.add_argument('--repeats', type=int, default=8)
    parser.add_argument('--connect-timeout-ms', type=int, default=5000)
    parser.add_argument('--seed', type=int, default=20261012)
    args = parser.parse_args()
    if (args.workers not in (1, 2, 4) or args.repeats < 3 or
            args.repeats % 2 or not args.concurrency or
            len(set(args.concurrency)) != len(args.concurrency) or
            any(c < 1 or c > MAX_TESTED_CONCURRENCY for c in args.concurrency) or
            args.requests < max(args.concurrency) or
            any(b < 1 or b > 65536 for b in args.body_bytes) or
            not 1 <= args.connect_timeout_ms <= 60000):
        parser.error('Invalid workers, concurrency, body size, repeats, requests or timeout')
    build = args.build_dir.resolve()
    build_meta_path = build / 'build.json'
    if not build_meta_path.is_file():
        parser.error('Build directory must contain the V2 build.json provenance file')
    metadata = json.loads(build_meta_path.read_text())
    for executable in ('forge-http', 'rust-http', 'http-load'):
        if not (build / executable).is_file():
            parser.error('Missing built executable: ' + executable)
    output = args.output.resolve()
    if output.exists() or output.with_suffix('.md').exists():
        parser.error('Choose a fresh output path; reports are immutable')
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = output.with_suffix('.raw')
    raw.mkdir()
    source = Path(__file__).read_bytes()
    (raw / 'executed-runner.py').write_bytes(source)
    cpus = physical_cpus()
    if args.workers + 2 > len(cpus):
        parser.error('Host does not have enough disjoint physical CPUs for server and client')
    server_cpus = cpus[:args.workers]
    client_cpus = cpus[args.workers:args.workers + 2]
    report = {
        'status': 'running',
        'protocol': 'prepared-http-v2-capacity-sweep',
        'build_directory': str(build),
        'build_sha256': sha(build_meta_path),
        'runner_sha256': hashlib.sha256(source).hexdigest(),
        'raw_directory': str(raw),
        'environment': {'physical_cpu_candidates': cpus, 'server_cpus': server_cpus,
                        'client_cpus': client_cpus},
        'method': {'protocol': 'prepared-http-v2-capacity-sweep',
                   'observer_protocol': 'prepared-http-v2-bounded-connect-stage-observer',
                   'workers': args.workers, 'concurrency': args.concurrency,
                   'body_bytes': args.body_bytes, 'requests_per_trial': args.requests,
                   'repeats': args.repeats, 'connect_timeout_ms': args.connect_timeout_ms,
                   'capacity_definition': 'highest tested concurrency with all requests exact and zero errors in every measured repeat',
                   'scope': 'closed-loop loopback HTTP connection-per-request; each client has at most one in-flight connection',
                   'order': 'balanced Forge/Rust order per workload and repeat; one complete checked prewarm immediately before each measurement',
                   'failures': 'retained as capacity outcomes; no retry; failed/partial samples do not enter error-free throughput ratios'},
        'samples': [], 'summary': [],
    }
    v2.save(output, report)
    binaries = {'forge': build / 'forge-http', 'rust': build / 'rust-http'}
    load = build / 'http-load'
    rng = random.Random(args.seed)
    orders = {}
    try:
        configurations = [(body, concurrency) for body in args.body_bytes
                          for concurrency in args.concurrency]
        for config_index, (body_size, concurrency) in enumerate(configurations):
            order_bits = [False, True] * (args.repeats // 2)
            rng.shuffle(order_bits)
            orders[(body_size, concurrency)] = order_bits
            for repeat in range(args.repeats):
                seed = rng.randrange(1, 1_000_000_000)
                order = ['forge', 'rust'] if order_bits[repeat] else ['rust', 'forge']
                for position, language in enumerate(order):
                    for kind in ('prewarm', 'measurement'):
                        prefix = raw / (f'w{args.workers}-b{body_size}-c{concurrency}-'
                                        f'r{repeat:02d}-{position}-{language}-{kind}')
                        sample = read_sample(
                            binaries[language], load, args.workers, concurrency,
                            args.requests, seed, body_size, server_cpus, client_cpus,
                            prefix, args.connect_timeout_ms)
                        sample.update(language=language, repeat=repeat, order=position,
                                      kind=kind, body_bytes=body_size,
                                      concurrency=concurrency)
                        report['samples'].append(sample)
                        v2.save(output, report)
            print(f'Completed capacity config {config_index + 1}/{len(configurations)} '
                  f'(body={body_size}, concurrency={concurrency})', flush=True)
        for body_size, concurrency in configurations:
            measured = [row for row in report['samples']
                        if row['kind'] == 'measurement' and
                        (row['body_bytes'], row['concurrency']) == (body_size, concurrency)]
            by_language = {name: [row for row in measured if row['language'] == name]
                           for name in binaries}
            clean = {name: [row for row in values if row['status'] == 'passed' and
                            row['successful_rows'] == args.requests and row['error_rows'] == 0]
                     for name, values in by_language.items()}
            summary = {
                'body_bytes': body_size, 'workers': args.workers,
                'concurrency': concurrency, 'repeats': args.repeats,
                'forge_clean_repeats': len(clean['forge']),
                'rust_clean_repeats': len(clean['rust']),
                'forge_median_success_rps': statistics.median(
                    [row['successful_requests_per_second'] for row in clean['forge']]) if clean['forge'] else None,
                'rust_median_success_rps': statistics.median(
                    [row['successful_requests_per_second'] for row in clean['rust']]) if clean['rust'] else None,
                'forge_median_response_bytes_per_second': statistics.median(
                    [row['successful_response_bytes_per_second'] for row in clean['forge']]) if clean['forge'] else None,
                'rust_median_response_bytes_per_second': statistics.median(
                    [row['successful_response_bytes_per_second'] for row in clean['rust']]) if clean['rust'] else None,
                'forge_median_latency_ns': statistics.median(
                    [row['successful_latency_median_ns'] for row in clean['forge']]) if clean['forge'] else None,
                'forge_p99_latency_ns_median': statistics.median(
                    [row['successful_latency_p99_ns'] for row in clean['forge']]) if clean['forge'] else None,
                'rust_median_latency_ns': statistics.median(
                    [row['successful_latency_median_ns'] for row in clean['rust']]) if clean['rust'] else None,
                'rust_p99_latency_ns_median': statistics.median(
                    [row['successful_latency_p99_ns'] for row in clean['rust']]) if clean['rust'] else None,
                'capacity_status': 'error-free for every measured repeat' if
                    len(clean['forge']) == args.repeats and len(clean['rust']) == args.repeats
                    else 'one or more measured repeats failed',
            }
            paired = []
            for repeat in range(args.repeats):
                pair = {name: next(row for row in by_language[name]
                                   if row['repeat'] == repeat) for name in binaries}
                if all(row['status'] == 'passed' and row['error_rows'] == 0 and
                       row['successful_rows'] == args.requests for row in pair.values()):
                    paired.append(pair['rust']['successful_requests_per_second'] /
                                  pair['forge']['successful_requests_per_second'])
            summary['clean_paired_rps_ratios'] = paired
            if len(paired) == args.repeats:
                summary['rust_over_forge_rps_ratio_median'] = statistics.median(paired)
                summary['rust_over_forge_rps_ratio_ci95'] = confidence(paired, args.seed + body_size + concurrency)
            report['summary'].append(summary)
            v2.save(output, report)
        for body_size in args.body_bytes:
            body_rows = [row for row in report['summary'] if row['body_bytes'] == body_size]
            fully_clean = [row['concurrency'] for row in body_rows
                           if row['forge_clean_repeats'] == args.repeats and
                           row['rust_clean_repeats'] == args.repeats]
            max_clean = max(fully_clean) if fully_clean else None
            failed_above = [row['concurrency'] for row in body_rows
                            if max_clean is not None and row['concurrency'] > max_clean and
                            (row['forge_clean_repeats'] < args.repeats or
                             row['rust_clean_repeats'] < args.repeats)]
            bound = (f'at least {max_clean}' if max_clean == max(args.concurrency) else
                     f'{max_clean}; failures observed at {min(failed_above)}' if failed_above else
                     str(max_clean)) if max_clean is not None else 'no error-free level observed'
            for row in body_rows:
                row['error_free_max_observed'] = bound
        report['status'] = 'completed_with_capacity_outcomes'
        report['finished_at_utc'] = v2.stamp()
        v2.save(output, report)
        output.with_suffix('.md').write_text(markdown(report, output))
    except BaseException as error:
        report.update(status='failed_with_retained_samples', error=repr(error),
                      finished_at_utc=v2.stamp())
        v2.save(output, report)
        raise


if __name__ == '__main__':
    main()
