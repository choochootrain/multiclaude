"""Environment creation strategies for multiclaude."""

import abc
import random
import shutil
import string
import subprocess
from pathlib import Path
from typing import Protocol

from .errors import MultiClaudeError
from .git_utils import configure_clone_remotes, get_environment_base_dir, get_repo_name, ref_exists


class EnvironmentStrategy(Protocol):
    """Interface for environment creation strategies."""

    @abc.abstractmethod
    def create(
        self, repo_root: Path, branch_name: str, base_ref: str = "main"
    ) -> tuple[Path, bool]:
        """Create a new environment.

        Returns:
            Tuple of (environment_path, was_reused)
        """
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

    def __init__(self, base_dir: Path):
        """Initialize the worktree strategy."""
        self.base_dir = base_dir

    @property
    def name(self) -> str:
        """Get the name of the strategy."""
        return "worktree"

    def create(
        self, repo_root: Path, branch_name: str, base_ref: str = "main"
    ) -> tuple[Path, bool]:
        """Create a new worktree with a new branch.

        Returns:
            Tuple of (worktree_path, was_reused) - always False for worktrees
        """
        repo_name = get_repo_name(repo_root)
        worktree_path = self.base_dir / repo_name / branch_name

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

        return worktree_path, False

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


def generate_hash(length: int = 7) -> str:
    """Generate a short alphanumeric hash for available environment names."""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=length))


class CloneStrategy(EnvironmentStrategy):
    """Strategy for creating environments by cloning the repository."""

    def __init__(self, base_dir: Path):
        """Initialize the clone strategy."""
        self.base_dir = base_dir

    @property
    def name(self) -> str:
        """Get the name of the strategy."""
        return "clone"

    def find_available_environment(self, repo_name: str) -> Path | None:
        """Find an available environment (named avail-{hash}) for the given repo."""
        repo_dir = self.base_dir / repo_name

        if not repo_dir.exists():
            return None

        # Look for directories matching avail-{hash} pattern
        for path in repo_dir.iterdir():
            if path.is_dir() and path.name.startswith("avail-"):
                # Basic validation that it looks like our hash pattern
                hash_part = path.name[6:]  # Remove "avail-" prefix
                if len(hash_part) >= 6 and all(
                    c in string.ascii_lowercase + string.digits for c in hash_part
                ):
                    return path

        return None

    def create(
        self, repo_root: Path, branch_name: str, base_ref: str = "main"
    ) -> tuple[Path, bool]:
        """Create a new environment by cloning the repository or reusing an available one.

        Returns:
            Tuple of (clone_path, was_reused)
        """
        repo_name = get_repo_name(repo_root)
        clone_path = self.base_dir / repo_name / branch_name

        clone_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if base_ref exists
        if not ref_exists(repo_root, base_ref):
            raise MultiClaudeError(f"Base ref '{base_ref}' does not exist")

        # Check for available environment to reuse
        available_env = self.find_available_environment(repo_name)

        if available_env:
            print(f"Reusing available environment: {available_env.name}")

            # Rename the available environment to the new task name
            available_env.rename(clone_path)

            # Clean up any uncommitted changes
            subprocess.run(
                ["git", "reset", "--hard"],
                capture_output=True,
                check=False,
                cwd=clone_path,
            )
            subprocess.run(
                ["git", "clean", "-fd"],
                capture_output=True,
                check=False,
                cwd=clone_path,
            )

            # Fetch latest from remotes
            subprocess.run(
                ["git", "fetch", "--all"],
                capture_output=True,
                check=False,
                cwd=clone_path,
            )

            # Checkout the base ref
            result = subprocess.run(
                ["git", "checkout", base_ref],
                capture_output=True,
                text=True,
                check=False,
                cwd=clone_path,
            )
            if result.returncode != 0:
                raise MultiClaudeError(f"Failed to checkout base ref '{base_ref}': {result.stderr}")

            # Create and checkout the new branch
            result = subprocess.run(
                ["git", "checkout", "-b", branch_name],
                capture_output=True,
                text=True,
                check=False,
                cwd=clone_path,
            )
            if result.returncode != 0:
                raise MultiClaudeError(
                    f"Failed to create branch in reused environment: {result.stderr}"
                )

        else:
            # No available environment, clone as usual
            print(f"Creating new clone for '{branch_name}' from '{base_ref}'")

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

        # Handle submodules (for both new and reused environments)
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

        return clone_path, bool(available_env)

    def remove(self, worktree_path: Path) -> None:
        """Remove a cloned environment by renaming it for reuse."""
        expanded_path = worktree_path.expanduser()
        if not expanded_path.exists():
            return

        # Generate a unique hash for the available environment name
        hash_suffix = generate_hash()
        available_name = f"avail-{hash_suffix}"
        available_path = expanded_path.parent / available_name

        # Make sure we don't collide with existing names
        while available_path.exists():
            hash_suffix = generate_hash()
            available_name = f"avail-{hash_suffix}"
            available_path = expanded_path.parent / available_name

        # Clean up the git state before making it available
        try:
            # Reset any uncommitted changes
            subprocess.run(
                ["git", "reset", "--hard"],
                capture_output=True,
                check=False,
                cwd=expanded_path,
            )
            subprocess.run(
                ["git", "clean", "-fd"],
                capture_output=True,
                check=False,
                cwd=expanded_path,
            )

            # Get the default branch
            result = subprocess.run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                capture_output=True,
                text=True,
                check=False,
                cwd=expanded_path,
            )
            default_branch = "main"
            if result.returncode == 0:
                # refs/remotes/origin/main -> main
                default_branch = result.stdout.strip().split("/")[-1]

            # Checkout default branch
            subprocess.run(
                ["git", "checkout", default_branch],
                capture_output=True,
                check=False,
                cwd=expanded_path,
            )
        except Exception as e:
            # If cleanup fails, just delete the directory
            print(f"Warning: Failed to clean environment before reuse, removing: {e}")
            shutil.rmtree(expanded_path)
            return

        # Rename to make it available for reuse
        expanded_path.rename(available_path)
        print(f"Environment renamed to {available_name} for reuse")


def get_strategy(strategy_name: str | None) -> EnvironmentStrategy:
    """Get an instance of the specified strategy."""
    base_dir = get_environment_base_dir()
    if strategy_name == "worktree":
        return WorktreeStrategy(base_dir)
    if strategy_name == "clone":
        return CloneStrategy(base_dir)
    return CloneStrategy(base_dir)
