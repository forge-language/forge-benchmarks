#!/usr/bin/env python3
"""Finite native/blocked/coroutine/mixed dispatch comparison, with explicit pools."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def oracle(count, steps, seed):
    mask = (1 << 64) - 1
    a, b, mul, add = 6364136223846793005, 1442695040888963407, 1, 0
    while steps:
        if steps & 1:
            mul, add = mul * a & mask, (add * a + b) & mask
        a, b = a * a & mask, b * (a + 1) & mask
        steps >>= 1
    return (mul * (count * seed + count * (count - 1) // 2) + add * count) & mask


def paired(samples, metric):
    ratios = [math.log(s['baseline'][metric] / s['candidate'][metric]) for s in samples]
    rng = random.Random(20261015)
    boot = sorted(math.exp(statistics.mean(rng.choices(ratios, k=len(ratios)))) for _ in range(5000))
    return {'speedup_geomean': math.exp(statistics.mean(ratios)), 'ci95': [boot[125], boot[4874]]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['baseline', 'candidate', 'output']:
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--pairs', type=int, default=24)
    p.add_argument('--workers', type=int, nargs='+', choices=[1, 4, 8, 12], default=[1, 4, 8, 12])
    p.add_argument('--modes', nargs='+', choices=['native', 'blocked', 'coro', 'mixed'],
                   default=['native', 'blocked', 'coro', 'mixed'])
    p.add_argument('--steps', type=int, nargs='+', choices=[16, 1024], default=[16, 1024])
    p.add_argument('--candidate-first', action='store_true')
    args = p.parse_args()
    if args.pairs < 2:
        p.error('at least two pairs required')
    available = sorted(os.sched_getaffinity(0))
    if not set(range(12)) <= set(available):
        p.error('requires Linux CPUs 0..11; adapt both fixtures consistently on another host')
    order = [0, 2, 4, 6, 8, 10, 1, 3, 5, 7, 9, 11]
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    binaries = {k: getattr(args, k).resolve() for k in ['baseline', 'candidate']}
    report = {'schema': 1, 'platform': platform.platform(), 'available_cpus': available,
              'pairs': args.pairs, 'workers': args.workers, 'modes': args.modes, 'steps': args.steps,
              'candidate_first': args.candidate_first,
              'binary_sha256': {k: sha(v) for k, v in binaries.items()}, 'script_sha256': sha(__file__),
              'method': 'Alternating AB/BA; excluded warmup pair per row. All workers gated before timed release. Identical explicit counts/masks; producer shares worker CPUs. Native-only, 32 parked receivers + native, yielded coroutine controls and half-coro/half-native mixed jobs. Kernel includes warm-gate release, native publication, callbacks, stop/join, excludes creation/coro publication. Total includes lifecycle/setup and parked-receiver cleanup, excludes item setup, gate primitive setup/teardown and result verification/sort. Independent affine checksum, exact-once results and every live CPU mask checked. Individual descriptive bootstrap intervals, no multiplicity or systematic-bias guarantee.',
              'results': []}

    def invoke(label, mode, workers, steps, seed):
        mask = sorted(order[:workers])
        command = ['taskset', '-c', ','.join(map(str, mask)), str(binaries[label]), mode,
                   str(workers), '20000', str(steps), str(seed)]
        proc = subprocess.run(command, text=True, capture_output=True, timeout=60, check=True)
        row = json.loads(proc.stdout)
        expected_coro = 20000 if mode == 'coro' else (10000 if mode == 'mixed' else 0)
        assert (row['mode'], row['workers'], row['requested'], row['count'], row['steps'], row['seed'], row['coro_count']) == (mode, workers, workers, 20000, steps, seed, expected_coro), row
        assert row['checksum'] == oracle(20000, steps, seed), row
        masks = [sorted(int(cpu) for cpu in line.split('=', 1)[1].split(',') if cpu)
                 for line in proc.stderr.splitlines() if line.startswith('affinity:')]
        assert len(masks) == workers + 1 and all(cpus == mask for cpus in masks), masks
        assert len(row['per_worker_jobs']) == workers and sum(row['per_worker_jobs']) == 20000, row
        row.update(command=command, stderr=proc.stderr, observed_cpu_masks=masks)
        return row

    for workers in args.workers:
        for steps in args.steps:
            for mode in args.modes:
                warmup = {label: invoke(label, mode, workers, steps, 41) for label in binaries}
                samples = []
                for i in range(args.pairs):
                    labels = ['baseline', 'candidate'] if (i + args.candidate_first) % 2 == 0 else ['candidate', 'baseline']
                    sample = {'order': labels}
                    for label in labels:
                        sample[label] = invoke(label, mode, workers, steps, 1009 + 7919 * i)
                    samples.append(sample)
                row = {'mode': mode, 'workers': workers, 'cpu_mask': sorted(order[:workers]), 'steps': steps,
                       'count': 20000, 'warmup_excluded': warmup, 'samples': samples,
                       'paired': {metric: paired(samples, metric) for metric in
                                  ['wall_ns', 'cpu_ns', 'total_ns', 'total_cpu_ns', 'p50_ns', 'p95_ns', 'p99_ns']}}
                report['results'].append(row)
                (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
                print(json.dumps({k: row[k] for k in ['mode', 'workers', 'steps', 'paired']}), flush=True)


if __name__ == '__main__':
    main()
