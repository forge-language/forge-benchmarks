#!/usr/bin/env python3
"""Paired finite native-pool measurements under inherited Linux CPU masks."""
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
    """Independent affine exponentiation, rather than the fixture's LCG loop."""
    mask = (1 << 64) - 1
    a, b, mul, add = 6364136223846793005, 1442695040888963407, 1, 0
    while steps:
        if steps & 1:
            mul, add = mul * a & mask, (add * a + b) & mask
        a, b = a * a & mask, b * (a + 1) & mask
        # The simultaneous assignment uses the old a in the increment formula.
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
    p.add_argument('--mask-sizes', type=int, nargs='+', choices=[1, 2, 4, 12], default=[1, 2, 4, 12])
    p.add_argument('--steps', type=int, nargs='+', choices=[16, 1024], default=[16, 1024])
    p.add_argument('--candidate-first', action='store_true', help='reverse the first AB/BA pair for a focused confirmation')
    args = p.parse_args()
    if args.pairs < 2:
        p.error('at least two pairs required')
    available = sorted(os.sched_getaffinity(0))
    if not set(range(12)) <= set(available):
        p.error('fixture requires Linux CPUs 0..11; adapt both masks for another host')
    online = os.sysconf('SC_NPROCESSORS_ONLN')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    binaries = {k: getattr(args, k).resolve() for k in ['baseline', 'candidate']}
    report = {'schema': 1, 'platform': platform.platform(), 'available_cpus': available,
              'online_cpus': online, 'pairs': args.pairs,
              'selected_mask_sizes': args.mask_sizes, 'selected_steps': args.steps,
              'candidate_first': args.candidate_first,
              'binary_sha256': {k: sha(v) for k, v in binaries.items()},
              'script_sha256': sha(__file__),
              'method': 'Alternating AB/BA; one excluded warmup pair per row; independent affine checksum, exact-once checks and every live thread CPU mask verified. Fixture gates one warmup job on every worker before release. Kernel includes submit, callbacks, stop/join. Total includes creation, start, warmup, affinity inspection and destroy; excludes item setup, result verification, warmup primitive setup/teardown and percentile sorting. Shared host, producer shares worker CPUs.',
              'results': []}

    def invoke(label, mask, requested, steps, seed):
        command = ['taskset', '-c', ','.join(map(str, mask)), str(binaries[label]), str(requested), '20000', str(steps), str(seed)]
        proc = subprocess.run(command, text=True, capture_output=True, timeout=60, check=True)
        row = json.loads(proc.stdout)
        expected_workers = requested or (online if label == 'baseline' else len(mask))
        assert row['requested'] == requested and row['workers'] == expected_workers, row
        assert row['count'] == 20000 and row['steps'] == steps and row['seed'] == seed, row
        assert row['checksum'] == oracle(20000, steps, seed), row
        observed = [sorted(int(cpu) for cpu in line.split('=', 1)[1].split(',') if cpu)
                    for line in proc.stderr.splitlines() if line.startswith('affinity:')]
        assert len(observed) == expected_workers + 1 and all(cpus == mask for cpus in observed), observed
        assert len(row['per_worker_jobs']) == expected_workers and sum(row['per_worker_jobs']) == 20000, row
        row.update(command=command, stderr=proc.stderr, observed_cpu_masks=observed)
        return row

    masks = [[11], [8, 10], [4, 6, 8, 10], list(range(12))]
    for mask in masks:
        if len(mask) not in args.mask_sizes:
            continue
        for steps in args.steps:
            for requested in [0, len(mask)]:
                samples, warmup = [], {}
                for label in binaries:
                    warmup[label] = invoke(label, mask, requested, steps, 41)
                for i in range(args.pairs):
                    seed = 1009 + 7919 * i
                    labels = ['baseline', 'candidate'] if (i + args.candidate_first) % 2 == 0 else ['candidate', 'baseline']
                    sample = {'order': labels}
                    for label in labels:
                        sample[label] = invoke(label, mask, requested, steps, seed)
                    samples.append(sample)
                row = {'cpu_mask': mask, 'requested_workers': requested, 'steps': steps,
                       'count': 20000, 'warmup_excluded': warmup, 'samples': samples,
                       'paired': {metric: paired(samples, metric) for metric in
                                  ['wall_ns', 'cpu_ns', 'total_ns', 'total_cpu_ns', 'p50_ns', 'p95_ns', 'p99_ns']}}
                report['results'].append(row)
                (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
                print(json.dumps({k: row[k] for k in ['cpu_mask', 'requested_workers', 'steps', 'paired']}), flush=True)


if __name__ == '__main__':
    main()
