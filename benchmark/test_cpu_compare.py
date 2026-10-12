import unittest

from cpu_compare import signed_remainder, weighted_reference, wrap_i64, reference


class SignedReferenceTest(unittest.TestCase):
    def test_remainder_matches_truncation_toward_zero(self):
        self.assertEqual(signed_remainder(-1, 13), -1)
        self.assertEqual(signed_remainder(-13, 13), 0)
        self.assertEqual(signed_remainder(-14, 13), -1)
        self.assertEqual(signed_remainder(14, 13), 1)

    def test_weighted_period_matches_direct_signed_remainder(self):
        edge = (-(1 << 63), -(1 << 63) + 1, -1001, -26, -1, 0, 1, 26, 1001,
                (1 << 63) - 2, (1 << 63) - 1)
        for n in (0, 1, 12, 13, 25, 26, 27, 1024):
            for seed in edge:
                for offset in (-12, -1, 0, 1, 12, (1 << 63) - 1):
                    expected = sum(
                        (65 + signed_remainder(wrap_i64(i + seed), 26)) *
                        (signed_remainder(wrap_i64(i + offset), 13) + 1)
                        for i in range(n))
                    self.assertEqual(weighted_reference(n, seed, offset), wrap_i64(expected))

    def test_scan_reference_supports_negative_results(self):
        self.assertLess(reference('scan', 1, 1, -100000), 0)
        self.assertEqual(reference('scan', 0, 10, -(1 << 63)), -(1 << 63))
        self.assertGreater(reference('scan', 1, 1, -(1 << 63)), 0)

    def test_lcg_matches_wrapping_scalar_steps(self):
        for n, rounds in ((0, 10), (1, 1), (3, 4), (11, 7), (-1, 10), (10, -1)):
            for seed in (-(1 << 63), -100000, -1, 0, 1, 100000, (1 << 63) - 1):
                value = seed
                for _ in range(max(n, 0) * max(rounds, 0)):
                    value = signed_remainder(wrap_i64(value * 48271), 2147483647)
                self.assertEqual(reference('lcg', n, rounds, seed), value)


if __name__ == '__main__':
    unittest.main()
