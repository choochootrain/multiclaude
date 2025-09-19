"""Test CloneStrategy implementation details."""

import subprocess

from multiclaude.strategies import CloneStrategy, generate_hash


def create_mock_config(base_dir):
    """Create a mock Config with the given base_dir."""
    from pathlib import Path

    from multiclaude.config import Config

    return Config(
        version="1.0.0",
        repo_root=Path.cwd(),
        default_branch="main",
        created_at="2024-01-01",
        environment_strategy="clone",
        default_agent="claude",
        environments_dir=base_dir,
    )


def test_generate_hash():
    """Test hash generation for available environment names."""
    hash1 = generate_hash()
    hash2 = generate_hash()

    # Should be 7 chars by default
    assert len(hash1) == 7
    assert len(hash2) == 7

    # Should be different
    assert hash1 != hash2

    # Should be alphanumeric lowercase
    assert all(c.islower() or c.isdigit() for c in hash1)
    assert all(c.islower() or c.isdigit() for c in hash2)

    # Test custom length
    hash3 = generate_hash(10)
    assert len(hash3) == 10


def test_find_available_environment(tmp_path):
    """Test finding available environments in various scenarios."""
    repo_name = "test-repo"
    mock_config = create_mock_config(tmp_path)
    strategy = CloneStrategy(mock_config)

    # Test when no environment directory exists
    result = strategy.find_available_environment(repo_name)
    assert result is None

    # Test when directory exists but no available envs
    repo_dir = tmp_path / repo_name
    repo_dir.mkdir()
    (repo_dir / "mc-my-feature-task").mkdir()  # Task environment, not available
    (repo_dir / "mc-another-task").mkdir()  # Another task environment

    result = strategy.find_available_environment(repo_name)
    assert result is None

    # Test when one available env exists
    available_env = repo_dir / "avail-abc123"
    available_env.mkdir()

    result = strategy.find_available_environment(repo_name)
    assert result == available_env

    # Test when multiple available envs exist
    env2 = repo_dir / "avail-xyz789"
    env2.mkdir()

    result = strategy.find_available_environment(repo_name)
    # Should return one of them (we don't care which)
    assert result in [available_env, env2]


def test_clone_strategy_reuses_available_environment(isolated_git_repo, tmp_path):
    """Test that CloneStrategy reuses available environments."""
    repo_path = isolated_git_repo
    mock_config = create_mock_config(tmp_path)
    strategy = CloneStrategy(mock_config)

    # Create first task
    task1_path, was_reused = strategy.create(repo_path, "mc-task1", "main")
    assert not was_reused  # First creation should not be reused
    assert task1_path.exists()
    assert task1_path.name == "mc-task1"

    # Remove the first task (should create available environment)
    strategy.remove(task1_path)
    assert not task1_path.exists()

    # Check that an available environment was created
    repo_name = repo_path.name
    repo_dir = tmp_path / repo_name
    available_envs = [p for p in repo_dir.iterdir() if p.is_dir() and p.name.startswith("avail-")]
    assert len(available_envs) == 1

    # Create second task (should reuse available environment)
    task2_path, was_reused = strategy.create(repo_path, "mc-task2", "main")

    assert was_reused  # Second creation should reuse available environment
    assert task2_path.exists()
    assert task2_path.name == "mc-task2"

    # The available environment should no longer exist
    available_envs_after = [
        p for p in repo_dir.iterdir() if p.is_dir() and p.name.startswith("avail-")
    ]
    assert len(available_envs_after) == 0


def test_clone_strategy_remove_creates_available_environment(isolated_git_repo, tmp_path):
    """Test that removing a clone creates a clean available environment."""
    repo_path = isolated_git_repo
    mock_config = create_mock_config(tmp_path)
    strategy = CloneStrategy(mock_config)

    # Create a task
    task_path, was_reused = strategy.create(repo_path, "mc-test-task", "main")
    assert not was_reused  # Should be newly created
    assert task_path.exists()

    # Make some changes in the environment to test cleanup
    test_file = task_path / "test.txt"
    test_file.write_text("uncommitted changes")

    # Create a different branch to test reset
    subprocess.run(
        ["git", "checkout", "-b", "feature-branch"],
        cwd=task_path,
        check=True,
    )

    # Remove the task
    strategy.remove(task_path)

    # Original task should not exist
    assert not task_path.exists()

    # Available environment should exist
    repo_name = repo_path.name
    repo_dir = tmp_path / repo_name
    available_envs = [p for p in repo_dir.iterdir() if p.is_dir() and p.name.startswith("avail-")]
    assert len(available_envs) == 1

    # The available environment should be clean (no uncommitted changes)
    available_env = available_envs[0]
    assert not (available_env / "test.txt").exists()

    # Should be on default branch (main or master)
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        cwd=available_env,
        check=True,
    )
    assert result.stdout.strip() in ["main", "master"]

    # Should have no uncommitted changes
    status_result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=available_env,
        check=True,
    )
    assert status_result.stdout.strip() == ""
