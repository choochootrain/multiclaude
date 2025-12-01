import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .git_utils import check_git_status, check_unpushed_commits, git, is_branch_merged

if TYPE_CHECKING:
    from .config import Config


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


def _get_tasks_file(config: "Config") -> Path:
    """Get path to tasks file."""
    return config.repo_root / ".multiclaude" / "tasks.json"


def initialize_tasks(config: "Config") -> None:
    """Initialize tasks file."""
    tasks_file = _get_tasks_file(config)
    tasks_file.write_text("[]")


def load_tasks(config: "Config") -> list[Task]:
    """Load all tasks."""
    tasks_file = _get_tasks_file(config)
    if not tasks_file.exists():
        return []
    data = json.loads(tasks_file.read_text())
    return [Task(**task) for task in data]


def save_tasks(config: "Config", tasks: list[Task]) -> None:
    """Save tasks to file."""
    tasks_file = _get_tasks_file(config)
    tasks_file.write_text(json.dumps([asdict(t) for t in tasks], indent=2))


def create_task(
    config: "Config", branch_name: str, environment_path: Path, agent_name: str
) -> Task:
    """Create and add a new task."""
    task = Task(
        id=branch_name,
        branch=branch_name,
        created_at=datetime.now().isoformat(),
        status="active",
        environment_path=str(environment_path),
        agent=agent_name,
    )
    tasks = load_tasks(config)
    tasks.append(task)
    save_tasks(config, tasks)
    return task


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

    # Handle missing environment
    if not env_path.exists():
        return {
            "prune": True,
            "reason": "Environment directory missing (stale metadata)",
            "issues": [],
            "warnings": [],
            "env_exists": False,
            "cleanup_only": True,
        }

    # Skip all safety checks when force is enabled
    if force:
        return _prune_result(True, f"Force pruning {task.branch}", [], [])

    issues = []
    warnings: list[str] = []

    # Check working directory
    is_clean, msg = check_git_status(env_path)
    if msg:
        issues.append(msg)
        if not is_clean and not force:
            return _prune_result(False, msg, issues, warnings)

    # Check unpushed commits
    issues.extend(check_unpushed_commits(env_path, task.branch))

    # Fetch latest (non-blocking)
    if git(["fetch", "origin", task.branch], env_path)[0] != 0:
        warnings.append(f"git fetch origin {task.branch} failed")

    # Check merge status
    is_merged, msg = is_branch_merged(env_path, task.branch, default_branch)
    if msg:
        issues.append(msg)

    # Make prune decision
    if not issues and is_merged:
        return _prune_result(True, f"Branch merged into {default_branch}", issues, warnings)

    return _prune_result(
        False, issues[0] if issues else "No safe prune condition met", issues, warnings
    )


def _prune_result(
    prune: bool, reason: str, issues: list[str], warnings: list[str]
) -> dict[str, str | bool | list[str]]:
    """Create prune result dict."""
    return {
        "prune": prune,
        "reason": reason,
        "issues": issues,
        "warnings": warnings,
        "env_exists": True,
        "cleanup_only": False,
    }


def find_task_by_selector(config: "Config", selector: str) -> Task:
    """Find a task by name/ID selector.

    Supports partial matching (e.g., 'feature' matches 'mc-feature').
    Raises MultiClaudeError if no match or multiple matches found.
    """
    from .errors import MultiClaudeError  # noqa: PLC0415

    tasks = load_tasks(config)
    if not tasks:
        raise MultiClaudeError("No tasks found. Create one with 'multiclaude new'.")

    # Get possible selectors (handles mc- prefix)
    selectors = normalize_task_selectors(selector)

    # Find matching tasks (exclude pruned)
    matches = [
        task
        for task in tasks
        if (task.branch in selectors or task.id in selectors) and task.status != "pruned"
    ]

    if not matches:
        raise MultiClaudeError(f"No task found matching '{selector}'.")

    if len(matches) > 1:
        branch_list = ", ".join(t.branch for t in matches)
        raise MultiClaudeError(
            f"Multiple tasks match '{selector}': {branch_list}. Please be more specific."
        )

    return matches[0]
