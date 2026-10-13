"""Source-integrity regression for native Windows/MSYS2 checkout filters."""
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cross_os_cpu_compare as runner


class CheckoutFilterTests(unittest.TestCase):
    def test_crlf_is_clean_but_content_edits_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.run(['git', '-C', str(root), *args], check=True,
                                      capture_output=True, text=True)
            git('init')
            git('config', 'core.autocrlf', 'false')
            git('config', 'user.name', 'Fixture')
            git('config', 'user.email', 'fixture@example.invalid')
            source = root / 'source.fg'
            source.write_bytes(b'first\nsecond\n')
            git('add', 'source.fg')
            git('commit', '-m', 'Fixture')
            source.write_bytes(b'first\r\nsecond\r\n')
            self.assertTrue(git('status', '--porcelain').stdout)
            with patch.object(runner, 'os', SimpleNamespace(name='nt')):
                self.assertEqual(runner.source_revision(root)['tracked_dirty'], '')
                source.write_bytes(b'first\r\nactual change\r\n')
                self.assertTrue(runner.source_revision(root)['tracked_dirty'])


if __name__ == '__main__':
    unittest.main()
