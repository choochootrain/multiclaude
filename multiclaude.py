#!/usr/bin/env python3
"""Multiclaude - CLI tool for managing parallel Claude Code instances with git worktrees."""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


class MultiClaudeError(Exception):
    """Base exception for multiclaude errors."""

    pass


class NotGitRepoError(MultiClaudeError):
    """Raised when not in a git repository."""

    pass


class NotInitializedError(MultiClaudeError):
    """Raised when multiclaude is not initialized."""

    pass


class ClaudeNotFoundError(MultiClaudeError):
    """Raised when Claude Code is not installed."""

    pass


class BranchExistsError(MultiClaudeError):
    """Raised when branch already exists."""

    pass


@dataclass
class Task:
    """Represents a multiclaude task."""

    id: str
    branch: str
    created_at: str
    status: str
    worktree_path: str
    pruned_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """Create Task from dictionary."""
        return cls(**data)


class MultiClaudeConfig:
    """Manages multiclaude configuration."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.config_dir = repo_root / ".multiclaude"
        self.config_file = self.config_dir / "config.json"

    def exists(self) -> bool:
        """Check if multiclaude is initialized."""
        return self.config_dir.exists() and self.config_file.exists()

    def initialize(self) -> None:
        """Initialize multiclaude configuration."""
        self.config_dir.mkdir(exist_ok=True)

        config = {
            "version": "1.0.0",
            "repo_root": str(self.repo_root),
            "default_branch": self._get_default_branch(),
            "created_at": datetime.now().isoformat(),
        }

        self.config_file.write_text(json.dumps(config, indent=2))

        # Add .multiclaude to .git/info/exclude
        exclude_file = self.repo_root / ".git" / "info" / "exclude"
        if exclude_file.exists():
            content = exclude_file.read_text()
            if ".multiclaude" not in content:
                exclude_file.write_text(content + "\n.multiclaude\n")

    def load(self) -> dict[str, Any]:
        """Load configuration."""
        if not self.exists():
            raise NotInitializedError("Multiclaude not initialized. Run 'multiclaude init' first.")
        return json.loads(self.config_file.read_text())

    def _get_default_branch(self) -> str:
        """Get the default branch name."""
        try:
            result = subprocess.run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                # refs/remotes/origin/main -> main
                return result.stdout.strip().split("/")[-1]
        except Exception:
            pass
        return "main"


class TaskManager:
    """Manages tasks in tasks.json."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.tasks_file = repo_root / ".multiclaude" / "tasks.json"

    def initialize(self) -> None:
        """Initialize empty tasks file."""
        self.tasks_file.write_text("[]")

    def load_tasks(self) -> list[Task]:
        """Load all tasks."""
        if not self.tasks_file.exists():
            return []
        data = json.loads(self.tasks_file.read_text())
        return [Task.from_dict(task) for task in data]

    def save_tasks(self, tasks: list[Task]) -> None:
        """Save tasks to file."""
        data = [asdict(task) for task in tasks]
        self.tasks_file.write_text(json.dumps(data, indent=2))

    def add_task(self, task: Task) -> None:
        """Add a new task."""
        tasks = self.load_tasks()
        tasks.append(task)
        self.save_tasks(tasks)

    def get_task(self, branch_name: str) -> Task | None:
        """Get task by branch name."""
        tasks = self.load_tasks()
        for task in tasks:
            if task.branch == branch_name:
                return task
        return None


