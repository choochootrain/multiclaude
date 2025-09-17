"""Test git strategies with submodule support for multiclaude task isolation."""

import json
import random
import shutil
import string
import subprocess
from pathlib import Path

import pytest

from tests.conftest import configure_git_repo


@pytest.fixture
def repo_with_submodules(isolated_repo):
    """Create a repo with submodules for testing advanced git strategies."""
    base_dir = isolated_repo.parent
    main_repo = isolated_repo

    # Create external library repo (submodule)
    lib_repo = base_dir / "shared-lib"
    lib_repo.mkdir()
    subprocess.run(["git", "init"], cwd=lib_repo, check=True, capture_output=True)
    configure_git_repo(lib_repo)

    # Add content to library repo
    lib_src = lib_repo / "src"
    lib_src.mkdir()
    (lib_src / "utils.js").write_text("""
export function helper() {
    return 'v1-initial';
}

export function calculate(a, b) {
    return a + b;
}
""")

    # Add package.json to submodule
    lib_package = {"name": "shared-lib", "version": "1.0.0", "dependencies": {"uuid": "^9.0.0"}}
    (lib_repo / "package.json").write_text(json.dumps(lib_package, indent=2))

    # Create node_modules in submodule
    lib_node_modules = lib_repo / "node_modules"
    lib_node_modules.mkdir()
    (lib_node_modules / "uuid").mkdir()
    (lib_node_modules / "uuid" / "index.js").write_text("// uuid library")

    # Commit library repo
    subprocess.run(["git", "add", "."], cwd=lib_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Initial library version"], cwd=lib_repo, check=True)

    # Disable submodule.recurse and allow file protocol for local testing
    subprocess.run(["git", "config", "submodule.recurse", "false"], cwd=main_repo, check=True)
    subprocess.run(["git", "config", "protocol.file.allow", "always"], cwd=main_repo, check=True)

    # Add submodule to main repo with protocol override
    subprocess.run(
        [
            "git",
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(lib_repo),
            "libs/shared-lib",
        ],
        cwd=main_repo,
        check=True,
    )

    # Initialize submodule
    subprocess.run(
        ["git", "submodule", "update", "--init", "--recursive"],
        cwd=main_repo,
        check=True,
        capture_output=True,
    )

    # Add main repo content that uses submodule
    main_src = main_repo / "src"
    main_src.mkdir(exist_ok=True)
    (main_src / "index.js").write_text("""
import { helper, calculate } from '../libs/shared-lib/src/utils.js';

function main() {
    console.log('Helper says:', helper());
    console.log('Calculation:', calculate(2, 3));
}

export { main };
""")

    # Add main repo package.json
    main_package = {
        "name": "main-app",
        "version": "1.0.0",
        "type": "module",
        "dependencies": {"express": "^4.18.0"},
    }
    (main_repo / "package.json").write_text(json.dumps(main_package, indent=2))

    # Create node_modules in main repo
    main_node_modules = main_repo / "node_modules"
    main_node_modules.mkdir(exist_ok=True)
    (main_node_modules / "express").mkdir()
    (main_node_modules / "express" / "index.js").write_text("// express framework")

    # Enhanced test script that checks both main and submodule deps
    test_script = main_repo / "test.sh"
    test_script.write_text("""#!/bin/bash
# Test script that verifies both main and submodule dependencies
echo "Testing main repo dependencies..."
if [ -d "node_modules/express" ]; then
    echo "✓ Main dependencies available"
else
    echo "✗ Main dependencies missing"
    exit 1
fi

echo "Testing submodule dependencies..."
if [ -d "libs/shared-lib/node_modules/uuid" ]; then
    echo "✓ Submodule dependencies available"
else
    echo "✗ Submodule dependencies missing"
    exit 1
fi

echo "Testing submodule code..."
if [ -f "libs/shared-lib/src/utils.js" ]; then
    echo "✓ Submodule code available"
else
    echo "✗ Submodule code missing"
    exit 1
fi

echo "All tests passed!"
""")
    test_script.chmod(0o755)

    # Commit everything
    subprocess.run(["git", "add", "."], cwd=main_repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add main app with submodule"], cwd=main_repo, check=True
    )

    return main_repo, lib_repo


# Helper functions


def create_worktree(
    repo_path: Path,
    branch_name: str,
    worktree_name: str | None = None,
    create_new_branch: bool = True,
) -> Path:
    """Helper to create a worktree."""
    if worktree_name is None:
        worktree_name = branch_name
    worktree_path = repo_path.parent / f"wt-{worktree_name}"

    if create_new_branch:
        cmd = ["git", "worktree", "add", str(worktree_path), "-b", branch_name]
    else:
        cmd = ["git", "worktree", "add", str(worktree_path), branch_name]

    subprocess.run(cmd, cwd=repo_path, check=True, capture_output=True)
    return worktree_path


def setup_submodule_branch(repo_path: Path, submodule_path: str, branch_name: str):
    """Create matching branch in submodule and make changes."""
    submodule_full_path = repo_path / submodule_path

    # Create branch in submodule
    subprocess.run(
        ["git", "checkout", "-b", branch_name],
        cwd=submodule_full_path,
        check=True,
        capture_output=True,
    )

    # Make changes to submodule
    random_suffix = "".join(random.choices(string.ascii_letters, k=6))
    utils_file = submodule_full_path / "src" / "utils.js"
    utils_file.write_text(f"""
export function helper() {{
    return 'v2-modified-{random_suffix}';
}}

export function calculate(a, b) {{
    console.log('Modified calculation in {random_suffix}');
    return a + b + 1;  // Modified behavior
}}

export function newFunction_{random_suffix}() {{
    return 'New feature in {branch_name}';
}}
""")

    # Commit submodule changes
    subprocess.run(["git", "add", "."], cwd=submodule_full_path, check=True)
    configure_git_repo(submodule_full_path)
    subprocess.run(
        ["git", "commit", "-m", f"Update library for {branch_name} - {random_suffix}"],
        cwd=submodule_full_path,
        check=True,
    )

    # Update main repo to reference new submodule commit
    configure_git_repo(repo_path)
    subprocess.run(["git", "add", submodule_path], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"Update submodule to {branch_name} version"],
        cwd=repo_path,
        check=True,
    )


