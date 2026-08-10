"""Sandboxed Python execution for the coder agent.

Deliberately subprocess-based rather than Docker-per-exec or `eval()`: each run
gets a scoped workspace directory, the child process is launched with a stripped
environment (so backend secrets like API keys are never inherited), resource
limits cap CPU time / memory / open files, and a wall-clock timeout is the
backstop if rlimits are unsupported on the host platform. This is a
demo-appropriate sandbox, not a multi-tenant-safe one — see README for the
production alternative (gVisor/Firecracker/Docker-per-exec).
"""

from __future__ import annotations

import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from langchain_core.tools import tool

MAX_OUTPUT_CHARS = 8_000


@dataclass
class ExecResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + f"\n... [truncated, {len(text) - MAX_OUTPUT_CHARS} more chars]"


def _make_preexec_fn(memory_limit_mb: int) -> Callable[[], None] | None:
    try:
        import resource
    except ImportError:
        return None  # not available on this platform (e.g. Windows)

    def limit_resources() -> None:
        cpu_seconds = 30
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        try:
            mem_bytes = memory_limit_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except (ValueError, OSError):
            pass  # RLIMIT_AS is unreliable on some platforms (e.g. macOS); timeout is the backstop
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        except (ValueError, OSError):
            pass

    return limit_resources


def run_python_sandboxed(
    code: str,
    workspace_dir: Path,
    timeout_seconds: int = 10,
    memory_limit_mb: int = 256,
) -> ExecResult:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    script_path = workspace_dir / f"_scratch_{uuid.uuid4().hex[:8]}.py"
    script_path.write_text(code)

    restricted_env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "PYTHONDONTWRITEBYTECODE": "1"}

    try:
        proc = subprocess.run(
            [sys.executable, script_path.name],
            cwd=workspace_dir,
            env=restricted_env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            preexec_fn=_make_preexec_fn(memory_limit_mb) if sys.platform != "win32" else None,
        )
        return ExecResult(
            stdout=_truncate(proc.stdout),
            stderr=_truncate(proc.stderr),
            exit_code=proc.returncode,
            timed_out=False,
        )
    except subprocess.TimeoutExpired as exc:
        return ExecResult(
            stdout=_truncate(exc.stdout.decode() if exc.stdout else ""),
            stderr=_truncate((exc.stderr.decode() if exc.stderr else "") + "\n[process killed: timeout exceeded]"),
            exit_code=-1,
            timed_out=True,
        )
    finally:
        script_path.unlink(missing_ok=True)


def make_code_exec_tool(workspace_dir: Path, timeout_seconds: int = 10, memory_limit_mb: int = 256):
    @tool
    def run_python(code: str) -> str:
        """Execute Python `code` in a sandboxed subprocess scoped to the run's workspace and return stdout/stderr."""
        result = run_python_sandboxed(code, workspace_dir, timeout_seconds, memory_limit_mb)
        status = "TIMED OUT" if result.timed_out else f"exit code {result.exit_code}"
        return f"[{status}]\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"

    return run_python
