import pytest

from app.tools.code_exec import run_python_sandboxed
from app.tools.file_io import WorkspacePathError, resolve_in_workspace


def test_sandbox_runs_simple_code_and_captures_stdout(tmp_path):
    result = run_python_sandboxed("print('hello from sandbox')", tmp_path)

    assert result.exit_code == 0
    assert not result.timed_out
    assert "hello from sandbox" in result.stdout


def test_sandbox_captures_nonzero_exit_and_stderr(tmp_path):
    result = run_python_sandboxed("import sys; sys.exit(3)", tmp_path)

    assert result.exit_code == 3
    assert not result.timed_out


def test_sandbox_enforces_wall_clock_timeout(tmp_path):
    result = run_python_sandboxed("import time; time.sleep(5)", tmp_path, timeout_seconds=1)

    assert result.timed_out is True
    assert result.exit_code == -1


def test_sandbox_does_not_inherit_parent_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPER_SECRET_API_KEY", "sk-should-not-leak")

    result = run_python_sandboxed("import os; print(os.environ.get('SUPER_SECRET_API_KEY', 'NOT_SET'))", tmp_path)

    assert "NOT_SET" in result.stdout
    assert "sk-should-not-leak" not in result.stdout


def test_sandbox_scratch_script_is_cleaned_up(tmp_path):
    run_python_sandboxed("print(1)", tmp_path)

    leftover_scripts = list(tmp_path.glob("_scratch_*.py"))
    assert leftover_scripts == []


def test_path_jail_rejects_parent_traversal(tmp_path):
    with pytest.raises(WorkspacePathError):
        resolve_in_workspace(tmp_path, "../outside.py")


def test_path_jail_rejects_absolute_paths(tmp_path):
    with pytest.raises(WorkspacePathError):
        resolve_in_workspace(tmp_path, "/etc/passwd")


def test_path_jail_allows_nested_relative_paths(tmp_path):
    resolved = resolve_in_workspace(tmp_path, "subdir/file.py")
    assert resolved == (tmp_path / "subdir" / "file.py").resolve()
