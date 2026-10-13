#!/usr/bin/env python3
"""Check the prototype against native signed % and its exceptional inputs."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int64_t __forge_mod_i64(int64_t value, int64_t divisor) {
    if (!divisor || (value == INT64_MIN && divisor == -1)) {
        fputs("Forge integer division\n", stderr); exit(EXIT_FAILURE);
    }
    return value % divisor;
}
#include "invariant_mod_probe.h"
static uint64_t random_bits(uint64_t *state) {
    *state ^= *state << 13; *state ^= *state >> 7; *state ^= *state << 17;
    return *state;
}
static size_t check_count;
static void check(int64_t n, int64_t d) {
    forge_probe_mod_descriptor descriptor = forge_probe_mod_prepare(d);
    if (!d || (n == INT64_MIN && d == -1)) return;
    int64_t actual = forge_probe_mod(n, descriptor), expected = n % d;
    if (actual != expected) {
        fprintf(stderr, "mismatch: %lld %% %lld: %lld != %lld\n",
                (long long)n, (long long)d, (long long)actual, (long long)expected);
        exit(2);
    }
    ++check_count;
}
int main(int argc, char **argv) {
    if (argc == 3) {
        int64_t n = strtoll(argv[1], NULL, 10), d = strtoll(argv[2], NULL, 10);
        printf("%lld\n", (long long)forge_probe_mod(n, forge_probe_mod_prepare(d)));
        return 0;
    }
    const int64_t edges[] = {INT64_MIN, INT64_MIN+1, -1373653, -26, -2, -1, 0,
                            1, 2, 3, 5, 26, 1373653, INT32_MAX, INT64_MAX-1, INT64_MAX};
    for (size_t i = 0; i < sizeof(edges)/sizeof(*edges); ++i)
        for (size_t j = 0; j < sizeof(edges)/sizeof(*edges); ++j) {
            check(edges[i], edges[j]);
        }
    for (unsigned shift = 1; shift < 63; ++shift) {
        int64_t pivot = INT64_C(1) << shift;
        for (int delta = -1; delta <= 1; ++delta) {
            int64_t d = pivot + delta;
            check(INT64_MAX, d); check(INT64_MAX-1, d); check(d-1, d);
            check(d, d); check(-d, d);
        }
    }
    for (int dn = -2; dn <= 2; ++dn)
        for (int dd = -2; dd <= 2; ++dd)
            check((INT64_C(1) << 43) + dn, (INT64_C(1) << 21) + dd);
    uint64_t state = UINT64_C(20261012);
    for (unsigned i = 0; i < 300000; ++i) {
        uint64_t bits = random_bits(&state); int64_t n, d;
        memcpy(&n, &bits, sizeof(n)); bits = random_bits(&state);
        memcpy(&d, &bits, sizeof(d));
        if (i % 3 == 0) d = (int64_t)(bits % 2000000) + 1;
        check(n, d);
    }
    printf("%zu native signed-remainder oracle cases passed\n", check_count);
    return 0;
}
'''


class InvariantModProbeTest(unittest.TestCase):
    def test_oracle_and_traps(self):
        header = Path(__file__).parent / 'cpu'
        for optimization, fallback, hint in [('0', False, False), ('3', False, False), ('3', True, False),
                                             ('0', False, True), ('3', False, True)]:
            with self.subTest(optimization=optimization, portable_fallback=fallback, bounded_hint=hint), tempfile.TemporaryDirectory() as directory:
                source, binary = Path(directory)/'check.c', Path(directory)/'check'
                source.write_text(SOURCE)
                command = [os.environ.get('CC', 'gcc'), '-std=gnu11', '-O'+optimization,
                           '-fsanitize=undefined', '-fno-sanitize-recover=all', '-I', str(header),
                           str(source), '-o', str(binary)]
                if fallback:
                    command.insert(1, '-U__SIZEOF_INT128__')
                if hint:
                    command.insert(1, '-DFORGE_PROBE_BOUNDED_HINT')
                subprocess.run(command, check=True)
                result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
                self.assertIn('301194 native signed-remainder oracle cases passed', result.stdout)
                for n, d in [(0, 0), (1, 0), (-1, 0), (-(1<<63), -1)]:
                    result = subprocess.run([str(binary), str(n), str(d)], capture_output=True)
                    self.assertEqual(result.returncode, 1, (optimization, fallback, n, d, result.stderr))
                    self.assertEqual(result.stderr, b'Forge integer division\n')


if __name__ == '__main__':
    unittest.main()
