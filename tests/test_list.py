"""Tests for multiclaude list command."""

import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

from multiclaude import cli as multiclaude


def test_list_empty(isolated_repo, capsys):
    """Test list command when no tasks exist."""
    # Initialize first
    args_init = SimpleNamespace()
    multiclaude.cmd_init(args_init)

    # List tasks (should be empty)
    args_list = SimpleNamespace(show_pruned=False)
    multiclaude.cmd_list(args_list)

    captured = capsys.readouterr()
    assert "No multiclaude tasks found" in captured.out


def test_list_single_task(isolated_repo, capsys):
    """Test list command with one task."""
    # Initialize and create one task
    args_init = SimpleNamespace()
    multiclaude.cmd_init(args_init)

    args_new = SimpleNamespace(branch_name="feature-one", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)

    # List tasks
    args_list = SimpleNamespace(show_pruned=False)
    multiclaude.cmd_list(args_list)

    captured = capsys.readouterr()
    assert "Active multiclaude tasks:" in captured.out
    assert "mc-feature-one" in captured.out
    assert "branch mc-feature-one" in captured.out
    assert "agent=claude" in captured.out


def test_list_multiple_tasks(isolated_repo, capsys):
    """Test list command with multiple tasks."""
    # Initialize and create multiple tasks
    args_init = SimpleNamespace()
    multiclaude.cmd_init(args_init)

    for name in ["feature-one", "feature-two", "bugfix"]:
        args_new = SimpleNamespace(branch_name=name, no_launch=True, base="main", agent=None)
        multiclaude.cmd_new(args_new)

    # List tasks
    args_list = SimpleNamespace(show_pruned=False)
    multiclaude.cmd_list(args_list)

    captured = capsys.readouterr()
    assert "Active multiclaude tasks:" in captured.out
    assert "mc-feature-one" in captured.out
    assert "mc-feature-two" in captured.out
    assert "mc-bugfix" in captured.out

    # Check all have branch info
    assert captured.out.count("branch mc-") == 3
    assert captured.out.count("agent=claude") == 3


def test_list_detects_missing_worktree(isolated_repo, capsys):
    """Test that list handles deleted worktrees gracefully."""
    repo_path = isolated_repo

    # Initialize and create a task
    args_init = SimpleNamespace()
    multiclaude.cmd_init(args_init)

    args_new = SimpleNamespace(branch_name="feature", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)

    # Manually delete the environment directory (simulate external deletion)
    environment_dir = os.environ.get("MULTICLAUDE_ENVIRONMENT_DIR")
    environment_path = Path(environment_dir) / repo_path.name / "mc-feature"
    if environment_path.exists():
        shutil.rmtree(environment_path)

    # Also remove from git worktrees
    subprocess.run(
        ["git", "worktree", "prune"],
        cwd=repo_path,
        capture_output=True,
    )

    # List should still work but show task as missing
    args_list = SimpleNamespace(show_pruned=False)
    multiclaude.cmd_list(args_list)

    captured = capsys.readouterr()
    # Task should still be listed (it's in tasks.json)
    assert "mc-feature" in captured.out
    # Should indicate missing status
    assert "[missing]" in captured.out or "missing" in captured.out.lower()