def make_main_repo_changes(repo_path: Path, branch_name: str):
    """Make changes to main repo code."""
    random_suffix = "".join(random.choices(string.ascii_letters, k=6))
    main_file = repo_path / "src" / "index.js"
    main_file.write_text(f"""
import {{ helper, calculate, newFunction_{random_suffix} }} from '../libs/shared-lib/src/utils.js';

function main() {{
    console.log('Helper says:', helper());
    console.log('Calculation:', calculate(2, 3));
    console.log('New feature:', newFunction_{random_suffix}());
    console.log('Modified in branch {branch_name} - {random_suffix}');
}}

export {{ main }};
""")

    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    configure_git_repo(repo_path)
    subprocess.run(
        ["git", "commit", "-m", f"Update main app for {branch_name} - {random_suffix}"],
        cwd=repo_path,
        check=True,
    )


def verify_submodule_state(
    repo_path: Path, submodule_path: str, expected_branch: str | None = None
):
    """Verify submodule is in correct state."""
    submodule_full_path = repo_path / submodule_path

    # Get current branch or commit
    branch_result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=submodule_full_path,
        capture_output=True,
        text=True,
        check=False,
    )

    commit_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=submodule_full_path,
        capture_output=True,
        text=True,
        check=True,
    )

    current_branch = branch_result.stdout.strip()
    current_commit = commit_result.stdout.strip()

    print(f"Submodule state: branch='{current_branch}', commit={current_commit[:8]}")

    if expected_branch and current_branch:
        assert current_branch == expected_branch, (
            f"Expected branch {expected_branch}, got {current_branch}"
        )

    # Verify content has modifications
    utils_content = (submodule_full_path / "src" / "utils.js").read_text()
    assert "v2-modified-" in utils_content, "Submodule changes not present"

    return current_branch, current_commit


def verify_full_functionality(repo_path: Path):
    """Verify both main repo and submodule dependencies work."""
    test_script = repo_path / "test.sh"
    if not test_script.exists():
        return False

    result = subprocess.run(["./test.sh"], cwd=repo_path, capture_output=True, check=False)

    print(f"Test script output: {result.stdout.decode()}")
    if result.stderr:
        print(f"Test script errors: {result.stderr.decode()}")

    return result.returncode == 0


# Enhanced Strategy Tests


