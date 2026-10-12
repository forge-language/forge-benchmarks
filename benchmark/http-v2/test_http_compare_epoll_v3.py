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


if __name__ == "__main__":
    unittest.main()
