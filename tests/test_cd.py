"""Tests for multiclaude cd command."""

import json
import shutil
from types import SimpleNamespace

import pytest

from multiclaude import cli as multiclaude


def test_cd_success_with_full_name(initialized_repo, monkeypatch, capsys):
    """Test cd command with full branch name."""
    args_new = SimpleNamespace(branch_name="feature", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)

    # Mock os.execvp to prevent actual execution
    exec_called = []

    def mock_execvp(file, args):
        exec_called.append((file, args))

    monkeypatch.setattr("os.execvp", mock_execvp)

    # CD to task directory
    args_cd = SimpleNamespace(task_name="mc-feature")
    multiclaude.cmd_cd(args_cd)

    captured = capsys.readouterr()
    assert "Opening shell in task 'mc-feature'" in captured.out
    assert "Type 'exit' to return" in captured.out

    # Verify execvp was called with shell
    assert len(exec_called) == 1
    file, args = exec_called[0]
    assert args == [file]  # Shell is called with just its name


def test_cd_success_with_partial_name(initialized_repo, monkeypatch, capsys):
    """Test cd command with partial task name."""
    args_new = SimpleNamespace(branch_name="feature-auth", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)

    # Mock os.execvp
    exec_called = []

    def mock_execvp(file, args):
        exec_called.append((file, args))

    monkeypatch.setattr("os.execvp", mock_execvp)

    # CD with partial name
    args_cd = SimpleNamespace(task_name="feature-auth")
    multiclaude.cmd_cd(args_cd)

    captured = capsys.readouterr()
    assert "Opening shell in task 'mc-feature-auth'" in captured.out
    assert len(exec_called) == 1


def test_cd_missing_environment(initialized_repo, capsys):
    """Test cd command with missing environment directory."""
    args_new = SimpleNamespace(branch_name="missing", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)

    # Delete the environment directory
    tasks_file = initialized_repo.repo_path / ".multiclaude" / "tasks.json"
    tasks = json.loads(tasks_file.read_text())
    env_path = tasks[0]["environment_path"]
    shutil.rmtree(env_path)

    # Try to cd (should fail gracefully)
    with pytest.raises(SystemExit):
        args_cd = SimpleNamespace(task_name="missing")
        multiclaude.cmd_cd(args_cd)

    captured = capsys.readouterr()
    assert "Task environment missing" in captured.err
    assert "no longer exists" in captured.err


def test_cd_nonexistent_task(initialized_repo, capsys):
    """Test cd command with non-existent task."""
    args_new = SimpleNamespace(branch_name="feature", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)

    # Try to cd to non-existent task
    with pytest.raises(SystemExit):
        args_cd = SimpleNamespace(task_name="nonexistent")
        multiclaude.cmd_cd(args_cd)

    captured = capsys.readouterr()
    assert "No task found matching 'nonexistent'" in captured.err


def test_cd_uses_user_shell(initialized_repo, monkeypatch, capsys):
    """Test cd command respects SHELL environment variable."""
    args_new = SimpleNamespace(branch_name="feature", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)

    # Mock os.execvp and set custom SHELL
    exec_called = []

    def mock_execvp(file, args):
        exec_called.append((file, args))

    monkeypatch.setattr("os.execvp", mock_execvp)
    monkeypatch.setenv("SHELL", "/usr/bin/zsh")

    # CD to task
    args_cd = SimpleNamespace(task_name="feature")
    multiclaude.cmd_cd(args_cd)

    # Verify correct shell was used
    assert len(exec_called) == 1
    assert exec_called[0] == ("/usr/bin/zsh", ["/usr/bin/zsh"])


def test_cd_defaults_to_bash_if_no_shell_env(initialized_repo, monkeypatch, capsys):
    """Test cd command defaults to bash when SHELL not set."""
    args_new = SimpleNamespace(branch_name="feature", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)

    # Mock os.execvp and unset SHELL
    exec_called = []

    def mock_execvp(file, args):
        exec_called.append((file, args))

    monkeypatch.setattr("os.execvp", mock_execvp)
    monkeypatch.delenv("SHELL", raising=False)

    # CD to task
    args_cd = SimpleNamespace(task_name="feature")
    multiclaude.cmd_cd(args_cd)

    # Verify bash was used as default
    assert len(exec_called) == 1
    assert exec_called[0] == ("/bin/bash", ["/bin/bash"])
