import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class Task:
    """Represents a multiclaude task."""

    id: str
    branch: str
    created_at: str
    status: str
    environment_path: str
    agent: str
    pruned_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """Create Task from dictionary."""
        return cls(**data)


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


def normalize_task_selectors(raw: str) -> set[str]:
    """Return possible task branch names for a user-provided selector."""

    normalized = raw.strip()
    if not normalized:
        return set()
    selectors = {normalized}
    if not normalized.startswith("mc-"):
        selectors.add(f"mc-{normalized}")
    return selectors


def evaluate_prune_candidate(task: Task, default_branch: str, force: bool) -> dict[str, Any]:
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
