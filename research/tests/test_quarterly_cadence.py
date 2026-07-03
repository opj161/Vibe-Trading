"""Unit tests for research/quarterly_cadence.py's driver logic. Never
actually runs the heavy underlying research scripts -- subprocess is mocked."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import quarterly_cadence  # noqa: E402


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="ok", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestRunItem:
    def test_success_reports_ok_true(self, monkeypatch):
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompletedProcess(returncode=0))
        out = quarterly_cadence.run_item("venue_funding", Path("."), ["true"], timeout=10)
        assert out["ok"] is True

    def test_nonzero_exit_reports_ok_false(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run", lambda *a, **k: _FakeCompletedProcess(returncode=1, stderr="boom"),
        )
        out = quarterly_cadence.run_item("venue_funding", Path("."), ["false"], timeout=10)
        assert out["ok"] is False
        assert "boom" in out["stderr_tail"]

    def test_timeout_reports_ok_false_without_raising(self, monkeypatch):
        def _raise(*a, **k):
            raise subprocess.TimeoutExpired(cmd="x", timeout=10)
        monkeypatch.setattr(subprocess, "run", _raise)
        out = quarterly_cadence.run_item("h1_btc", Path("."), ["sleep", "100"], timeout=10)
        assert out["ok"] is False
        assert "TIMEOUT" in out["stderr_tail"]

    def test_unexpected_exception_does_not_propagate(self, monkeypatch):
        def _raise(*a, **k):
            raise RuntimeError("unexpected")
        monkeypatch.setattr(subprocess, "run", _raise)
        out = quarterly_cadence.run_item("capacity", Path("."), ["x"], timeout=10)
        assert out["ok"] is False
        assert "unexpected" in out["stderr_tail"]


class TestAppendLog:
    def test_creates_file_with_header_on_first_write(self, tmp_path, monkeypatch):
        monkeypatch.setattr(quarterly_cadence, "LOG_PATH", tmp_path / "log.md")
        quarterly_cadence.append_log([{"name": "venue_funding", "ok": True, "stderr_tail": ""}])

        content = (tmp_path / "log.md").read_text()
        assert "# Quarterly Cadence Run Log" in content
        assert "venue_funding" in content
        assert "OK" in content

    def test_appends_without_duplicating_header(self, tmp_path, monkeypatch):
        monkeypatch.setattr(quarterly_cadence, "LOG_PATH", tmp_path / "log.md")
        quarterly_cadence.append_log([{"name": "a", "ok": True, "stderr_tail": ""}])
        quarterly_cadence.append_log([{"name": "b", "ok": False, "stderr_tail": "oops"}])

        content = (tmp_path / "log.md").read_text()
        assert content.count("# Quarterly Cadence Run Log") == 1
        assert "a" in content and "b" in content
        assert "FAILED" in content
        assert "oops" in content


class TestMainSkipsRequestedItems(object):
    def test_skip_flag_excludes_named_items(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(quarterly_cadence, "LOG_PATH", tmp_path / "log.md")
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompletedProcess(returncode=0))
        monkeypatch.setattr(
            sys, "argv",
            ["quarterly_cadence.py", "--skip", "h1_btc,h1_sol,capacity,quantization"],
        )

        quarterly_cadence.main()

        out = capsys.readouterr().out
        assert "skipping h1_btc" in out
        assert "running forward_validation" in out
        assert "running venue_funding" in out
        assert "running h1_btc" not in out
