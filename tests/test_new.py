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
    args_new = SimpleNamespace(branch_name="test-feature", no_launch=True, base="main")
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
    args_new = SimpleNamespace(branch_name="feature", no_launch=True, base="main")
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
    args_new = SimpleNamespace(branch_name="test", no_launch=True, base="main")
    multiclaude.cmd_new(args_new)

    # Check output shows it didn't launch
    captured = capsys.readouterr()
    assert "Launching Claude Code" not in captured.out
    # First task should always create new environment
    assert "Created new environment" in captured.out


def test_new_short_n_flag(isolated_repo, capsys):
    """Test that -n short flag works the same as --no-launch."""
    repo_path = isolated_repo

    # Initialize multiclaude
    args_init = SimpleNamespace()
    multiclaude.cmd_init(args_init)

    # Create task with -n (simulated as no_launch=True in args)
    args_new = SimpleNamespace(branch_name="test-short", no_launch=True, base="main")
    multiclaude.cmd_new(args_new)

    captured = capsys.readouterr()
    assert "Launching Claude Code" not in captured.out
    # Should create new environment (different branch name from previous test)
    assert "Created new environment" in captured.out


def test_new_would_launch_claude(isolated_repo, capsys):
    """Test that without --no-launch, claude would be launched."""
    repo_path = isolated_repo

    # Initialize first
    args_init = SimpleNamespace()
    multiclaude.cmd_init(args_init)

    # Create task without --no-launch (this will launch claude, but mocked)
    args_new = SimpleNamespace(branch_name="test", no_launch=False, base="main")
    multiclaude.cmd_new(args_new)

    # Check output shows it tried to launch
    captured = capsys.readouterr()
    assert "Launching Claude Code" in captured.out
    # Should create new environment
    assert "Created new environment" in captured.out


def test_new_with_custom_base_branch(isolated_repo):
    """Test creating task from a different base branch."""
    repo_path = isolated_repo

    # Initialize first
    args_init = SimpleNamespace()
    multiclaude.cmd_init(args_init)

    # Create a base branch first
    subprocess.run(["git", "checkout", "-b", "develop"], cwd=repo_path, check=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo_path, check=True)

    # Create new task from develop branch
    args_new = SimpleNamespace(branch_name="feature-from-develop", no_launch=True, base="develop")
    multiclaude.cmd_new(args_new)

    # Check environment was created
    environment_dir = os.environ.get("MULTICLAUDE_ENVIRONMENT_DIR")
    expected_environment = Path(environment_dir) / repo_path.name / "mc-feature-from-develop"
    assert expected_environment.exists()

    # Verify the branch was created from develop by checking git history
    env_branch_result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=expected_environment,
        capture_output=True,
        text=True,
    )
    assert env_branch_result.stdout.strip() == "mc-feature-from-develop"

    # Check that the branch was created from develop by verifying the merge-base
    # The merge-base shows the common ancestor commit
    merge_base_result = subprocess.run(
        ["git", "merge-base", "mc-feature-from-develop", "develop"],
        cwd=expected_environment,
        capture_output=True,
        text=True,
    )
    merge_base_commit = merge_base_result.stdout.strip()

    # Get the commit hash of develop branch
    develop_result = subprocess.run(
        ["git", "rev-parse", "develop"],
        cwd=expected_environment,
        capture_output=True,
        text=True,
    )
    develop_commit = develop_result.stdout.strip()

    # Verify they match (merge-base should be develop itself since we branched from it)
    assert merge_base_commit == develop_commit, (
        f"Branch not created from develop. Merge-base: {merge_base_commit}, Develop: {develop_commit}"
    )

    # Check base branch (develop) exists locally
    branches_result = subprocess.run(
        ["git", "branch", "-a"],
        cwd=expected_environment,
        capture_output=True,
        text=True,
    )
    assert "develop" in branches_result.stdout or "remotes/local/develop" in branches_result.stdout


def test_new_with_invalid_base_ref(isolated_repo, capsys):
    """Test that new command fails when base ref doesn't exist."""
    repo_path = isolated_repo

    # Initialize first
    args_init = SimpleNamespace()
    multiclaude.cmd_init(args_init)

    # Try to create task from non-existent branch
    args_new = SimpleNamespace(branch_name="test", no_launch=True, base="nonexistent-branch")
    try:
        multiclaude.cmd_new(args_new)
        assert False, "Should have exited"
    except SystemExit as e:
        assert e.code == 1

    captured = capsys.readouterr()
    assert "does not exist" in captured.err


