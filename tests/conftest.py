"""Pytest fixtures for multiclaude tests."""

import os
import shutil
import subprocess
import time
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def configure_git_repo(path: Path) -> None:
    """Configure git user info and disable GPG signing for test repos."""
    settings = [
        ("user.name", "Test User"),
        ("user.email", "test@example.com"),
        ("commit.gpgsign", "false"),
    ]
    for key, value in settings:
        subprocess.run(
            ["git", "config", key, value],
            cwd=path,
            capture_output=True,
            check=True,
        )


@pytest.fixture
def isolated_git_repo(tmp_path: Path, monkeypatch) -> Generator[Path, None, None]:
    """Create an isolated git repository for testing.

    Yields:
        Path to the test repository
    """
    # Create unique test name with timestamp
    test_name = f"test-{int(time.time() * 1000)}"

    # Create test repo
    repo_path = tmp_path / test_name
    repo_path.mkdir(parents=True)

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
    configure_git_repo(repo_path)

    # Create initial commit
    readme = repo_path / "README.md"
    readme.write_text("# Test Repository\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True, check=True
    )

    # Change to repo directory
    monkeypatch.chdir(repo_path)

    yield repo_path


@dataclass
class MCTestRepo:
    """Test repository with multiclaude-specific setup."""

    repo_path: Path
    environments_dir: Path


@pytest.fixture
def isolated_repo(isolated_git_repo: Path, tmp_path: Path, monkeypatch) -> MCTestRepo:
    """Create an isolated repository with multiclaude test setup.

    Returns:
        MCTestRepo with repo_path and environments_dir
    """
    # Create environments directory for tests
    environments_dir = tmp_path / "environments"
    environments_dir.mkdir(exist_ok=True)

    # Mock subprocess.run to handle "which claude" and actual claude launches
    agent_commands: set[str] = set()

    original_which = shutil.which

    def mock_which(command, *args, **kwargs):
        if isinstance(command, str) and command.strip():
            normalized = command.strip()
            agent_commands.add(normalized)
            return str(Path("/usr/local/bin") / normalized)
        return original_which(command, *args, **kwargs)

    monkeypatch.setattr(shutil, "which", mock_which)

    original_run = subprocess.run

    def mock_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and cmd and cmd[0] in agent_commands:
            result = MagicMock()
            result.returncode = 0
            result.stdout = f"{cmd[0]} launched (mocked)"
            result.stderr = ""
            return result
        # Let other commands through
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr("subprocess.run", mock_run)

    # Mock os.chdir to prevent trying to change to non-existent directories
    original_chdir = os.chdir

    def mock_chdir(path):
        # Only change to paths that exist
        if Path(path).exists():
            original_chdir(path)
        # Otherwise just ignore (for claude launch in worktree)

    monkeypatch.setattr("os.chdir", mock_chdir)

    return MCTestRepo(repo_path=isolated_git_repo, environments_dir=environments_dir)


@pytest.fixture
def initialized_repo(isolated_repo: MCTestRepo) -> MCTestRepo:
    """Create an isolated repository with multiclaude already initialized.

    This reduces duplication across test files by providing a pre-initialized
    multiclaude repository with standard configuration.

    Returns:
        MCTestRepo with multiclaude already initialized
    """
    from types import SimpleNamespace
    from multiclaude import cli as multiclaude

    # Initialize multiclaude with the test environments directory
    args_init = SimpleNamespace()
    args_init.environments_dir = isolated_repo.environments_dir
    multiclaude.cmd_init(args_init)

    return isolated_repo


@pytest.fixture
def mock_claude(monkeypatch) -> MagicMock:
    """Mock for tracking claude launches.

    Returns:
        MagicMock that can be used to assert claude was called
    """
    mock = MagicMock()

    import subprocess

    original_run = subprocess.run

    def track_claude_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and "claude" in str(cmd):
            # Track claude launches
            mock(cmd, *args, **kwargs)
            result = MagicMock()
            result.returncode = 0
            return result
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr("subprocess.run", track_claude_run)

    return mock
