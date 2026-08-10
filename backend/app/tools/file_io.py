"""Path-jailed file read/write tools scoped to a single run's workspace directory.

Every tool call resolves its target path and rejects anything that would escape
the workspace root (absolute paths, `..` traversal, symlink escapes) — this is
the boundary that keeps the coder agent's writes confined to `workspaces/{run_id}/`
even though the LLM fully controls the path argument it passes in.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool


class WorkspacePathError(ValueError):
    pass


def resolve_in_workspace(workspace_dir: Path, rel_path: str) -> Path:
    if Path(rel_path).is_absolute():
        raise WorkspacePathError(f"absolute paths are not allowed: {rel_path!r}")

    workspace_root = workspace_dir.resolve()
    candidate = (workspace_root / rel_path).resolve()

    if candidate != workspace_root and workspace_root not in candidate.parents:
        raise WorkspacePathError(f"path escapes workspace: {rel_path!r}")

    return candidate


def make_file_tools(workspace_dir: Path) -> list:
    workspace_dir.mkdir(parents=True, exist_ok=True)

    @tool
    def write_file(path: str, content: str) -> str:
        """Write `content` to a file at `path`, relative to the run's sandboxed workspace."""
        target = resolve_in_workspace(workspace_dir, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"wrote {len(content)} bytes to {path}"

    @tool
    def read_file(path: str) -> str:
        """Read and return the contents of a file at `path`, relative to the run's workspace."""
        target = resolve_in_workspace(workspace_dir, path)
        if not target.exists():
            return f"error: {path} does not exist"
        return target.read_text()

    @tool
    def list_files() -> str:
        """List all files currently in the run's workspace."""
        files = sorted(p.relative_to(workspace_dir).as_posix() for p in workspace_dir.rglob("*") if p.is_file())
        return "\n".join(files) if files else "(workspace is empty)"

    return [write_file, read_file, list_files]
