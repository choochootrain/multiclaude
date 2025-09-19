"""Tests for multiclaude config command."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from multiclaude import cli as multiclaude


def test_config_read_existing_value(initialized_repo):
    """Test reading an existing configuration value."""

    # Read default_branch
    args_config = SimpleNamespace(path="default_branch", write=None)
    multiclaude.cmd_config(args_config)


def test_config_read_nonexistent_value(isolated_repo, capsys):
    """Test reading a configuration value that doesn't exist."""

    # Initialize first - don't set environments_dir so it gets default
    args_init = SimpleNamespace()
    multiclaude.cmd_init(args_init)

    # Read environments_dir - should show the default
    args_config = SimpleNamespace(path="environments_dir", write=None)
    multiclaude.cmd_config(args_config)

    captured = capsys.readouterr()
    # When environments_dir is not explicitly set, it uses the default
    assert "multiclaude-environments" in captured.out


def test_config_write_environments_dir(initialized_repo, capsys):
    """Test writing environments_dir configuration."""
    repo_path = initialized_repo.repo_path

    # Write environments_dir
    test_dir = repo_path.parent / "test-environments"
    args_config = SimpleNamespace(path="environments_dir", write=str(test_dir))
    multiclaude.cmd_config(args_config)

    captured = capsys.readouterr()
    assert f"Set environments_dir = {test_dir}" in captured.out

    # Verify it was saved
    config_file = repo_path / ".multiclaude" / "config.json"
    config = json.loads(config_file.read_text())
    assert config["environments_dir"] == str(test_dir)


def test_config_write_environment_strategy(initialized_repo, capsys):
    """Test writing environment_strategy configuration."""
    repo_path = initialized_repo.repo_path

    # Write valid strategy
    args_config = SimpleNamespace(path="environment_strategy", write="worktree")
    multiclaude.cmd_config(args_config)

    captured = capsys.readouterr()
    assert "Set environment_strategy = worktree" in captured.out

    # Verify it was saved
    config_file = repo_path / ".multiclaude" / "config.json"
    config = json.loads(config_file.read_text())
    assert config["environment_strategy"] == "worktree"


def test_config_write_invalid_strategy(initialized_repo, capsys):
    """Test writing invalid environment_strategy fails."""

    # Write invalid strategy
    args_config = SimpleNamespace(path="environment_strategy", write="invalid")

    with pytest.raises(SystemExit):
        multiclaude.cmd_config(args_config)

    captured = capsys.readouterr()
    assert "Invalid environment strategy: invalid" in captured.err


def test_config_write_default_agent(initialized_repo, capsys):
    """Test writing default_agent configuration."""
    repo_path = initialized_repo.repo_path

    # Write valid agent
    args_config = SimpleNamespace(path="default_agent", write="cursor")
    multiclaude.cmd_config(args_config)

    captured = capsys.readouterr()
    assert "Set default_agent = cursor" in captured.out

    # Verify it was saved
    config_file = repo_path / ".multiclaude" / "config.json"
    config = json.loads(config_file.read_text())
    assert config["default_agent"] == "cursor"


def test_config_write_invalid_agent(initialized_repo, capsys):
    """Test writing empty default_agent fails."""

    # Write empty agent
    args_config = SimpleNamespace(path="default_agent", write="")

    with pytest.raises(SystemExit):
        multiclaude.cmd_config(args_config)

    captured = capsys.readouterr()
    assert "Default agent must be a non-empty string" in captured.err


def test_config_write_readonly_field(initialized_repo, capsys):
    """Test that writing to read-only fields fails."""

    # Try to write to version (read-only)
    args_config = SimpleNamespace(path="version", write="2.0.0")

    with pytest.raises(SystemExit):
        multiclaude.cmd_config(args_config)

    captured = capsys.readouterr()
    assert "Configuration key 'version' is read-only" in captured.err


def test_config_unknown_path(initialized_repo, capsys):
    """Test that accessing unknown configuration paths fails."""

    # Try to read unknown path
    args_config = SimpleNamespace(path="unknown_field", write=None)

    with pytest.raises(SystemExit):
        multiclaude.cmd_config(args_config)

    captured = capsys.readouterr()
    assert "Unknown configuration field: unknown_field" in captured.err


def test_config_write_unknown_path(initialized_repo, capsys):
    """Test that writing to unknown configuration paths fails."""

    # Try to write to unknown path
    args_config = SimpleNamespace(path="unknown_field", write="value")

    with pytest.raises(SystemExit):
        multiclaude.cmd_config(args_config)

    captured = capsys.readouterr()
    assert "Unknown configuration field: unknown_field" in captured.err


def test_config_not_initialized(isolated_repo, capsys):
    """Test config command fails when multiclaude not initialized."""

    # Don't initialize, just try to use config
    args_config = SimpleNamespace(path="default_branch", write=None)

    with pytest.raises(SystemExit):
        multiclaude.cmd_config(args_config)

    captured = capsys.readouterr()
    assert "Multiclaude not initialized" in captured.err


def test_config_environments_dir_validation(initialized_repo, capsys):
    """Test that environments_dir validation checks parent directory."""

    # Try to write to a path with non-existent parent
    invalid_path = "/nonexistent/parent/dir/environments"
    args_config = SimpleNamespace(path="environments_dir", write=invalid_path)

    with pytest.raises(SystemExit):
        multiclaude.cmd_config(args_config)

    captured = capsys.readouterr()
    assert "Parent directory does not exist" in captured.err


def test_config_environments_dir_expansion(initialized_repo, capsys):
    """Test that environments_dir expands ~ and resolves paths."""
    repo_path = initialized_repo.repo_path

    # Write with ~ path
    args_config = SimpleNamespace(path="environments_dir", write="~/test-environments")
    multiclaude.cmd_config(args_config)

    # Verify it was expanded
    config_file = repo_path / ".multiclaude" / "config.json"
    config = json.loads(config_file.read_text())
    assert config["environments_dir"] == str(Path.home() / "test-environments")
    assert "~" not in config["environments_dir"]
