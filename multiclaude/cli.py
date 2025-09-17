#!/usr/bin/env python3
"""Multiclaude - CLI tool for managing parallel Claude Code instances with git worktrees."""

import argparse
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import MultiClaudeError, NotInitializedError
from .git_utils import branch_exists, is_git_repo, ref_exists
from .strategies import get_strategy

DEFAULT_AGENT = "claude"


@dataclass
class Task:
    """Represents a multiclaude task."""

    id: str
    branch: str
    created_at: str
    status: str
    environment_path: str
    agent: str = DEFAULT_AGENT
    pruned_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """Create Task from dictionary."""
        normalized = data.copy()
        agent = normalized.get("agent")
        if not isinstance(agent, str) or not agent.strip():
            normalized["agent"] = DEFAULT_AGENT
        else:
            normalized["agent"] = agent.strip()
        return cls(**normalized)


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
            "version": get_version(),
            "repo_root": str(self.repo_root),
            "default_branch": self._get_default_branch(),
            "created_at": datetime.now().isoformat(),
            "environment_strategy": "clone",
            "default_agent": DEFAULT_AGENT,
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
        config = json.loads(self.config_file.read_text())
        if "default_agent" not in config or not isinstance(config["default_agent"], str):
            config["default_agent"] = DEFAULT_AGENT
        return config

    def _get_default_branch(self) -> str:
        """Get the default branch name."""
        try:
            result = subprocess.run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                capture_output=True,
                text=True,
                check=False,
                cwd=self.repo_root,
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


def _normalize_task_selectors(raw: str) -> set[str]:
    """Return possible task branch names for a user-provided selector."""

    normalized = raw.strip()
    if not normalized:
        return set()
    selectors = {normalized}
    if not normalized.startswith("mc-"):
        selectors.add(f"mc-{normalized}")
    return selectors


def _evaluate_prune_candidate(task: Task, default_branch: str, force: bool) -> dict[str, Any]:
    """Inspect a task/environment to determine prune safety."""

    env_path = Path(task.environment_path).expanduser()
    issues: list[str] = []
    warnings: list[str] = []

    if not env_path.exists():
        return {
            "prune": True,
            "reason": "Environment directory missing (stale metadata)",
            "issues": issues,
            "warnings": warnings,
            "env_exists": False,
            "cleanup_only": True,
        }

    status_proc = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
        cwd=env_path,
    )

    if status_proc.returncode != 0:
        details = status_proc.stderr.strip() or status_proc.stdout.strip() or "unknown error"
        issues.append(f"failed to inspect git status: {details}")
        if not force:
            return {
                "prune": False,
                "reason": issues[0],
                "issues": issues,
                "warnings": warnings,
                "env_exists": True,
                "cleanup_only": False,
            }
    elif status_proc.stdout.strip():
        issues.append("uncommitted changes present")

    remote_proc = subprocess.run(
        ["git", "remote"],
        capture_output=True,
        text=True,
        check=False,
        cwd=env_path,
    )

    if remote_proc.returncode != 0:
        details = remote_proc.stderr.strip() or remote_proc.stdout.strip() or "unknown error"
        issues.append(f"failed to list git remotes: {details}")
    else:
        remotes = {line.strip() for line in remote_proc.stdout.splitlines() if line.strip()}
        if "origin" not in remotes:
            issues.append("origin remote not configured (cannot verify pushed commits)")
        else:
            remote_branch = f"origin/{task.branch}"
            rev_parse = subprocess.run(
                ["git", "rev-parse", "--verify", remote_branch],
                capture_output=True,
                text=True,
                check=False,
                cwd=env_path,
            )
            if rev_parse.returncode != 0:
                issues.append(f"remote branch {remote_branch} not found (unpushed commits)")
            else:
                log_proc = subprocess.run(
                    ["git", "log", f"{remote_branch}..HEAD"],
                    capture_output=True,
                    text=True,
                    check=False,
                    cwd=env_path,
                )
                if log_proc.returncode != 0:
                    details = log_proc.stderr.strip() or log_proc.stdout.strip() or "unknown error"
                    issues.append(f"failed to compare with {remote_branch}: {details}")
                elif log_proc.stdout.strip():
                    issues.append("unpushed commits present")

    fetch_proc = subprocess.run(
        ["git", "fetch", "--all"],
        capture_output=True,
        text=True,
        check=False,
        cwd=env_path,
    )
    if fetch_proc.returncode != 0:
        details = fetch_proc.stderr.strip() or fetch_proc.stdout.strip() or "unknown error"
        warnings.append(f"git fetch --all failed: {details}")

    merged_proc = subprocess.run(
        ["git", "branch", "--merged", default_branch],
        capture_output=True,
        text=True,
        check=False,
        cwd=env_path,
    )

    merged = False
    if merged_proc.returncode != 0:
        details = merged_proc.stderr.strip() or merged_proc.stdout.strip() or "unknown error"
        issues.append(f"failed to check merge status against {default_branch}: {details}")
    else:
        merged_branches = {
            line.strip().lstrip("*").strip()
            for line in merged_proc.stdout.splitlines()
            if line.strip()
        }
        merged = task.branch in merged_branches
        if not merged:
            issues.append(f"branch not merged into {default_branch}")

    if not issues and merged:
        return {
            "prune": True,
            "reason": f"Branch merged into {default_branch}",
            "issues": issues,
            "warnings": warnings,
            "env_exists": True,
            "cleanup_only": False,
        }

    if force:
        return {
            "prune": True,
            "reason": issues[0] if issues else f"Force pruning {task.branch}",
            "issues": issues,
            "warnings": warnings,
            "env_exists": True,
            "cleanup_only": False,
        }

    reason = issues[0] if issues else "No safe prune condition met"
    return {
        "prune": False,
        "reason": reason,
        "issues": issues,
        "warnings": warnings,
        "env_exists": True,
        "cleanup_only": False,
    }


