"""Environment creation strategies for multiclaude."""

import abc
import shutil
import subprocess
from pathlib import Path
from typing import Protocol

from .errors import MultiClaudeError
from .git_utils import configure_clone_remotes, get_environment_base_dir, get_repo_name, ref_exists


class EnvironmentStrategy(Protocol):
    """Interface for environment creation strategies."""

    @abc.abstractmethod
    def create(self, repo_root: Path, branch_name: str, base_ref: str = "main") -> Path:
        """Create a new environment."""
        ...

    @abc.abstractmethod
    def remove(self, worktree_path: Path) -> None:
        """Remove an existing environment."""
        ...

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Get the name of the strategy."""
        ...


class WorktreeStrategy(EnvironmentStrategy):
    """Strategy for creating environments using git worktrees."""

    @property
    def name(self) -> str:
        """Get the name of the strategy."""
        return "worktree"

    def create(self, repo_root: Path, branch_name: str, base_ref: str = "main") -> Path:
        """Create a new worktree with a new branch."""
        repo_name = get_repo_name(repo_root)
        worktree_base = get_environment_base_dir()
        worktree_path = worktree_base / repo_name / branch_name

        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if base_ref exists
        if not ref_exists(repo_root, base_ref):
            raise MultiClaudeError(f"Base ref '{base_ref}' does not exist")

        result = subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", branch_name, base_ref],
            capture_output=True,
            text=True,
            check=False,
            cwd=repo_root,
        )

        if result.returncode != 0:
            raise MultiClaudeError(f"Failed to create worktree: {result.stderr}")

        return worktree_path

    def remove(self, worktree_path: Path) -> None:
        """Remove a git worktree."""
        # The path in the task might be relative from the home dir, expand it
        expanded_path = worktree_path.expanduser()

        result = subprocess.run(
            ["git", "worktree", "remove", str(expanded_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 and "No such worktree" not in result.stderr:
            raise MultiClaudeError(f"Failed to remove worktree: {result.stderr}")


class CloneStrategy(EnvironmentStrategy):
    """Strategy for creating environments by cloning the repository."""

    @property
    def name(self) -> str:
        """Get the name of the strategy."""
        return "clone"

    def create(self, repo_root: Path, branch_name: str, base_ref: str = "main") -> Path:
        """Create a new environment by cloning the repository."""
        repo_name = get_repo_name(repo_root)
        clone_base = get_environment_base_dir()
        clone_path = clone_base / repo_name / branch_name

        clone_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if base_ref exists
        if not ref_exists(repo_root, base_ref):
            raise MultiClaudeError(f"Base ref '{base_ref}' does not exist")

        # Clone the repository with renamed remote
        result = subprocess.run(
            ["git", "clone", "-o", "local", str(repo_root), str(clone_path), "--no-checkout"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise MultiClaudeError(f"Failed to clone repository: {result.stderr}")

        # Checkout the base ref in the clone (safe, doesn't touch base repo)
        result = subprocess.run(
            ["git", "checkout", base_ref],
            capture_output=True,
            text=True,
            check=False,
            cwd=clone_path,
        )
        if result.returncode != 0:
            raise MultiClaudeError(f"Failed to checkout base ref '{base_ref}': {result.stderr}")

        # Configure remotes (add origin from base repo, set push.autoSetupRemote)
        configure_clone_remotes(clone_path, repo_root)

        # Create and checkout the new branch from the base ref
        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            capture_output=True,
            text=True,
            check=False,
            cwd=clone_path,
        )
        if result.returncode != 0:
            raise MultiClaudeError(f"Failed to create branch in clone: {result.stderr}")

        # Handle submodules
        result = subprocess.run(
            ["git", "submodule", "update", "--init", "--recursive"],
            capture_output=True,
            text=True,
            check=False,
            cwd=clone_path,
        )
        if result.returncode != 0:
            # This is not always a fatal error, so maybe just warn
            print(f"Warning: 'git submodule update' failed: {result.stderr}")

        return clone_path

    def remove(self, worktree_path: Path) -> None:
        """Remove a cloned environment by deleting its directory."""
        expanded_path = worktree_path.expanduser()
        if expanded_path.exists():
            shutil.rmtree(expanded_path)


def get_strategy(strategy_name: str | None) -> EnvironmentStrategy:
    """Get an instance of the specified strategy."""
    if strategy_name == "worktree":
        return WorktreeStrategy()
    if strategy_name == "clone":
        return CloneStrategy()
    return CloneStrategy()