class GitWorktreeManager:
    """Manages git worktree operations."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    def is_git_repo(self) -> bool:
        """Check if current directory is a git repository."""
        return (self.repo_root / ".git").exists()

    def branch_exists(self, branch_name: str) -> bool:
        """Check if branch already exists."""
        result = subprocess.run(
            ["git", "branch", "--list", branch_name],
            capture_output=True,
            text=True,
            check=False,
        )
        return bool(result.stdout.strip())

    def create_worktree(self, worktree_path: Path, branch_name: str) -> None:
        """Create a new worktree with branch."""
        # Create parent directories if needed
        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        # Create worktree with new branch
        result = subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", branch_name],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise MultiClaudeError(f"Failed to create worktree: {result.stderr}")

    def list_worktrees(self) -> list[dict[str, str]]:
        """List all worktrees."""
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )

        worktrees = []
        current = {}
        for line in result.stdout.strip().split("\n"):
            if not line:
                if current:
                    worktrees.append(current)
                    current = {}
            elif line.startswith("worktree "):
                current["path"] = line[9:]
            elif line.startswith("branch "):
                current["branch"] = line[7:].replace("refs/heads/", "")

        if current:
            worktrees.append(current)

        return worktrees


def get_repo_name(repo_root: Path) -> str:
    """Get repository name from path."""
    return repo_root.name


def get_worktree_base_dir() -> Path:
    """Get base directory for worktrees."""
    # Check environment variable first
    if env_dir := os.environ.get("MULTICLAUDE_WORKTREE_DIR"):
        return Path(env_dir)
    return Path.home() / "multiclaude-worktrees"


def cmd_init(args: argparse.Namespace) -> None:
    """Initialize multiclaude in current repository."""
    repo_root = Path.cwd()
    git_mgr = GitWorktreeManager(repo_root)

    if not git_mgr.is_git_repo():
        print("Error: Not a git repository. Please run this command in a git repo.", file=sys.stderr)
        sys.exit(1)

    config = MultiClaudeConfig(repo_root)
    if config.exists():
        print("Multiclaude already initialized in this repository.")
        return

    config.initialize()
    task_mgr = TaskManager(repo_root)
    task_mgr.initialize()

    print("✓ Initialized multiclaude in this repository")
    print(f"✓ Created .multiclaude/ directory")
    print(f"✓ Added .multiclaude to .git/info/exclude")


def cmd_new(args: argparse.Namespace) -> None:
    """Create new task with worktree and launch Claude."""
    repo_root = Path.cwd()
    config = MultiClaudeConfig(repo_root)

    if not config.exists():
        print("Error: Multiclaude not initialized. Run 'multiclaude init' first.", file=sys.stderr)
        sys.exit(1)

    # Check if claude is installed
    claude_check = subprocess.run(
        ["which", "claude"],
        capture_output=True,
        check=False,
    )
    if claude_check.returncode != 0:
        print("Error: Claude Code not found. Please install Claude Code first.", file=sys.stderr)
        print("Visit: https://claude.ai/download", file=sys.stderr)
        sys.exit(1)

    branch_name = f"mc-{args.branch_name}"
    git_mgr = GitWorktreeManager(repo_root)

    if git_mgr.branch_exists(branch_name):
        print(f"Error: Branch '{branch_name}' already exists.", file=sys.stderr)
        sys.exit(1)

    # Create worktree path
    repo_name = get_repo_name(repo_root)
    worktree_base = get_worktree_base_dir()
    worktree_path = worktree_base / repo_name / branch_name

    print(f"Creating worktree at {worktree_path}...")

    try:
        git_mgr.create_worktree(worktree_path, branch_name)
    except MultiClaudeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Add task to tasks.json
    task = Task(
        id=branch_name,
        branch=branch_name,
        created_at=datetime.now().isoformat(),
        status="active",
        worktree_path=str(worktree_path),
    )
    task_mgr = TaskManager(repo_root)
    task_mgr.add_task(task)

    print(f"✓ Created worktree for branch '{branch_name}'")

    if not args.no_launch:
        print(f"Launching Claude Code in {worktree_path}...")
        os.chdir(worktree_path)
        subprocess.run(["claude"], check=False)
    else:
        print(f"Changing to worktree directory: {worktree_path}")
        # Can't actually change parent's directory, but we can print instruction
        print(f"Run: cd {worktree_path}")


def cmd_list(args: argparse.Namespace) -> None:
    """List all multiclaude tasks."""
    repo_root = Path.cwd()
    config = MultiClaudeConfig(repo_root)

    if not config.exists():
        print("Error: Multiclaude not initialized. Run 'multiclaude init' first.", file=sys.stderr)
        sys.exit(1)

    task_mgr = TaskManager(repo_root)
    tasks = task_mgr.load_tasks()

    if not tasks:
        print("No multiclaude tasks found.")
        return

    # Get actual worktrees
    git_mgr = GitWorktreeManager(repo_root)
    worktrees = git_mgr.list_worktrees()
    worktree_branches = {wt.get("branch") for wt in worktrees if wt.get("branch")}

    # Separate active and pruned tasks
    active_tasks = []
    pruned_tasks = []

    for task in tasks:
        if task.status == "pruned":
            pruned_tasks.append(task)
        else:
            # Check if worktree still exists
            if task.branch not in worktree_branches:
                task.status = "missing"
            active_tasks.append(task)

    # Display active tasks
    if active_tasks:
        print("Active multiclaude tasks:")
        for task in active_tasks:
            created = datetime.fromisoformat(task.created_at)
            age = datetime.now() - created
            if age.days > 0:
                age_str = f"{age.days}d ago"
            elif age.seconds > 3600:
                age_str = f"{age.seconds // 3600}h ago"
            else:
                age_str = f"{age.seconds // 60}m ago"

            status = "" if task.status == "active" else f" [{task.status}]"
            print(f"  - {task.branch}: branch {task.branch} (created {age_str}){status}")

    # Display pruned tasks if any
    if pruned_tasks and args.show_pruned:
        print("\nPruned tasks (metadata retained):")
        for task in pruned_tasks:
            pruned = datetime.fromisoformat(task.pruned_at or task.created_at)
            age = datetime.now() - pruned
            if age.days > 0:
                age_str = f"{age.days}d ago"
            else:
                age_str = f"{age.seconds // 3600}h ago"
            print(f"  - {task.branch}: branch {task.branch} (pruned {age_str})")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Multiclaude - Manage parallel Claude Code instances with git worktrees"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init command
    parser_init = subparsers.add_parser("init", help="Initialize multiclaude in current repository")
    parser_init.set_defaults(func=cmd_init)

    # new command
    parser_new = subparsers.add_parser("new", help="Create new task with worktree")
    parser_new.add_argument("branch_name", help="Branch name for the task (mc- prefix added automatically)")
    parser_new.add_argument("--no-launch", action="store_true", help="Don't launch Claude Code")
    parser_new.set_defaults(func=cmd_new)

    # list command
    parser_list = subparsers.add_parser("list", help="List all multiclaude tasks")
    parser_list.add_argument("--show-pruned", action="store_true", help="Show pruned tasks")
    parser_list.set_defaults(func=cmd_list)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()