def cmd_init(args: argparse.Namespace) -> None:
    """Initialize multiclaude in current repository."""
    repo_root = Path.cwd()

    if not is_git_repo(repo_root):
        print(
            "Error: Not a git repository. Please run this command in a git repo.", file=sys.stderr
        )
        sys.exit(1)

    config = MultiClaudeConfig(repo_root)
    if config.exists():
        print("Multiclaude already initialized in this repository.")
        return

    config.initialize()
    task_mgr = TaskManager(repo_root)
    task_mgr.initialize()

    print("✓ Initialized multiclaude in this repository")
    print("✓ Created .multiclaude/ directory")
    print("✓ Added .multiclaude to .git/info/exclude")


def cmd_new(args: argparse.Namespace) -> None:
    """Create new task with isolated environment and launch Claude."""
    repo_root = Path.cwd()
    mc_config = MultiClaudeConfig(repo_root)

    if not mc_config.exists():
        print("Error: Multiclaude not initialized. Run 'multiclaude init' first.", file=sys.stderr)
        sys.exit(1)

    config = mc_config.load()
    strategy_name = config.get("environment_strategy", "clone")
    strategy = get_strategy(strategy_name)

    agent_name = (
        args.agent if args.agent is not None else config.get("default_agent", DEFAULT_AGENT)
    )
    if not isinstance(agent_name, str) or not agent_name.strip():
        print(
            "Error: Agent name cannot be empty. Provide a command with --agent or set default_agent in .multiclaude/config.json.",
            file=sys.stderr,
        )
        sys.exit(1)
    agent_name = agent_name.strip()

    agent_path = shutil.which(agent_name)
    if agent_path is None:
        print(
            f"Error: Agent '{agent_name}' not found on PATH. Install it or update --agent/default_agent to a valid command.",
            file=sys.stderr,
        )
        sys.exit(1)

    branch_name = f"mc-{args.branch_name}"

    if branch_exists(repo_root, branch_name):
        print(f"Error: Branch '{branch_name}' already exists.", file=sys.stderr)
        sys.exit(1)

    # Validate base ref exists
    if not ref_exists(repo_root, args.base):
        print(f"Error: Base ref '{args.base}' does not exist.", file=sys.stderr)
        sys.exit(1)

    print(
        f"Creating new isolated environment for '{branch_name}' from '{args.base}' using strategy: {strategy.name} (agent: {agent_name})"
    )

    try:
        environment_path, was_reused = strategy.create(repo_root, branch_name, base_ref=args.base)
    except MultiClaudeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Add task to tasks.json
    task = Task(
        id=branch_name,
        branch=branch_name,
        created_at=datetime.now().isoformat(),
        status="active",
        environment_path=str(environment_path),
        agent=agent_name,
    )
    task_mgr = TaskManager(repo_root)
    task_mgr.add_task(task)

    if was_reused:
        print(f"✓ Reused existing environment for branch '{branch_name}' at {environment_path}")
    else:
        print(f"✓ Created new environment for branch '{branch_name}' at {environment_path}")

    if not args.no_launch:
        print(f"Launching {agent_name} in {environment_path}...")
        os.chdir(environment_path)
        subprocess.run([agent_name], check=False)
    else:
        print(f"To start working, run: cd {environment_path}")


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

    # Separate active and pruned tasks
    active_tasks = []
    pruned_tasks = []

    for task in tasks:
        if task.status == "pruned" or task.pruned_at is not None:
            pruned_tasks.append(task)
            continue

        # Check if environment still exists
        environment_exists = Path(task.environment_path).expanduser().exists()

        if not environment_exists:
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
            agent_info = f" agent={task.agent}" if task.agent else ""
            print(
                f"  - {task.branch}: branch {task.branch} (created {age_str}){status}{agent_info}"
            )

    # Display pruned tasks if any
    if pruned_tasks and args.show_pruned:
        print("\nPruned tasks (metadata retained):")
        for task in pruned_tasks:
            pruned = datetime.fromisoformat(task.pruned_at or task.created_at)
            age = datetime.now() - pruned
            age_str = f"{age.days}d ago" if age.days > 0 else f"{age.seconds // 3600}h ago"
            agent_info = f" agent={task.agent}" if task.agent else ""
            print(f"  - {task.branch}: branch {task.branch} (pruned {age_str}){agent_info}")


