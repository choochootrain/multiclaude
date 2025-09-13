"""Pytest fixtures for multiclaude tests."""

import os
import time
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def isolated_repo(tmp_path: Path, monkeypatch) -> Generator[Path, None, None]:
    """Create an isolated test repository.

    Yields:
        Path to the test repository
    """
    # Create unique test name with timestamp
    test_name = f"test-{int(time.time() * 1000)}"

    # Create test repo
    repo_path = tmp_path / test_name
    repo_path.mkdir(parents=True)

    # Initialize git repo
    import subprocess

    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)

    # Create initial commit
    readme = repo_path / "README.md"
    readme.write_text("# Test Repository\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True, check=True
    )

    # Set environment directory for tests
    environment_dir = tmp_path / "environments"
    environment_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("MULTICLAUDE_ENVIRONMENT_DIR", str(environment_dir))

    # Change to repo directory
    monkeypatch.chdir(repo_path)

    # Mock subprocess.run to handle "which claude" and actual claude launches
    original_run = subprocess.run

    def mock_run(cmd, *args, **kwargs):
        if isinstance(cmd, list):
            # Mock "which claude" to succeed
            if cmd == ["which", "claude"]:
                result = MagicMock()
                result.returncode = 0
                result.stdout = "/usr/local/bin/claude"
                result.stderr = ""
                return result
            # Mock actual claude launch
            elif len(cmd) > 0 and cmd[0] == "claude":
                result = MagicMock()
                result.returncode = 0
                result.stdout = "Claude launched (mocked)"
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

    yield repo_path


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
        if isinstance(cmd, list):
            # Track claude launches
            if "claude" in str(cmd):
                mock(cmd, *args, **kwargs)
                result = MagicMock()
                result.returncode = 0
                return result
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr("subprocess.run", track_claude_run)

    return mock
