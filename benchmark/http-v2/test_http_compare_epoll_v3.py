#!/usr/bin/env python3
"""Focused V3 runner checks for observer footer and TSV diagnostics."""
import importlib.util
from pathlib import Path
import sys
import unittest


RUNNER = Path(__file__).resolve().parents[1] / "http_compare_epoll_v3.py"
sys.path.insert(0, str(RUNNER.parent / "http-v2"))
sys.path.insert(0, str(RUNNER.parent))
SPEC = importlib.util.spec_from_file_location("http_compare_epoll_v3", RUNNER)
V3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V3)


class EpollRunnerValidationTests(unittest.TestCase):
    def setUp(self):
        self.columns = ["id", "failed_stage", "error"]

    def test_connect_errors_are_reported_as_observer_failure(self):
        rows = [
            {"id": "0", "failed_stage": "connect", "error": "stage deadline exceeded"},
            {"id": "1", "failed_stage": "", "error": ""},
        ]
        with self.assertRaisesRegex(
            RuntimeError,
            r"requested=4, attempted=2, completed=1, errors=1; first failure id=0 stage=connect",
        ):
            V3.validate_request_rows(self.columns, rows, self.columns, 4, 2, 1, 1)

    def test_footer_and_tsv_row_count_must_agree(self):
        with self.assertRaisesRegex(RuntimeError, r"row count 1 does not match observer footer attempted=2"):
            V3.validate_request_rows(
                self.columns,
                [{"id": "0", "failed_stage": "", "error": ""}],
                self.columns,
                2,
                2,
                2,
                0,
            )

    def test_complete_successful_vector_is_accepted(self):
        rows = [
            {"id": "0", "failed_stage": "", "error": ""},
            {"id": "1", "failed_stage": "", "error": ""},
        ]
        self.assertIsNone(V3.validate_request_rows(self.columns, rows, self.columns, 2, 2, 2, 0))

    def test_peaks_are_observations_instead_of_the_configured_ceiling(self):
        self.assertEqual(V3.parse_footer(b"1000\t128000\t0\t390\t256\t256", 128000, 128000),
                         [1000, 128000, 0, 390, 256, 256])

    def test_old_ungauged_footer_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "requires actual observed"):
            V3.parse_footer(b"1000\t10\t0", 10, 10)

    def test_inconsistent_peak_and_counter_combinations_are_rejected(self):
        for footer in [b"0\t10\t0\t4\t4\t4", b"1\t10\t11\t4\t4\t4",
                       b"1\t1001\t0\t4\t4\t4", b"1\t10\t0\t11\t4\t4",
                       b"1\t10\t0\t4\t5\t4", b"1\t10\t0\t4\t4\t5",
                       b"1\t10\t0\t4\t1\t1", b"1\t10\t0\t0\t0\t0",
                       b"1\t1000\t0\t1000\t900\t257"]:
            with self.subTest(footer=footer), self.assertRaisesRegex(RuntimeError, "bounds"):
                V3.parse_footer(footer, 1000, 1000)

    def test_failure_before_any_socket_is_registered_is_valid(self):
        self.assertEqual(V3.parse_footer(b"1000\t1\t1\t0\t0\t0", 10, 10),
                         [1000, 1, 1, 0, 0, 0])


if __name__ == "__main__":
    unittest.main()