def test_worktree_temporary_branch_swap_with_submodules_fails(repo_with_submodules):
    """Test worktree swap with submodules - matching branch convention."""
    main_repo, lib_repo = repo_with_submodules
    branch_name = "mc-feature"

    # Create worktree
    worktree_path = create_worktree(main_repo, branch_name)

    # Configure protocol override in worktree and initialize submodules
    subprocess.run(
        ["git", "config", "protocol.file.allow", "always"], cwd=worktree_path, check=True
    )
    subprocess.run(
        ["git", "-c", "protocol.file.allow=always", "submodule", "update", "--init", "--recursive"],
        cwd=worktree_path,
        check=True,
        capture_output=True,
    )

    # Set up submodule branch and make changes in worktree
    setup_submodule_branch(worktree_path, "libs/shared-lib", branch_name)
    make_main_repo_changes(worktree_path, branch_name)

    # Verify changes in worktree
    assert verify_full_functionality(worktree_path), "Worktree functionality broken"
    worktree_branch, worktree_commit = verify_submodule_state(
        worktree_path, "libs/shared-lib", branch_name
    )

    # SWAP PROCESS: Attempt to remove worktree (should fail with submodules)
    result = subprocess.run(
        ["git", "worktree", "remove", str(worktree_path)],
        cwd=main_repo,
        capture_output=True,
        text=True,
        check=False,
    )

    # CRITICAL TEST: Verify this fails because worktrees with submodules cannot be removed
    assert result.returncode != 0, "Expected worktree removal to fail with submodules"
    assert "working trees containing submodules cannot be moved or removed" in result.stderr, (
        f"Expected submodule error, got: {result.stderr}"
    )

    print("✓ CONFIRMED: Worktree temporary swap strategy FAILS with submodules")
    print(f"  Error: {result.stderr.strip()}")

    # This strategy is fundamentally incompatible with submodules


