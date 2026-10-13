#!/usr/bin/env python3
"""Build a frozen generated-C invariant-divisor probe from a CPU snapshot.

This changes only remainder calls in two explicit benchmark functions. It is
an arithmetic lowering experiment; no compiler implementation is claimed.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from cpu_compare import sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output-build', type=Path, required=True)
    args = parser.parse_args()
    baseline, output = args.baseline.resolve(), args.output_build.resolve()
    if output.exists():
        parser.error('Use a fresh output build directory')
    build = json.loads((baseline / 'build.json').read_text())
    for language in ('forge', 'rust'):
        if sha(baseline / (language + '-cpu')) != build['executables'][language]['sha256']:
            raise RuntimeError('Baseline executable changed: ' + language)
    shutil.copytree(baseline, output)
    source = output / 'snapshot/kernels.c'
    text = source.read_text()
    original_hash = sha(source)
    text = text.replace('static int64_t prime_mod_pow(int64_t base, int64_t exponent, int64_t modulus) {',
                        '#include "invariant_mod_probe.h"\n\n'
                        'static int64_t prime_mod_pow(int64_t base, int64_t exponent, int64_t modulus) {\n'
                        '    const forge_probe_mod_descriptor mod_descriptor = forge_probe_mod_prepare(modulus);', 1)
    text = text.replace('    int64_t r = INT64_C(1);\n    while (\n(r < s)) {',
                        '    const forge_probe_mod_descriptor mod_descriptor = forge_probe_mod_prepare(value);\n'
                        '    int64_t r = INT64_C(1);\n    while (\n(r < s)) {', 1)
    replacements = {
        'FORGE_MOD(base, modulus)': 'forge_probe_mod(base, mod_descriptor)',
        'FORGE_MOD(FORGE_MUL(result, factor), modulus)': 'forge_probe_mod(FORGE_MUL(result, factor), mod_descriptor)',
        'FORGE_MOD(FORGE_MUL(factor, factor), modulus)': 'forge_probe_mod(FORGE_MUL(factor, factor), mod_descriptor)',
        'FORGE_MOD(FORGE_MUL(x, x), value)': 'forge_probe_mod(FORGE_MUL(x, x), mod_descriptor)',
    }
    for old, new in replacements.items():
        if text.count(old) != 1:
            raise RuntimeError('Unexpected generated-C fixture shape: ' + old)
        text = text.replace(old, new)
    source.write_text(text)
    support = Path(__file__).parent / 'cpu/invariant_mod_probe.h'
    shutil.copyfile(support, output / 'snapshot/invariant_mod_probe.h')
    command = [part.replace(str(baseline), str(output)) for part in build['commands'][1]]
    subprocess.run(command, check=True)
    build['baseline_commands'] = build['commands']
    build['commands'] = [command]
    build['fixture_sha256']['kernels.c'] = sha(source)
    build['generated_c_probe'] = {'description': __doc__, 'baseline_c_sha256': original_hash,
                                'support_sha256': sha(support), 'transform_sha256': sha(Path(__file__)),
                                'command': command, 'baseline_build_json_sha256': sha(baseline / 'build.json')}
    for language in ('forge', 'rust'):
        binary = output / (language + '-cpu')
        build['executables'][language] = {'path': str(binary), 'sha256': sha(binary)}
    (output / 'build.json').write_text(json.dumps(build, indent=2) + '\n')
    print('Generated-C probe built: ' + str(output))


if __name__ == '__main__':
    main()
