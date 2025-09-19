#!/usr/bin/env python3
"""Multiclaude - CLI tool for managing parallel Claude Code instances with git worktrees."""

import argparse
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import (
    Config,
    config_exists,
    get_config_value,
    initialize_config,
    load_config,
    set_config_value,
)
from .errors import MultiClaudeError, NotInitializedError
from .git_utils import branch_exists, is_git_repo, ref_exists
from .strategies import get_strategy
from .tasks import (
    Task,
    create_task,
    evaluate_prune_candidate,
    initialize_tasks,
    load_tasks,
    normalize_task_selectors,
    save_tasks,
)


def exit_with_error(msg: str) -> None:
    """Print error message and exit."""
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def print_success(msg: str) -> None:
    """Print success message with checkmark."""
    print(f"✓ {msg}")


def get_version() -> str:
    """Get the multiclaude version."""

    try:
        return importlib.metadata.version("multiclaude")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def validate_config() -> Config:
    try:
        repo_root = Path.cwd()
        return load_config(repo_root)
    except NotInitializedError as e:
        exit_with_error(str(e))


def cmd_init(args: argparse.Namespace) -> None:
    """Initialize multiclaude in current repository."""
    repo_root = Path.cwd()

    if not is_git_repo(repo_root):
        exit_with_error("Not a git repository. Please run this command in a git repo.")

    if config_exists(repo_root):
        print("Multiclaude already initialized in this repository.")
        return

    # Initialize config and tasks
    config = initialize_config(repo_root, environments_dir=getattr(args, "environments_dir", None))
    initialize_tasks(config)

    print_success("Initialized multiclaude in this repository")
    print_success("Created .multiclaude/ directory")
    print_success("Added .multiclaude to .git/info/exclude")


def cmd_new(args: argparse.Namespace) -> None:
    """Create new task with isolated environment and launch Claude."""

    config = validate_config()
    strategy = get_strategy(config)

    agent_name = (args.agent if args.agent is not None else config.default_agent).strip()
    if not agent_name:
        exit_with_error(
            "Agent name cannot be empty. Provide a command with --agent or set default_agent in .multiclaude/config.json."
        )

    agent_path = shutil.which(agent_name)
    if agent_path is None:
        exit_with_error(
            f"Agent '{agent_name}' not found on PATH. Install it or update --agent/default_agent to a valid command."
        )

    branch_name = f"mc-{args.branch_name}"

    if branch_exists(config.repo_root, branch_name):
        exit_with_error(f"Branch '{branch_name}' already exists.")

    # Validate base ref exists
    if not ref_exists(config.repo_root, args.base):
        exit_with_error(f"Base ref '{args.base}' does not exist.")

    print(
        f"Creating new isolated environment for '{branch_name}' from '{args.base}' using strategy: {strategy.name} (agent: {agent_name})"
    )

    try:
        environment_path, was_reused = strategy.create(
            config.repo_root, branch_name, base_ref=args.base
        )
    except MultiClaudeError as e:
        exit_with_error(str(e))

    # Add task to tasks.json
    create_task(config, branch_name, environment_path, agent_name)

    if was_reused:
        print_success(
            f"Reused existing environment for branch '{branch_name}' at {environment_path}"
        )
    else:
        print_success(f"Created new environment for branch '{branch_name}' at {environment_path}")

    if not args.no_launch:
        print(f"Launching {agent_name} in {environment_path}...")
        os.chdir(environment_path)
        subprocess.run([agent_name], check=False)
    else:
        print(f"To start working, run: cd {environment_path}")


def cmd_list(args: argparse.Namespace) -> None:
    """List all multiclaude tasks."""

    config = validate_config()
    tasks = load_tasks(config)

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

    config = validate_config()

    default_branch = config.default_branch
    strategy = get_strategy(config)

    tasks = load_tasks(config)
    if not tasks:
        print("No multiclaude tasks found.")
        return

    if args.task_name:
        selectors = normalize_task_selectors(args.task_name)
        tasks_to_consider = [
            task for task in tasks if task.branch in selectors or task.id in selectors
        ]
        if not tasks_to_consider:
            exit_with_error(f"No task found matching '{args.task_name}'.")
    else:
        tasks_to_consider = tasks

    prune_candidates: list[tuple[Task, dict[str, Any]]] = []

    for task in tasks_to_consider:
        if task.status == "pruned":
            print(f"Skipping {task.branch}: already pruned")
            continue

        evaluation = evaluate_prune_candidate(task, default_branch, args.force)

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
        save_tasks(config, tasks)


def cmd_config(args: argparse.Namespace) -> None:
    """Get or set configuration values."""

    config = validate_config()

    if args.write is not None:
        # Write mode
        try:
            config = set_config_value(config, args.path, args.write)
            print(f"Set {args.path} = {args.write}")
        except MultiClaudeError as e:
            exit_with_error(str(e))
    else:
        # Read mode
        try:
            value = get_config_value(config, args.path)
            if value is None:
                print(f"{args.path} is not set")
            else:
                if isinstance(value, dict | list):
                    # Pretty print complex values
                    print(json.dumps(value, indent=2))
                else:
                    print(value)
        except MultiClaudeError as e:
            exit_with_error(str(e))


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Multiclaude - Manage parallel Claude Code instances with isolated environments"
    )
    parser.add_argument("--version", action="version", version=f"multiclaude {get_version()}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init command
    parser_init = subparsers.add_parser("init", help="Initialize multiclaude in current repository")
    parser_init.add_argument(
        "--environments-dir",
        type=Path,
        help="Directory to store environments (default: ~/multiclaude-environments)",
    )
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

    # config command
    parser_config = subparsers.add_parser("config", help="Get or set configuration values")
    parser_config.add_argument("path", help="Configuration path (e.g., environments_dir)")
    parser_config.add_argument("--write", help="Value to write to the configuration path")
    parser_config.set_defaults(func=cmd_config)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
