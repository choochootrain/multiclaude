"""Tests for multiclaude new command."""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from multiclaude import cli as multiclaude
from multiclaude.config import load_config
from multiclaude.git_utils import git
from multiclaude.strategies import CloneStrategy


def test_new_creates_task(initialized_repo):
    """Test that new command creates worktree, branch, and updates tasks.json."""
    repo_path = initialized_repo.repo_path

    # Create new task
    args_new = SimpleNamespace(branch_name="test-feature", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)

    # Check environment was created
    expected_environment = initialized_repo.environments_dir / repo_path.name / "mc-test-feature"
    assert expected_environment.exists()
    assert (expected_environment / ".git").exists()
    assert (expected_environment / "README.md").exists()

    # Check that we're on the correct branch in the environment
    code, stdout, stderr = git(
        ["branch", "--show-current"],
        expected_environment,
        check=False,
    )
    assert stdout == "mc-test-feature"

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
    assert task["agent"] == "claude"


def test_new_fails_duplicate_branch(initialized_repo, capsys):
    """Test that new command fails when branch already exists."""

    # Create first task
    args_new = SimpleNamespace(branch_name="feature", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)

    # Try to create same task again
    try:
        multiclaude.cmd_new(args_new)
        assert False, "Should have exited"
    except SystemExit as e:
        assert e.code == 1

    captured = capsys.readouterr()
    assert "already exists" in captured.err


def test_new_no_launch_flag(initialized_repo, capsys):
    """Test that --no-launch flag prevents claude from being launched."""

    # Create task with --no-launch
    args_new = SimpleNamespace(branch_name="test", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)

    # Check output shows it didn't launch
    captured = capsys.readouterr()
    assert "Launching claude" not in captured.out
    # First task should always create new environment
    assert "Created new environment" in captured.out


def test_new_short_n_flag(initialized_repo, capsys):
    """Test that -n short flag works the same as --no-launch."""

    # Create task with -n (simulated as no_launch=True in args)
    args_new = SimpleNamespace(branch_name="test-short", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)

    captured = capsys.readouterr()
    assert "Launching claude" not in captured.out
    # Should create new environment (different branch name from previous test)
    assert "Created new environment" in captured.out


def test_new_would_launch_claude(initialized_repo, capsys):
    """Test that without --no-launch, the agent is launched."""

    # Create task without --no-launch (this will launch claude, but mocked)
    args_new = SimpleNamespace(branch_name="test", no_launch=False, base="main", agent=None)
    multiclaude.cmd_new(args_new)

    # Check output shows it tried to launch
    captured = capsys.readouterr()
    assert "Launching claude" in captured.out
    # Should create new environment
    assert "Created new environment" in captured.out


def test_new_with_custom_agent_flag(initialized_repo, capsys):
    """Test that specifying a custom agent persists and surfaces correctly."""
    repo_path = initialized_repo.repo_path

    args_new = SimpleNamespace(
        branch_name="custom-agent-task",
        no_launch=True,
        base="main",
        agent="custom-agent",
    )
    multiclaude.cmd_new(args_new)

    captured = capsys.readouterr()
    assert "agent: custom-agent" in captured.out

    tasks_file = repo_path / ".multiclaude" / "tasks.json"
    tasks = json.loads(tasks_file.read_text())
    assert tasks[0]["agent"] == "custom-agent"


def test_new_fails_when_agent_missing(initialized_repo, monkeypatch, capsys):
    """Test that new command fails when the requested agent is unavailable."""
    repo_path = initialized_repo.repo_path

    original_which = shutil.which

    def missing_agent(command: str, *args, **kwargs):
        if command == "missing-agent":
            return None
        return original_which(command, *args, **kwargs)

    monkeypatch.setattr("shutil.which", missing_agent)

    args_new = SimpleNamespace(
        branch_name="missing-agent-task",
        no_launch=True,
        base="main",
        agent="missing-agent",
    )

    with pytest.raises(SystemExit) as exc:
        multiclaude.cmd_new(args_new)

    assert exc.value.code == 1  # type: ignore[unresolved-attribute]
    captured = capsys.readouterr()
    assert "Agent 'missing-agent' not found" in captured.err

    tasks_file = repo_path / ".multiclaude" / "tasks.json"
    assert json.loads(tasks_file.read_text()) == []


def test_new_with_custom_base_branch(initialized_repo):
    """Test creating task from a different base branch."""
    repo_path = initialized_repo.repo_path

    # Create a base branch first
    git(["checkout", "-b", "develop"], repo_path, check=True)
    git(["checkout", "main"], repo_path, check=True)

    # Create new task from develop branch
    args_new = SimpleNamespace(
        branch_name="feature-from-develop", no_launch=True, base="develop", agent=None
    )
    multiclaude.cmd_new(args_new)

    # Check environment was created
    environment_dir = initialized_repo.environments_dir
    expected_environment = environment_dir / repo_path.name / "mc-feature-from-develop"
    assert expected_environment.exists()

    # Verify the branch was created from develop by checking git history
    code, stdout, stderr = git(
        ["branch", "--show-current"],
        expected_environment,
        check=False,
    )
    env_branch_result = type("obj", (object,), {"stdout": stdout, "returncode": code})()
    assert env_branch_result.stdout.strip() == "mc-feature-from-develop"

    # Check that the branch was created from develop by verifying the merge-base
    # The merge-base shows the common ancestor commit
    code, stdout, stderr = git(
        ["merge-base", "mc-feature-from-develop", "develop"],
        expected_environment,
        check=False,
    )
    merge_base_commit = stdout

    # Get the commit hash of develop branch
    code, stdout, stderr = git(
        ["rev-parse", "develop"],
        expected_environment,
        check=False,
    )
    develop_commit = stdout

    # Verify they match (merge-base should be develop itself since we branched from it)
    assert merge_base_commit == develop_commit, (
        f"Branch not created from develop. Merge-base: {merge_base_commit}, Develop: {develop_commit}"
    )

    # Check base branch (develop) exists locally
    code, stdout, stderr = git(
        ["branch", "-a"],
        expected_environment,
        check=False,
    )
    assert "develop" in stdout or "remotes/local/develop" in stdout


