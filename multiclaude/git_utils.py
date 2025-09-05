"""Git utility functions for multiclaude."""

import os
import subprocess
from pathlib import Path


def get_repo_name(repo_root: Path) -> str:
    """Get repository name from path."""
    return repo_root.name


def get_environment_base_dir() -> Path:
    """Get base directory for environments (worktrees or clones)."""
    if env_dir := os.environ.get("MULTICLAUDE_ENVIRONMENT_DIR"):
        return Path(env_dir)
    return Path.home() / "multiclaude-environments"


def is_git_repo(repo_root: Path) -> bool:
    """Check if directory is a git repository."""
    return (repo_root / ".git").exists()


def branch_exists(repo_root: Path, branch_name: str) -> bool:
    """Check if branch already exists."""
    result = subprocess.run(
        ["git", "branch", "--list", branch_name],
        capture_output=True,
        text=True,
        check=False,
        cwd=repo_root,
    )
    return bool(result.stdout.strip())


def ref_exists(repo_root: Path, ref: str) -> bool:
    """Check if a git ref (branch/tag/commit) exists."""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        capture_output=True,
        text=True,
        check=False,
        cwd=repo_root,
    )
    return result.returncode == 0
