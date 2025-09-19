"""Tests for multiclaude init command."""

import json
import subprocess
from types import SimpleNamespace

from multiclaude import cli as multiclaude


def test_init_success(isolated_repo):
    """Test that init creates all required files and updates git exclude."""
    repo_path = isolated_repo.repo_path

    # Create args object and call init directly
    args = SimpleNamespace()
    multiclaude.cmd_init(args)

    # Check .multiclaude directory exists
    multiclaude_dir = repo_path / ".multiclaude"
    assert multiclaude_dir.exists()
    assert multiclaude_dir.is_dir()

    # Check config.json exists and has correct structure
    config_file = multiclaude_dir / "config.json"
    assert config_file.exists()
    config = json.loads(config_file.read_text())
    assert config["version"] == multiclaude.get_version()
    assert config["repo_root"] == str(repo_path)
    assert "created_at" in config
    assert "default_branch" in config

    # Check tasks.json exists and is empty array
    tasks_file = multiclaude_dir / "tasks.json"
    assert tasks_file.exists()
    tasks = json.loads(tasks_file.read_text())
    assert tasks == []

    # Check .git/info/exclude contains .multiclaude
    exclude_file = repo_path / ".git" / "info" / "exclude"
    assert exclude_file.exists()
    exclude_content = exclude_file.read_text()
    assert ".multiclaude" in exclude_content


def test_init_fails_non_git_repo(tmp_path, monkeypatch, capsys):
    """Test that init fails when not in a git repository."""
    # Create a non-git directory
    non_git_dir = tmp_path / "not-a-repo"
    non_git_dir.mkdir()
    monkeypatch.chdir(non_git_dir)

    # Run init - should exit with error
    args = SimpleNamespace()

    try:
        multiclaude.cmd_init(args)
        assert False, "Should have exited"
    except SystemExit as e:
        assert e.code == 1

    # Check error message
    captured = capsys.readouterr()
    assert "Not a git repository" in captured.err

    # Verify no .multiclaude directory was created
    assert not (non_git_dir / ".multiclaude").exists()


def test_init_idempotent(isolated_repo, capsys):
    """Test that running init twice is safe and doesn't error."""
    repo_path = isolated_repo.repo_path

    # Run init first time
    args = SimpleNamespace()
    multiclaude.cmd_init(args)

    # Get original config
    config_file = repo_path / ".multiclaude" / "config.json"
    original_config = json.loads(config_file.read_text())
    original_created_at = original_config["created_at"]

    # Run init second time
    multiclaude.cmd_init(args)

    # Check message
    captured = capsys.readouterr()
    assert "already initialized" in captured.out.lower()

    # Check config wasn't overwritten (created_at should be same)
    new_config = json.loads(config_file.read_text())
    assert new_config["created_at"] == original_created_at

    # Check .git/info/exclude doesn't have duplicate entries
    exclude_file = repo_path / ".git" / "info" / "exclude"
    exclude_lines = exclude_file.read_text().strip().split("\n")
    multiclaude_count = sum(1 for line in exclude_lines if line.strip() == ".multiclaude")
    assert multiclaude_count == 1


def test_init_from_subdirectory(tmp_path, monkeypatch):
    """Test that init and list commands work from subdirectories."""
    # Create a git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)

    # Create initial commit
    (tmp_path / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True)

    # Create a subdirectory
    subdir = tmp_path / "src" / "nested"
    subdir.mkdir(parents=True)

    # Change to subdirectory
    monkeypatch.chdir(subdir)

    # Initialize multiclaude from subdirectory
    args = SimpleNamespace(environments_dir=None)
    multiclaude.cmd_init(args)

    # Verify config was created in repo root, not current directory
    assert (tmp_path / ".multiclaude" / "config.json").exists()
    assert not (subdir / ".multiclaude" / "config.json").exists()

    # Test list command from subdirectory
    args = SimpleNamespace()
    multiclaude.cmd_list(args)  # Should not raise NotInitializedError
