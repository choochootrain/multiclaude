"""Tests for the multiclaude prune command."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from multiclaude import cli as multiclaude
from tests.conftest import configure_git_repo


def _setup_remote(repo_path: Path) -> Path:
    """Create a bare remote repository and push main to it."""
    remote_path = repo_path.parent / f"{repo_path.name}-remote.git"
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote_path)],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "main"], cwd=repo_path, check=True, capture_output=True
    )
    return remote_path


def _read_tasks(repo_path: Path) -> list[dict]:
    tasks_file = repo_path / ".multiclaude" / "tasks.json"
    return json.loads(tasks_file.read_text())


def test_prune_prunes_merged_branch(isolated_repo, capsys):
    """Prune should recycle merged clone environments and mark metadata."""
    repo_path = isolated_repo.repo_path
    _setup_remote(repo_path)

    args_init = SimpleNamespace()
    args_init.environments_dir = isolated_repo.environments_dir
    multiclaude.cmd_init(args_init)

    args_new = SimpleNamespace(branch_name="feature", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)
    capsys.readouterr()  # reset capture before prune output

    task = _read_tasks(repo_path)[0]
    env_path = Path(task["environment_path"])
    configure_git_repo(env_path)

    # Make a commit on the task branch
    feature_file = env_path / "feature.txt"
    feature_file.write_text("feature work\n")
    subprocess.run(["git", "add", "feature.txt"], cwd=env_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add feature", "--no-gpg-sign"],
        cwd=env_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", task["branch"]],
        cwd=env_path,
        check=True,
        capture_output=True,
    )

    # Merge branch into main and push main back to origin
    subprocess.run(["git", "checkout", "main"], cwd=env_path, check=True, capture_output=True)
    subprocess.run(["git", "pull", "origin", "main"], cwd=env_path, check=True, capture_output=True)
    subprocess.run(["git", "merge", task["branch"]], cwd=env_path, check=True, capture_output=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=env_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "checkout", task["branch"]], cwd=env_path, check=True, capture_output=True
    )

    args_prune = SimpleNamespace(task_name=None, force=False, dry_run=False, yes=True)
    multiclaude.cmd_prune(args_prune)

    captured = capsys.readouterr()
    assert "Pruned task" in captured.out

    updated_task = _read_tasks(repo_path)[0]
    assert updated_task["status"] == "pruned"
    assert updated_task["pruned_at"] is not None

    assert not env_path.exists()
    recycled = [p for p in env_path.parent.iterdir() if p.name.startswith("avail-")]
    assert recycled, "Expected cloned environment to be recycled"


def test_prune_skips_unmerged_branch(isolated_repo, capsys):
    """Prune should skip branches that have not been merged yet."""
    repo_path = isolated_repo.repo_path
    _setup_remote(repo_path)

    args_init = SimpleNamespace()
    args_init.environments_dir = isolated_repo.environments_dir
    multiclaude.cmd_init(args_init)

    args_new = SimpleNamespace(branch_name="wip", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)
    capsys.readouterr()

    task = _read_tasks(repo_path)[0]
    env_path = Path(task["environment_path"])
    configure_git_repo(env_path)

    # Create commit and push branch but do NOT merge
    work_file = env_path / "work.txt"
    work_file.write_text("still working\n")
    subprocess.run(["git", "add", "work.txt"], cwd=env_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "WIP", "--no-gpg-sign"],
        cwd=env_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", task["branch"]],
        cwd=env_path,
        check=True,
        capture_output=True,
    )

    args_prune = SimpleNamespace(task_name=None, force=False, dry_run=False, yes=True)
    multiclaude.cmd_prune(args_prune)

    captured = capsys.readouterr()
    assert "Skipping" in captured.out
    assert "not merged" in captured.out

    updated_task = _read_tasks(repo_path)[0]
    assert updated_task["status"] == "active"
    assert Path(updated_task["environment_path"]).exists()


def test_prune_force_removes_dirty_environment(isolated_repo, capsys):
    """--force should prune even when safeguards would normally block it."""
    repo_path = isolated_repo.repo_path
    _setup_remote(repo_path)

    args_init = SimpleNamespace()
    args_init.environments_dir = isolated_repo.environments_dir
    multiclaude.cmd_init(args_init)

    args_new = SimpleNamespace(branch_name="cleanup", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)
    capsys.readouterr()

    task = _read_tasks(repo_path)[0]
    env_path = Path(task["environment_path"])
    configure_git_repo(env_path)

    # Commit and push branch so remote tracking exists
    ready_file = env_path / "ready.txt"
    ready_file.write_text("ready\n")
    subprocess.run(["git", "add", "ready.txt"], cwd=env_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Prep", "--no-gpg-sign"],
        cwd=env_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", task["branch"]],
        cwd=env_path,
        check=True,
        capture_output=True,
    )

    # Introduce dirty state
    dirty_file = env_path / "dirty.txt"
    dirty_file.write_text("dirty\n")

    args_prune = SimpleNamespace(task_name=None, force=False, dry_run=False, yes=True)
    multiclaude.cmd_prune(args_prune)
    captured = capsys.readouterr()
    assert "Skipping" in captured.out
    assert "uncommitted" in captured.out

    # Force prune
    force_args = SimpleNamespace(task_name=None, force=True, dry_run=False, yes=True)
    multiclaude.cmd_prune(force_args)
    captured = capsys.readouterr()
    assert "Force pruning" in captured.out

    updated_task = _read_tasks(repo_path)[0]
    assert updated_task["status"] == "pruned"
    assert not Path(task["environment_path"]).exists()


def test_prune_dry_run_does_not_change_state(isolated_repo, capsys):
    """Dry run should report actions without modifying environments or tasks."""
    repo_path = isolated_repo.repo_path
    _setup_remote(repo_path)

    args_init = SimpleNamespace()
    args_init.environments_dir = isolated_repo.environments_dir
    multiclaude.cmd_init(args_init)

    args_new = SimpleNamespace(branch_name="dryrun", no_launch=True, base="main", agent=None)
    multiclaude.cmd_new(args_new)
    capsys.readouterr()

    task = _read_tasks(repo_path)[0]
    env_path = Path(task["environment_path"])
    configure_git_repo(env_path)

    # Make commit, merge, push like in first test
    artifact = env_path / "artifact.txt"
    artifact.write_text("done\n")
    subprocess.run(["git", "add", "artifact.txt"], cwd=env_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Done", "--no-gpg-sign"],
        cwd=env_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", task["branch"]],
        cwd=env_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "checkout", "main"], cwd=env_path, check=True, capture_output=True)
    subprocess.run(["git", "pull", "origin", "main"], cwd=env_path, check=True, capture_output=True)
    subprocess.run(["git", "merge", task["branch"]], cwd=env_path, check=True, capture_output=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=env_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "checkout", task["branch"]], cwd=env_path, check=True, capture_output=True
    )

    dry_args = SimpleNamespace(task_name=None, force=False, dry_run=True, yes=True)
    multiclaude.cmd_prune(dry_args)

    captured = capsys.readouterr()
    assert "Dry run" in captured.out
    assert "would prune" in captured.out

    updated_task = _read_tasks(repo_path)[0]
    assert updated_task["status"] == "active"
    assert updated_task["pruned_at"] is None
    assert env_path.exists()
