"""Tests for multiclaude new command."""

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

from multiclaude import cli as multiclaude


def test_new_creates_task(isolated_repo):
    """Test that new command creates worktree, branch, and updates tasks.json."""
    repo_path = isolated_repo

    # Initialize first
    args_init = SimpleNamespace()
    multiclaude.cmd_init(args_init)

    # Create new task
    args_new = SimpleNamespace(branch_name="test-feature", no_launch=True)
    multiclaude.cmd_new(args_new)

    # Check environment was created
    environment_dir = os.environ.get("MULTICLAUDE_ENVIRONMENT_DIR")
    expected_environment = Path(environment_dir) / repo_path.name / "mc-test-feature"
    assert expected_environment.exists()
    assert (expected_environment / ".git").exists()
    assert (expected_environment / "README.md").exists()
    
    # Check that we're on the correct branch in the environment
    env_branch_result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=expected_environment,
        capture_output=True,
        text=True,
    )
    assert env_branch_result.stdout.strip() == "mc-test-feature"

    # Check tasks.json was updated
    tasks_file = repo_path / ".multiclaude" / "tasks.json"
    tasks = json.loads(tasks_file.read_text())
    assert len(tasks) == 1
    task = tasks[0]
    assert task["id"] == "mc-test-feature"
    assert task["branch"] == "mc-test-feature"
    assert task["status"] == "active"
    assert task["environment_path"] == str(expected_environment)
    assert "created_at" in task


def test_new_fails_duplicate_branch(isolated_repo, capsys):
    """Test that new command fails when branch already exists."""
    repo_path = isolated_repo

    # Initialize first
    args_init = SimpleNamespace()
    multiclaude.cmd_init(args_init)

    # Create first task
    args_new = SimpleNamespace(branch_name="feature", no_launch=True)
    multiclaude.cmd_new(args_new)

    # Try to create same task again
    try:
        multiclaude.cmd_new(args_new)
        assert False, "Should have exited"
    except SystemExit as e:
        assert e.code == 1

    captured = capsys.readouterr()
    assert "already exists" in captured.err


def test_new_no_launch_flag(isolated_repo, capsys):
    """Test that --no-launch flag prevents claude from being launched."""
    repo_path = isolated_repo

    # Initialize first
    args_init = SimpleNamespace()
    multiclaude.cmd_init(args_init)

    # Create task with --no-launch
    args_new = SimpleNamespace(branch_name="test", no_launch=True)
    multiclaude.cmd_new(args_new)

    # Check output shows it didn't launch
    captured = capsys.readouterr()
    assert "Launching Claude Code" not in captured.out
    assert "Created isolated environment" in captured.out


def test_new_would_launch_claude(isolated_repo, capsys):
    """Test that without --no-launch, claude would be launched."""
    repo_path = isolated_repo

    # Initialize first
    args_init = SimpleNamespace()
    multiclaude.cmd_init(args_init)

    # Create task without --no-launch (this will launch claude, but mocked)
    args_new = SimpleNamespace(branch_name="test", no_launch=False)
    multiclaude.cmd_new(args_new)

    # Check output shows it tried to launch
    captured = capsys.readouterr()
    assert "Launching Claude Code" in captured.out
    assert "Created isolated environment" in captured.out
