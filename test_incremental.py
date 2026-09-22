"""Run with python3 test_incremental.py; all data lives in temporary directories."""
import importlib.util
import os
from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
loader = SourceFileLoader("cleaner", str(Path(__file__).resolve().with_name("codex-claude-code-secret-cleaner")))
spec = importlib.util.spec_from_loader(loader.name, loader)
cleaner = importlib.util.module_from_spec(spec)
loader.exec_module(cleaner)


class IncrementalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="secret-cleaner-test-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.sessions = self.root / "sessions"
        self.sessions.mkdir()
        self.checkpoint = self.root / "checkpoint"
        for name, value in {
            "STATE_DIR": self.root,
            "LOG_FILE": self.root / "log",
            "LOCK_FILE": self.root / "lock",
            "CHECKPOINT_FILE": self.checkpoint,
        }.items():
            p = patch.object(cleaner, name, value, create=True)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(cleaner, "default_paths", return_value=[self.sessions])
        p.start()
        self.addCleanup(p.stop)

    def run_scan(self, *args):
        with patch.object(sys, "argv", ["cleaner", "--incremental", "--quiet", *args]):
            return cleaner.main()

    def secret_file(self, name):
        path = self.sessions / name
        path.write_text("AKIA" + "Z" * 16 + "\n")
        return path

    def test_first_run_redacts_and_unchanged_run_reads_no_content(self):
        path = self.secret_file("session.jsonl")
        self.assertEqual(self.run_scan(), 0)
        self.assertEqual(path.read_text(), cleaner.MASK + "\n")
        # A rewrite after the checkpoint legitimately gets checked once more.
        self.run_scan()
        with patch.object(cleaner.subprocess, "run", side_effect=AssertionError("content prefilter ran")):
            self.assertEqual(self.run_scan(), 0)

    def test_changed_and_new_backdated_files_are_selected(self):
        old = self.secret_file("old.jsonl")
        changed = self.secret_file("changed.jsonl")
        cutoff = time.time_ns()
        time.sleep(0.01)
        changed.write_text("updated\n")
        new = self.secret_file("new.jsonl")
        os.utime(new, (1, 1))
        with patch.object(cleaner.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(set(cleaner.candidate_files([self.sessions], cutoff)), {changed, new})
        self.assertTrue(old.exists())

    def test_dry_run_and_failure_do_not_advance_checkpoint(self):
        path = self.secret_file("session.jsonl")
        self.run_scan("--dry-run")
        self.assertFalse(self.checkpoint.exists())
        self.assertNotIn(cleaner.MASK, path.read_text())
        self.checkpoint.write_text("1\n")
        with patch.object(cleaner, "redact_file", side_effect=OSError("simulated read failure")):
            with self.assertRaises(OSError):
                self.run_scan()
        self.assertEqual(self.checkpoint.read_text(), "1\n")
        with self.assertRaises(FileNotFoundError):
            cleaner.count_file_redactions(self.sessions / "missing", cleaner.build_patterns())

    def test_checkpoint_records_start_and_retains_mid_scan_changes(self):
        path = self.secret_file("session.jsonl")
        started = time.time_ns()
        def modified_during_scan(*args):
            time.sleep(0.01)
            path.write_text("appended after the scan began\n")
            return 0
        with patch.object(cleaner.time, "time_ns", return_value=started):
            with patch.object(cleaner, "redact_file", side_effect=modified_during_scan):
                self.run_scan()
        self.assertEqual(int(self.checkpoint.read_text()), started)
        with patch.object(cleaner.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(cleaner.candidate_files([self.sessions], started), [path])

    def test_custom_scope_cannot_advance_global_checkpoint(self):
        with self.assertRaises(SystemExit) as error:
            self.run_scan("--path", str(self.sessions))
        self.assertEqual(error.exception.code, 2)
        self.assertFalse(self.checkpoint.exists())

    def test_manual_full_scan_still_redacts_without_changing_checkpoint(self):
        path = self.secret_file("session.jsonl")
        self.checkpoint.write_text("1\n")
        with patch.object(sys, "argv", ["cleaner", "--quiet", "--path", str(self.sessions)]):
            self.assertEqual(cleaner.main(), 0)
        self.assertEqual(path.read_text(), cleaner.MASK + "\n")
        self.assertEqual(self.checkpoint.read_text(), "1\n")


if __name__ == "__main__":
    unittest.main()
