"""Git utility functions for multiclaude."""

import subprocess
from pathlib import Path


def git(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    proc = subprocess.run(["git", *cmd], capture_output=True, text=True, check=False, cwd=cwd)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def get_git_root(cwd: Path | None = None) -> Path | None:
    """Get the root of the git repository containing the current or given directory.

    Returns None if not in a git repository.
    """
    working_dir = cwd or Path.cwd()
    code, stdout, _ = git(["rev-parse", "--show-toplevel"], working_dir)
    if code == 0 and stdout:
        return Path(stdout)
    return None


def get_repo_name(repo_root: Path) -> str:
    """Get repository name from path."""
    return repo_root.name


def is_git_repo(repo_root: Path) -> bool:
    """Check if directory is a git repository."""
    return (repo_root / ".git").exists()


def branch_exists(repo_root: Path, branch_name: str) -> bool:
    """Check if branch already exists."""
    code, stdout, _ = git(["branch", "--list", branch_name], repo_root)
    return code == 0 and bool(stdout.strip())


def ref_exists(repo_root: Path, ref: str) -> bool:
    """Check if a git ref (branch/tag/commit) exists."""
    code, _, _ = git(["rev-parse", "--verify", ref], repo_root)
    return code == 0


def get_origin_remote(repo_root: Path) -> str | None:
    """Get the URL of the origin remote if it exists."""
    code, stdout, _ = git(["remote", "get-url", "origin"], repo_root)
    return stdout if code == 0 else None


def get_default_branch(repo_root: Path) -> str:
    """Get the default branch name."""
    code, stdout, _ = git(["symbolic-ref", "refs/remotes/origin/HEAD"], repo_root)
    if code == 0 and stdout:
        # refs/remotes/origin/main -> main
        return stdout.split("/")[-1]
    return "main"


def configure_clone_remotes(clone_path: Path, base_repo_path: Path) -> tuple[bool, str]:
    """Configure remotes in a cloned repository.

    Adds the origin remote from base repo and sets push.autoSetupRemote.
    Returns (success, error_message).
    """
    origin_url = get_origin_remote(base_repo_path)

    if origin_url:
        # Add origin remote pointing to the actual remote repository
        code, _, stderr = git(["remote", "add", "origin", origin_url], clone_path)
        if code != 0:
            return False, f"Failed to add origin remote: {stderr or 'unknown error'}"

    # Configure auto-setup for push
    code, _, stderr = git(["config", "push.autoSetupRemote", "true"], clone_path)
    if code != 0:
        return False, f"Failed to configure push.autoSetupRemote: {stderr or 'unknown error'}"

    return True, ""


def check_git_status(repo_path: Path) -> tuple[bool, str | None]:
    """Check if working directory is clean. Returns (is_clean, error_msg)."""
    code, stdout, stderr = git(["status", "--porcelain"], repo_path)
    if code != 0:
        return False, f"failed to inspect git status: {stderr or stdout or 'unknown error'}"
    return not stdout, "uncommitted changes present" if stdout else None


def check_unpushed_commits(repo_path: Path, branch: str) -> list[str]:
    """Check for unpushed commits. Returns list of issues."""
    issues = []

    # Check if origin exists
    code, stdout, stderr = git(["remote"], repo_path)
    if code != 0:
        return [f"failed to list git remotes: {stderr or stdout or 'unknown error'}"]
    if "origin" not in stdout.splitlines():
        return ["origin remote not configured (cannot verify pushed commits)"]

    # Check if remote branch exists and has unpushed commits
    remote_branch = f"origin/{branch}"
    if git(["rev-parse", "--verify", remote_branch], repo_path)[0] != 0:
        issues.append(f"remote branch {remote_branch} not found (unpushed commits)")
    else:
        # Check for unpushed commits
        code, stdout, stderr = git(["log", f"{remote_branch}..HEAD"], repo_path)
        if code != 0:
            issues.append(
                f"failed to compare with {remote_branch}: {stderr or stdout or 'unknown error'}"
            )
        elif stdout:
            issues.append("unpushed commits present")

    return issues


def is_branch_merged(repo_path: Path, branch: str, target: str) -> tuple[bool, str | None]:
    """Check if branch is merged into target. Returns (is_merged, error_msg)."""
    code, stdout, stderr = git(["branch", "--merged", target], repo_path)
    if code != 0:
        return False, f"failed to check merge status: {stderr or stdout or 'unknown error'}"

    merged_branches = {
        line.strip().lstrip("*").strip() for line in stdout.splitlines() if line.strip()
    }
    is_merged = branch in merged_branches
    return is_merged, None if is_merged else f"branch not merged into {target}"


def clean_working_tree(repo_path: Path) -> tuple[bool, str]:
    """Clean working tree by resetting and removing untracked files.

    Returns (success, error_message).
    """
    code, _, stderr = git(["reset", "--hard"], repo_path)
    if code != 0:
        return False, f"Failed to reset: {stderr or 'unknown error'}"

    code, _, stderr = git(["clean", "-fd"], repo_path)
    if code != 0:
        return False, f"Failed to clean: {stderr or 'unknown error'}"

    return True, ""


def fetch_all_safe(repo_path: Path) -> bool:
    """Fetch all remotes, returning True if successful."""
    code, _, _ = git(["fetch", "--all"], repo_path)
    return code == 0


def checkout_branch(
    repo_path: Path, branch: str, create: bool = False, base: str | None = None
) -> tuple[bool, str]:
    """Checkout a branch, optionally creating it from a base ref.

    Returns (success, error_message).
    """
    if create:
        cmd = ["checkout", "-b", branch]
        if base:
            cmd.append(base)
    else:
        cmd = ["checkout", branch]

    code, _, stderr = git(cmd, repo_path)
    if code != 0:
        return False, stderr or "checkout failed"
    return True, ""


def setup_branch_from_ref(repo_path: Path, branch: str, base_ref: str) -> tuple[bool, str]:
    """Setup a new branch from base ref with clean working tree.

    Returns (success, error_message).
    """
    # Clean any uncommitted changes
    success, error = clean_working_tree(repo_path)
    if not success:
        return False, f"Failed to clean working tree: {error}"

    # Fetch latest (non-critical if it fails)
    fetch_all_safe(repo_path)

    # Checkout base ref first
    success, error = checkout_branch(repo_path, base_ref, create=False)
    if not success:
        return False, f"Failed to checkout base ref '{base_ref}': {error}"

    # Create and checkout new branch
    success, error = checkout_branch(repo_path, branch, create=True)
    if not success:
        return False, f"Failed to create branch: {error}"

    return True, ""