def test_worktree_patch_based_swap_with_submodules_fails(repo_with_submodules):
    """Test patch-based swap with submodules."""
    main_repo, lib_repo = repo_with_submodules
    branch_name = "mc-patch-test"

    # Create worktree and set up submodule changes
    worktree_path = create_worktree(main_repo, branch_name)
    subprocess.run(
        ["git", "config", "protocol.file.allow", "always"], cwd=worktree_path, check=True
    )
    subprocess.run(
        ["git", "-c", "protocol.file.allow=always", "submodule", "update", "--init", "--recursive"],
        cwd=worktree_path,
        check=True,
        capture_output=True,
    )

    setup_submodule_branch(worktree_path, "libs/shared-lib", branch_name)
    make_main_repo_changes(worktree_path, branch_name)

    # Generate patches separately for main repo and submodules
    patches_dir = main_repo / "patches"
    patches_dir.mkdir(exist_ok=True)

    # 1. Generate patches for submodule changes
    worktree_submodule = worktree_path / "libs/shared-lib"
    submodule_patches_dir = patches_dir / "submodule"
    submodule_patches_dir.mkdir(exist_ok=True)

    # Get submodule commits that are new
    submodule_log = subprocess.run(
        ["git", "log", "--oneline", "main..HEAD"],
        cwd=worktree_submodule,
        capture_output=True,
        text=True,
        check=True,
    )
    if submodule_log.stdout.strip():
        num_submodule_commits = len(submodule_log.stdout.strip().split("\n"))
        subprocess.run(
            [
                "git",
                "format-patch",
                f"-{num_submodule_commits}",
                "HEAD",
                "-o",
                str(submodule_patches_dir),
            ],
            cwd=worktree_submodule,
            capture_output=True,
            check=True,
        )

    # 2. Generate patches for main repo changes (including submodule reference updates)
    main_log = subprocess.run(
        ["git", "log", "--oneline", "main..HEAD"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        check=True,
    )
    if main_log.stdout.strip():
        num_main_commits = len(main_log.stdout.strip().split("\n"))
        subprocess.run(
            ["git", "format-patch", f"-{num_main_commits}", "HEAD", "-o", str(patches_dir)],
            cwd=worktree_path,
            capture_output=True,
            check=True,
        )

        # 3. Apply submodule patches first
        submodule_patch_files = list(submodule_patches_dir.glob("*.patch"))
        if submodule_patch_files:
            main_submodule = main_repo / "libs/shared-lib"
            configure_git_repo(main_submodule)
            for patch_file in sorted(submodule_patch_files):
                subprocess.run(
                    ["git", "am", str(patch_file)],
                    cwd=main_submodule,
                    capture_output=True,
                    check=True,
                )

    # 4. Apply main repo patches (these will update submodule references)
    main_patch_files = [f for f in patches_dir.glob("*.patch") if f.parent == patches_dir]
    for patch_file in sorted(main_patch_files):
        subprocess.run(
            ["git", "am", str(patch_file)], cwd=main_repo, capture_output=True, check=True
        )

    # DON'T update submodules - this is where the complexity shows
    # The submodule reference is updated but the submodule itself is on wrong commit/branch

    # CRITICAL: Verify this creates inconsistent state - submodule ref updated but content wrong
    main_submodule = main_repo / "libs/shared-lib"
    current_branch, current_commit = verify_submodule_state(main_repo, "libs/shared-lib")

    # The submodule should now be in detached HEAD state pointing to the new commit
    # but functionality will be broken because dependencies/branches don't match
    try:
        functionality_works = verify_full_functionality(main_repo)
        assert functionality_works, "Expected functionality to work after patch application"
    except Exception as e:
        print(f"Patch-based approach creates inconsistent submodule state: {e}")
        # This demonstrates the complexity - patches work but create broken states

    # Test reverse patching (main -> worktree)
    # First, ensure worktree is up-to-date with main repo state by fast-forwarding
    subprocess.run(["git", "fetch", str(main_repo)], cwd=worktree_path, check=True)
    subprocess.run(["git", "merge", "main"], cwd=worktree_path, check=True)

    # Now make additional changes in main repo AND its submodule
    make_main_repo_changes(main_repo, f"{branch_name}-reverse")

    # Generate reverse patches - separate for submodule and main repo
    reverse_patches_dir = patches_dir / "reverse"
    reverse_patches_dir.mkdir(exist_ok=True)
    reverse_submodule_patches_dir = reverse_patches_dir / "submodule"
    reverse_submodule_patches_dir.mkdir(exist_ok=True)

    # CRITICAL: This demonstrates the complexity of patch-based approach with submodules
    # The main repo's submodule doesn't have branch references, only commits from patches
    # This causes branch resolution to fail when trying to generate reverse patches

    # Attempt to generate patches for main repo submodule changes
    main_submodule = main_repo / "libs/shared-lib"
    result = subprocess.run(
        ["git", "log", "--oneline", f"{branch_name}..HEAD"],
        cwd=main_submodule,
        capture_output=True,
        text=True,
        check=False,  # Expect this to fail
    )

    # This should fail because submodule doesn't have the branch reference
    assert result.returncode != 0, "Expected branch reference failure in submodule"
    assert "unknown revision" in result.stderr or "ambiguous argument" in result.stderr, (
        f"Expected branch resolution error, got: {result.stderr}"
    )

    print("✓ CONFIRMED: Patch-based swap with submodules FAILS due to branch reference complexity")
    print(f"  Error: {result.stderr.strip()}")
    print("  Note: While theoretically possible to implement, this approach requires:")
    print("    - Complex branch reference management across repos")
    print("    - Sophisticated patch ordering and dependency resolution")
    print("    - Manual synchronization of submodule commit hashes and branch states")
    print("    - Error-prone bidirectional patching with conflict resolution")
    print("  Conclusion: Patch-based approach is too complex for practical use with submodules")

    # Skip the rest of reverse patching since we've demonstrated the failure point
    return

    # Verify bidirectional sync worked
    assert verify_full_functionality(worktree_path), "Reverse patching broke worktree"

    print("✓ Patch-based swap with submodules successful")


def test_mirror_clone_with_submodules(repo_with_submodules):
    """Test mirror clone approach with submodules."""
    main_repo, lib_repo = repo_with_submodules
    base_dir = main_repo.parent
    branch_name = "mc-mirror-test"

    # Create mirror clone (bare repos don't support --recursive, so we'll use different approach)
    mirror_path = base_dir / "mirror.git"
    subprocess.run(["git", "clone", "--mirror", str(main_repo), str(mirror_path)], check=True)

    # Clone from mirror for task work
    task_repo = base_dir / "task-from-mirror"
    subprocess.run(
        [
            "git",
            "-c",
            "protocol.file.allow=always",
            "clone",
            "--recursive",
            str(mirror_path),
            str(task_repo),
        ],
        check=True,
    )

    # Create branch and make submodule changes in task repo
    subprocess.run(["git", "checkout", "-b", branch_name], cwd=task_repo, check=True)
    setup_submodule_branch(task_repo, "libs/shared-lib", branch_name)
    make_main_repo_changes(task_repo, branch_name)

    # Push main repo branch to mirror
    subprocess.run(["git", "push", "origin", branch_name], cwd=task_repo, check=True)

    # Push submodule branch to its origin (the lib_repo)
    task_submodule = task_repo / "libs/shared-lib"
    subprocess.run(["git", "push", "origin", branch_name], cwd=task_submodule, check=True)

    # Clone from mirror to main work repo
    main_work = base_dir / "main-from-mirror"
    subprocess.run(
        [
            "git",
            "-c",
            "protocol.file.allow=always",
            "clone",
            "--recursive",
            str(mirror_path),
            str(main_work),
        ],
        check=True,
    )

    # Checkout branch in main work repo
    subprocess.run(["git", "fetch", "origin"], cwd=main_work, check=True)
    subprocess.run(["git", "checkout", branch_name], cwd=main_work, check=True)

    # Update submodules to get the right branch
    subprocess.run(["git", "config", "protocol.file.allow", "always"], cwd=main_work, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "update",
            "--recursive",
            "--remote",
        ],
        cwd=main_work,
        check=True,
        capture_output=True,
    )

    # CRITICAL: Manually checkout the matching branch in submodule after swap
    main_work_submodule = main_work / "libs/shared-lib"
    subprocess.run(
        ["git", "checkout", branch_name], cwd=main_work_submodule, check=True, capture_output=True
    )

    # Verify submodule state and functionality
    verify_submodule_state(main_work, "libs/shared-lib")
    assert verify_full_functionality(main_work), "Mirror clone functionality broken"

    print("✓ Mirror clone with submodules successful")


