"""Utilities for managing sandbox environments for testing."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


class SandboxManager:
    """Manages sandbox git repositories and worktrees for testing."""

    def __init__(self, base_path: Path, name: str):
        """Initialize sandbox manager.
        
        Args:
            base_path: Base directory for sandbox (e.g., repos/)
            name: Name of sandbox (e.g., "sandbox" or "test-init-123456")
        """
        self.base_path = Path(base_path)
        self.name = name
        self.repo_path = self.base_path / name / "main"
        self.worktree_path = self.base_path / name / "worktrees"

    def create_sandbox(self) -> None:
        """Create a new sandbox with git repo and worktree directory."""
        # Create directories
        self.repo_path.mkdir(parents=True, exist_ok=True)
        self.worktree_path.mkdir(parents=True, exist_ok=True)

        # Initialize git repo
        subprocess.run(
            ["git", "init"],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
        )

        # Create initial commit
        readme = self.repo_path / "README.md"
        readme.write_text(f"# Test Repository - {self.name}\n")
        
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
        )
        
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
        )

    def reset_sandbox(self) -> None:
        """Reset sandbox by deleting and recreating it."""
        self.cleanup_sandbox()
        self.create_sandbox()

    def cleanup_sandbox(self) -> None:
        """Remove all sandbox files."""
        sandbox_dir = self.base_path / self.name
        if sandbox_dir.exists():
            shutil.rmtree(sandbox_dir)


    @property
    def exists(self) -> bool:
        """Check if sandbox exists."""
        return self.repo_path.exists()

    @property
    def is_initialized(self) -> bool:
        """Check if multiclaude is initialized in sandbox."""
        return (self.repo_path / ".multiclaude").exists()

    def get_worktree_count(self) -> int:
        """Get number of worktrees in sandbox."""
        if not self.worktree_path.exists():
            return 0
        # Count subdirectories in worktrees/<repo-name>/
        repo_worktree_dir = self.worktree_path / self.repo_path.name
        if not repo_worktree_dir.exists():
            return 0
        return len(list(repo_worktree_dir.iterdir()))