def test_new_with_origin_remote(isolated_repo):
    """Test new command configures remotes correctly when origin exists."""
    repo_path = isolated_repo

    # Add a fake GitHub remote to the base repo
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:user/repo.git"],
        cwd=repo_path,
        check=True,
    )

    # Initialize multiclaude
    args_init = SimpleNamespace()
    multiclaude.cmd_init(args_init)

    # Create new task
    args_new = SimpleNamespace(branch_name="test-remotes", no_launch=True, base="main")
    multiclaude.cmd_new(args_new)

    # Check environment was created
    environment_dir = os.environ.get("MULTICLAUDE_ENVIRONMENT_DIR")
    expected_environment = Path(environment_dir) / repo_path.name / "mc-test-remotes"
    assert expected_environment.exists()

    # Check 'local' remote points to base repo
    local_result = subprocess.run(
        ["git", "remote", "get-url", "local"],
        cwd=expected_environment,
        capture_output=True,
        text=True,
    )
    assert local_result.returncode == 0
    assert str(repo_path) in local_result.stdout.strip()

    # Check 'origin' remote points to GitHub
    origin_result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=expected_environment,
        capture_output=True,
        text=True,
    )
    assert origin_result.returncode == 0
    assert "github.com:user/repo.git" in origin_result.stdout.strip()

    # Check push.autoSetupRemote is configured
    config_result = subprocess.run(
        ["git", "config", "push.autoSetupRemote"],
        cwd=expected_environment,
        capture_output=True,
        text=True,
    )
    assert config_result.stdout.strip() == "true"

    # Check base branch (main) exists
    branches_result = subprocess.run(
        ["git", "branch", "-a"],
        cwd=expected_environment,
        capture_output=True,
        text=True,
    )
    assert "main" in branches_result.stdout or "remotes/local/main" in branches_result.stdout


def test_new_without_origin_remote(isolated_repo):
    """Test new command when base repo has no origin remote."""
    repo_path = isolated_repo

    # Initialize multiclaude (no origin remote added)
    args_init = SimpleNamespace()
    multiclaude.cmd_init(args_init)

    # Create new task
    args_new = SimpleNamespace(branch_name="test-no-origin", no_launch=True, base="main")
    multiclaude.cmd_new(args_new)

    # Check environment was created
    environment_dir = os.environ.get("MULTICLAUDE_ENVIRONMENT_DIR")
    expected_environment = Path(environment_dir) / repo_path.name / "mc-test-no-origin"
    assert expected_environment.exists()

    # Check 'local' remote exists and points to base repo
    local_result = subprocess.run(
        ["git", "remote", "get-url", "local"],
        cwd=expected_environment,
        capture_output=True,
        text=True,
    )
    assert local_result.returncode == 0
    assert str(repo_path) in local_result.stdout.strip()

    # Check 'origin' remote does NOT exist
    origin_result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=expected_environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert origin_result.returncode != 0  # Should fail since origin doesn't exist

    # Check push.autoSetupRemote is still configured
    config_result = subprocess.run(
        ["git", "config", "push.autoSetupRemote"],
        cwd=expected_environment,
        capture_output=True,
        text=True,
    )
    assert config_result.stdout.strip() == "true"

    # Check base branch (main) exists
    branches_result = subprocess.run(
        ["git", "branch", "-a"],
        cwd=expected_environment,
        capture_output=True,
        text=True,
    )
    assert "main" in branches_result.stdout or "remotes/local/main" in branches_result.stdout


def test_new_reuses_available_environment(isolated_repo, capsys):
    """Test that new command reuses available environments."""
    repo_path = isolated_repo

    # Initialize multiclaude
    args_init = SimpleNamespace()
    multiclaude.cmd_init(args_init)

    # Create first task
    args_new1 = SimpleNamespace(branch_name="task1", no_launch=True, base="main")
    multiclaude.cmd_new(args_new1)

    captured = capsys.readouterr()
    assert "Created new environment" in captured.out
    assert "Reused existing environment" not in captured.out

    # Get the environment path
    environment_dir = os.environ.get("MULTICLAUDE_ENVIRONMENT_DIR")
    task1_path = Path(environment_dir) / repo_path.name / "mc-task1"

    # Manually remove the task to create an available environment
    # (since there's no remove command yet, we use the strategy directly)
    from multiclaude.strategies import CloneStrategy
    from multiclaude.git_utils import get_environment_base_dir
    strategy = CloneStrategy(get_environment_base_dir())
    strategy.remove(task1_path)

    # Verify available environment was created
    repo_dir = Path(environment_dir) / repo_path.name
    available_envs = [
        p for p in repo_dir.iterdir() if p.is_dir() and p.name.startswith("avail-")
    ]
    assert len(available_envs) == 1

    # Create second task - should reuse the available environment
    args_new2 = SimpleNamespace(branch_name="task2", no_launch=True, base="main")
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
