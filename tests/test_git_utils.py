"""Tests for git utility functions."""

import os
import subprocess

from multiclaude.git_utils import get_git_root


def test_get_git_root_from_root(tmp_path):
    """Test getting git root when already at root."""
    # Create a git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    # Get root from the root directory
    root = get_git_root(tmp_path)
    assert root == tmp_path


def test_get_git_root_from_subdirectory(tmp_path):
    """Test getting git root from a subdirectory."""
    # Create a git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    # Create a subdirectory
    subdir = tmp_path / "subdir" / "nested"
    subdir.mkdir(parents=True)

    # Get root from the subdirectory
    root = get_git_root(subdir)
    assert root == tmp_path


def test_get_git_root_not_in_repo(tmp_path):
    """Test get_git_root returns None when not in a git repo."""
    # Don't initialize git repo
    root = get_git_root(tmp_path)
    assert root is None


def test_get_git_root_uses_cwd_by_default(tmp_path):
    """Test get_git_root uses current working directory by default."""
    # Create a git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    # Create a subdirectory
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    # Change to subdirectory and test without arguments
    original_cwd = os.getcwd()
    try:
        os.chdir(subdir)
        root = get_git_root()
        assert root == tmp_path
    finally:
        os.chdir(original_cwd)