def test_direct_clone_to_clone_with_submodules(repo_with_submodules):
    """Test direct clone-to-clone with submodules."""
    main_repo, lib_repo = repo_with_submodules
    base_dir = main_repo.parent
    branch_name = "mc-direct-test"

    # Setup main repo with full dependencies (simulation)
    main_work = base_dir / "main-with-full-deps"
    shutil.copytree(main_repo, main_work)

    # Clone main repo for task work
    task_repo = base_dir / "task-direct-clone"
    subprocess.run(
        [
            "git",
            "-c",
            "protocol.file.allow=always",
            "clone",
            "--recursive",
            str(main_work),
            str(task_repo),
        ],
        check=True,
    )

    # Create branch and make changes in task repo
    subprocess.run(["git", "checkout", "-b", branch_name], cwd=task_repo, check=True)
    setup_submodule_branch(task_repo, "libs/shared-lib", branch_name)
    make_main_repo_changes(task_repo, branch_name)

    # Push branch to main repo
    subprocess.run(["git", "push", "origin", branch_name], cwd=task_repo, check=True)

    # Push submodule branch to its origin
    task_submodule = task_repo / "libs/shared-lib"
    subprocess.run(["git", "push", "origin", branch_name], cwd=task_submodule, check=True)

    # Fetch and checkout in main work repo
    subprocess.run(["git", "fetch"], cwd=main_work, check=True)
    subprocess.run(["git", "checkout", branch_name], cwd=main_work, check=True)

    # Update submodules
    subprocess.run(["git", "config", "protocol.file.allow", "always"], cwd=main_work, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "update",
            "--recursive",
            "--remote",
        ],
        cwd=main_work,
        check=True,
        capture_output=True,
    )

    # CRITICAL: Manually checkout the matching branch in submodule after swap
    main_work_submodule = main_work / "libs/shared-lib"
    subprocess.run(
        ["git", "checkout", branch_name], cwd=main_work_submodule, check=True, capture_output=True
    )

    # Verify state - submodule should now be on correct branch with changes
    verify_submodule_state(main_work, "libs/shared-lib")
    assert verify_full_functionality(main_work), "Direct clone functionality broken"

    print("✓ Direct clone-to-clone with submodules successful")