def cmd_prune(args: argparse.Namespace) -> None:
    """Prune completed or stale multiclaude environments."""

    repo_root = Path.cwd()
    config = MultiClaudeConfig(repo_root)

    if not config.exists():
        print("Error: Multiclaude not initialized. Run 'multiclaude init' first.", file=sys.stderr)
        sys.exit(1)

    config_data = config.load()
    default_branch = config_data.get("default_branch", "main")
    strategy_name = config_data.get("environment_strategy", "clone")
    strategy = get_strategy(strategy_name)

    task_mgr = TaskManager(repo_root)
    tasks = task_mgr.load_tasks()
    if not tasks:
        print("No multiclaude tasks found.")
        return

    if args.task_name:
        selectors = _normalize_task_selectors(args.task_name)
        tasks_to_consider = [
            task for task in tasks if task.branch in selectors or task.id in selectors
        ]
        if not tasks_to_consider:
            print(f"Error: No task found matching '{args.task_name}'.", file=sys.stderr)
            sys.exit(1)
    else:
        tasks_to_consider = tasks

    prune_candidates: list[tuple[Task, dict[str, Any]]] = []

    for task in tasks_to_consider:
        if task.status == "pruned":
            print(f"Skipping {task.branch}: already pruned")
            continue

        evaluation = _evaluate_prune_candidate(task, default_branch, args.force)

        for warning in evaluation.get("warnings", []):
            print(f"Warning for {task.branch}: {warning}")

        if evaluation["prune"]:
            prune_candidates.append((task, evaluation))
        else:
            print(f"Skipping {task.branch}: {evaluation['reason']}")

    if not prune_candidates:
        print("No tasks eligible for pruning.")
        return

    if args.dry_run:
        print("Dry run mode enabled. No changes will be made.")
        for task, evaluation in prune_candidates:
            reason = evaluation.get("reason", "")
            print(f"Dry run: would prune {task.branch} ({reason}).")
        return

    if not args.yes:
        branches = ", ".join(task.branch for task, _ in prune_candidates)
        try:
            response = input(f"Prune {len(prune_candidates)} task(s): {branches}? [y/N]: ")
        except (EOFError, KeyboardInterrupt):
            print("Prune cancelled.")
            return
        if response.strip().lower() not in {"y", "yes"}:
            print("Prune cancelled.")
            return

    pruned_any = False

    for task, evaluation in prune_candidates:
        env_path = Path(task.environment_path).expanduser()
        cleanup_only = evaluation.get("cleanup_only", False)
        issues = evaluation.get("issues", [])
        reason = evaluation.get("reason", "")

        if cleanup_only:
            print(f"Pruned task {task.branch}: {reason}")
        else:
            try:
                strategy.remove(env_path)
            except MultiClaudeError as exc:
                print(f"Error pruning {task.branch}: {exc}", file=sys.stderr)
                continue

            if args.force and issues:
                print(f"Force pruning {task.branch}: ignoring {', '.join(issues)}")
            else:
                print(f"Pruned task {task.branch}: {reason}")

        pruned_any = True
        task.status = "pruned"
        task.pruned_at = datetime.now().isoformat()

    if pruned_any:
        task_mgr.save_tasks(tasks)


def get_version() -> str:
    """Get the version of multiclaude."""
    try:
        return importlib.metadata.version("multiclaude")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Multiclaude - Manage parallel Claude Code instances with isolated environments"
    )
    parser.add_argument("--version", action="version", version=f"multiclaude {get_version()}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init command
    parser_init = subparsers.add_parser("init", help="Initialize multiclaude in current repository")
    parser_init.set_defaults(func=cmd_init)

    # new command
    parser_new = subparsers.add_parser("new", help="Create new task with isolated environment")
    parser_new.add_argument(
        "branch_name", help="Branch name for the task (mc- prefix added automatically)"
    )
    parser_new.add_argument("--no-launch", "-n", action="store_true", help="Don't launch the agent")
    parser_new.add_argument(
        "--base",
        default="main",
        help="Base branch/commit/tag to branch from (default: main)",
    )
    parser_new.add_argument(
        "--agent",
        "-a",
        help="Command to launch for this task's agent (defaults to config default_agent)",
    )
    parser_new.set_defaults(func=cmd_new)

    # list command
    parser_list = subparsers.add_parser("list", help="List all multiclaude tasks")
    parser_list.add_argument("--show-pruned", action="store_true", help="Show pruned tasks")
    parser_list.set_defaults(func=cmd_list)

    # prune command
    parser_prune = subparsers.add_parser("prune", help="Prune merged or stale tasks")
    parser_prune.add_argument("task_name", nargs="?", help="Specific task to prune")
    parser_prune.add_argument("--force", action="store_true", help="Override safety checks")
    parser_prune.add_argument(
        "--dry-run", action="store_true", help="Show actions without applying changes"
    )
    parser_prune.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    parser_prune.set_defaults(func=cmd_prune)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