def test_new_with_invalid_base_ref(initialized_repo, capsys):
    """Test that new command fails when base ref does not exist."""

    # Try to create task from non-existent branch
    args_new = SimpleNamespace(
        branch_name="test", no_launch=True, base="nonexistent-branch", agent=None
    )
    try:
        multiclaude.cmd_new(args_new)
        assert False, "Should have exited"
    except SystemExit as e:
        assert e.code == 1

    captured = capsys.readouterr()
    assert "does not exist" in captured.err


def test_new_with_origin_remote(initialized_repo):
    """Test new command configures remotes correctly when origin exists."""
    repo_path = initialized_repo.repo_path

    # Add a fake GitHub remote to the base repo
    git(
        ["remote", "add", "origin", "git@github.com:user/repo.git"],
        repo_path,
        check=True,
    )

    # Create new task
    args_new = SimpleNamespace(branch_name="test-remotes", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)

    # Check environment was created
    environment_dir = initialized_repo.environments_dir
    expected_environment = environment_dir / repo_path.name / "mc-test-remotes"
    assert expected_environment.exists()

    # Check 'local' remote points to base repo
    code, local_stdout, stderr = git(
        ["remote", "get-url", "local"],
        expected_environment,
        check=False,
    )
    assert code == 0
    assert str(repo_path) in local_stdout.strip()

    # Check 'origin' remote points to GitHub
    code, origin_stdout, stderr = git(
        ["remote", "get-url", "origin"],
        expected_environment,
        check=False,
    )
    assert code == 0
    assert "github.com:user/repo.git" in origin_stdout

    # Check push.autoSetupRemote is configured
    code, config_stdout, stderr = git(
        ["config", "push.autoSetupRemote"],
        expected_environment,
        check=False,
    )
    assert config_stdout == "true"

    # Check base branch (main) exists
    code, branches_stdout, stderr = git(
        ["branch", "-a"],
        expected_environment,
        check=False,
    )
    assert "main" in branches_stdout or "remotes/local/main" in branches_stdout


def test_new_without_origin_remote(initialized_repo):
    """Test new command when base repo has no origin remote."""
    repo_path = initialized_repo.repo_path

    # Create new task
    args_new = SimpleNamespace(
        branch_name="test-no-origin", no_launch=True, base="main", agent=None
    )
    multiclaude.cmd_new(args_new)

    # Check environment was created
    environment_dir = initialized_repo.environments_dir
    expected_environment = environment_dir / repo_path.name / "mc-test-no-origin"
    assert expected_environment.exists()

    # Check 'local' remote exists and points to base repo
    code, local_stdout, stderr = git(
        ["remote", "get-url", "local"],
        expected_environment,
        check=False,
    )
    assert code == 0
    assert str(repo_path) in local_stdout.strip()

    # Check 'origin' remote does NOT exist
    code, _, _ = git(
        ["remote", "get-url", "origin"],
        expected_environment,
        check=False,
    )
    assert code != 0  # Should fail since origin doesn't exist

    # Check push.autoSetupRemote is still configured
    code, config_stdout, stderr = git(
        ["config", "push.autoSetupRemote"],
        expected_environment,
        check=False,
    )
    assert config_stdout == "true"

    # Check base branch (main) exists
    code, branches_stdout, stderr = git(
        ["branch", "-a"],
        expected_environment,
        check=False,
    )
    assert "main" in branches_stdout or "remotes/local/main" in branches_stdout


def test_new_reuses_available_environment(initialized_repo, capsys):
    """Test that new command reuses available environments."""
    repo_path = initialized_repo.repo_path

    # Create first task
    args_new1 = SimpleNamespace(branch_name="task1", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new1)

    captured = capsys.readouterr()
    assert "Created new environment" in captured.out
    assert "Reused existing environment" not in captured.out

    # Get the environment path
    environment_dir = initialized_repo.environments_dir
    task1_path = Path(environment_dir) / repo_path.name / "mc-task1"

    # Manually remove the task to create an available environment
    # (since there's no remove command yet, we use the strategy directly)

    # Load config for the strategy
    config = load_config(repo_path)
    strategy = CloneStrategy(config)
    strategy.remove(task1_path)

    # Verify available environment was created
    repo_dir = Path(environment_dir) / repo_path.name
    available_envs = [p for p in repo_dir.iterdir() if p.is_dir() and p.name.startswith("avail-")]
    assert len(available_envs) == 1

    # Create second task - should reuse the available environment
    args_new2 = SimpleNamespace(branch_name="task2", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new2)

    captured = capsys.readouterr()
    assert "Reused existing environment" in captured.out
    assert "Created new environment" not in captured.out

    # Verify available environment is gone
    available_envs_after = [
        p for p in repo_dir.iterdir() if p.is_dir() and p.name.startswith("avail-")
    ]
    assert len(available_envs_after) == 0

    # Verify new task exists
    task2_path = Path(environment_dir) / repo_path.name / "mc-task2"
    assert task2_path.exists()
