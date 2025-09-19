"""Environment creation strategies for multiclaude."""

import abc
import random
import shutil
import string
from pathlib import Path
from typing import Protocol

from .config import Config
from .errors import MultiClaudeError
from .git_utils import (
    checkout_branch,
    clean_working_tree,
    configure_clone_remotes,
    get_default_branch,
    get_repo_name,
    git,
    ref_exists,
    setup_branch_from_ref,
)


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


def generate_hash(length: int = 7) -> str:
    """Generate a short alphanumeric hash for available environment names."""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=length))


def find_available_environment(base_dir: Path, repo_name: str) -> Path | None:
    """Find an available environment (named avail-{hash}) for the given repo."""
    repo_dir = base_dir / repo_name
    if not repo_dir.exists():
        return None

    # Look for directories starting with "avail-"
    for path in repo_dir.iterdir():
        if path.is_dir() and path.name.startswith("avail-"):
            return path

    return None


def prepare_reused_environment(env_path: Path, base_ref: str, branch_name: str) -> None:
    """Prepare a reused environment by cleaning and creating new branch."""
    success, error = setup_branch_from_ref(env_path, branch_name, base_ref)
    if not success:
        raise MultiClaudeError(error)


def make_environment_available(env_path: Path) -> None:
    """Make an environment available for reuse by renaming to avail-*."""
    # Generate unique available name
    hash_suffix = generate_hash()
    available_name = f"avail-{hash_suffix}"
    available_path = env_path.parent / available_name

    # Make sure we don't collide with existing names
    while available_path.exists():
        hash_suffix = generate_hash()
        available_name = f"avail-{hash_suffix}"
        available_path = env_path.parent / available_name

    # Clean up the git state before making it available
    try:
        success, error = clean_working_tree(env_path)
        if not success:
            raise Exception(f"Failed to clean: {error}")

        default_branch = get_default_branch(env_path)
        success, error = checkout_branch(env_path, default_branch)
        if not success:
            raise Exception(f"Failed to checkout default branch: {error}")

    except Exception as e:
        # If cleanup fails, just delete the directory
        print(f"Warning: Failed to clean environment before reuse, removing: {e}")
        shutil.rmtree(env_path)
        return

    # Rename to make available
    env_path.rename(available_path)
    print(f"Environment renamed to {available_name} for reuse")


class WorktreeStrategy(EnvironmentStrategy):
    """Strategy for creating environments using git worktrees."""

    def __init__(self, config: Config):
        """Initialize the worktree strategy."""
        self.config = config
        self.base_dir = config.environments_dir

    @property
    def name(self) -> str:
        """Get the name of the strategy."""
        return "worktree"

    def create(
        self, repo_root: Path, branch_name: str, base_ref: str = "main"
    ) -> tuple[Path, bool]:
        """Create a new environment using git worktree.

        Returns:
            Tuple of (worktree_path, was_reused=False)
        """
        repo_name = get_repo_name(repo_root)
        worktree_path = self.base_dir / repo_name / branch_name

        # Ensure the parent directory exists
        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if base_ref exists
        if not ref_exists(repo_root, base_ref):
            raise MultiClaudeError(f"Base ref '{base_ref}' does not exist")

        # Create the worktree with the new branch from base_ref
        code, _, stderr = git(
            ["worktree", "add", str(worktree_path), "-b", branch_name, base_ref], repo_root
        )
        if code != 0:
            raise MultiClaudeError(f"Failed to create worktree: {stderr}")

        return worktree_path, False

    def remove(self, worktree_path: Path) -> None:
        """Remove an existing worktree."""
        # Handle ~ in paths
        expanded_path = worktree_path.expanduser()

        code, _, stderr = git(["worktree", "remove", str(expanded_path)], Path.cwd())
        if code != 0:
            raise MultiClaudeError(f"Failed to remove worktree: {stderr}")


class CloneStrategy(EnvironmentStrategy):
    """Strategy for creating environments by cloning the repository."""

    def __init__(self, config: Config):
        """Initialize the clone strategy."""
        self.config = config
        self.base_dir = config.environments_dir

    @property
    def name(self) -> str:
        """Get the name of the strategy."""
        return "clone"

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
        available_env = find_available_environment(self.base_dir, repo_name)

        if available_env:
            print(f"Reusing available environment: {available_env.name}")

            # Rename the available environment to the new task name
            available_env.rename(clone_path)

            # Prepare the reused environment
            prepare_reused_environment(clone_path, base_ref, branch_name)

        else:
            # No available environment, clone as usual
            print(f"Creating new clone for '{branch_name}' from '{base_ref}'")

            # Clone the repository with renamed remote
            code, _, stderr = git(
                ["clone", "-o", "local", str(repo_root), str(clone_path), "--no-checkout"],
                Path.cwd(),
            )
            if code != 0:
                raise MultiClaudeError(f"Failed to clone repository: {stderr}")

            # Checkout the base ref in the clone (safe, doesn't touch base repo)
            success, error = checkout_branch(clone_path, base_ref)
            if not success:
                # Clean up the failed clone
                shutil.rmtree(clone_path)
                raise MultiClaudeError(f"Failed to checkout base ref '{base_ref}': {error}")

            # Configure remotes (adds origin from base repo)
            success, error = configure_clone_remotes(clone_path, repo_root)
            if not success:
                raise MultiClaudeError(f"Failed to configure remotes: {error}")

            # Create and checkout the new branch from the base ref
            success, error = checkout_branch(clone_path, branch_name, create=True)
            if not success:
                raise MultiClaudeError(f"Failed to create branch: {error}")

        # Handle submodules (for both new and reused environments)
        code, stdout, _ = git(["submodule", "update", "--init", "--recursive"], clone_path)
        if code == 0 and stdout:
            print("Initialized submodules")

        return clone_path, bool(available_env)

    def remove(self, clone_path: Path) -> None:
        """Remove an existing clone by renaming it to avail-{hash}."""
        # Handle ~ in paths
        expanded_path = clone_path.expanduser()

        if not expanded_path.exists():
            raise MultiClaudeError(f"Clone path does not exist: {clone_path}")

        # Instead of deleting, rename to make available for reuse
        make_environment_available(expanded_path)


def get_strategy(config: Config) -> EnvironmentStrategy:
    """Get the appropriate strategy based on configuration."""
    strategy_name = config.environment_strategy

    if strategy_name == "worktree":
        return WorktreeStrategy(config)
    elif strategy_name == "clone":
        return CloneStrategy(config)
    else:
        raise MultiClaudeError(f"Unknown environment strategy: {strategy_name}")
