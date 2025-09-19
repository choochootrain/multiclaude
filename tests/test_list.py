"""Tests for multiclaude list command."""

import json
import shutil
import subprocess
from datetime import datetime
from types import SimpleNamespace

from multiclaude import cli as multiclaude


def test_list_empty(initialized_repo, capsys):
    """Test list command when no tasks exist."""

    # List tasks (should be empty)
    args_list = SimpleNamespace(show_pruned=False)
    multiclaude.cmd_list(args_list)

    captured = capsys.readouterr()
    assert "No multiclaude tasks found" in captured.out


def test_list_single_task(initialized_repo, capsys):
    """Test list command with one task."""

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


def test_list_multiple_tasks(initialized_repo, capsys):
    """Test list command with multiple tasks."""

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


def test_list_detects_missing_worktree(initialized_repo, capsys):
    """Test that list handles deleted worktrees gracefully."""
    repo_path = initialized_repo.repo_path

    args_new = SimpleNamespace(branch_name="feature", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)

    # Manually delete the environment directory (simulate external deletion)
    environment_path = initialized_repo.environments_dir / repo_path.name / "mc-feature"
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


def test_list_hides_pruned_tasks_by_default(initialized_repo, capsys):
    """Pruned tasks should only show when --show-pruned is used."""
    repo_path = initialized_repo.repo_path

    # Create two tasks
    for name in ["old-task", "active-task"]:
        args_new = SimpleNamespace(branch_name=name, no_launch=True, base="main", agent=None)
        multiclaude.cmd_new(args_new)

    tasks_file = repo_path / ".multiclaude" / "tasks.json"
    tasks = json.loads(tasks_file.read_text())

    # Mark the first task as pruned
    tasks[0]["status"] = "pruned"
    tasks[0]["pruned_at"] = datetime.now().isoformat()
    tasks_file.write_text(json.dumps(tasks, indent=2))

    capsys.readouterr()

    # Without --show-pruned we should only see the active task
    args_list = SimpleNamespace(show_pruned=False)
    multiclaude.cmd_list(args_list)
    captured = capsys.readouterr()
    assert "mc-active-task" in captured.out
    assert "mc-old-task" not in captured.out

    # With --show-pruned the pruned task should appear in the pruned section
    capsys.readouterr()
    args_list_pruned = SimpleNamespace(show_pruned=True)
    multiclaude.cmd_list(args_list_pruned)
    captured = capsys.readouterr()
    assert "Pruned tasks" in captured.out
    assert "mc-old-task" in captured.out
    assert "mc-active-task" in captured.out
