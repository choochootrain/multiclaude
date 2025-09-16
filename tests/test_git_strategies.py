"""Test various git strategies for multiclaude task isolation."""

import json
import os
import random
import shutil
import string
import subprocess
from pathlib import Path

import pytest

from tests.conftest import configure_git_repo

# Helper fixture for complex repo with dependencies


@pytest.fixture
def repo_with_deps(isolated_repo):
    """Create a repo with simulated dependencies and tooling."""
    repo_path = isolated_repo

    # Add package.json for Node.js simulation
    package_json = {
        "name": "test-project",
        "version": "1.0.0",
        "dependencies": {"lodash": "^4.17.21"},
        "devDependencies": {"vitest": "^0.34.0"},
        "scripts": {"test": "vitest", "test:run": "vitest run"},
    }
    (repo_path / "package.json").write_text(json.dumps(package_json, indent=2))

    # Create node_modules directory (simulated)
    node_modules = repo_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "lodash").mkdir()
    (node_modules / "lodash" / "index.js").write_text("// lodash")
    (node_modules / "vitest").mkdir()
    (node_modules / "vitest" / "index.js").write_text("// vitest")

    # Add Python requirements
    (repo_path / "requirements.txt").write_text("requests==2.28.0\npytest==7.4.0\n")

    # Add vitest config
    vitest_config = """
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
  },
});
"""
    (repo_path / "vitest.config.js").write_text(vitest_config)

    # Add a dummy test
    test_dir = repo_path / "tests"
    test_dir.mkdir()
    test_file = test_dir / "example.test.js"
    test_file.write_text("""
describe('Example Test', () => {
  it('should pass', () => {
    expect(1 + 1).toBe(2);
  });
});
""")

    # Create test.sh script that simulates running tests
    test_script = repo_path / "test.sh"
    test_script.write_text("""#!/bin/bash
# Simulate test run - check if node_modules exists
if [ -d "node_modules/vitest" ]; then
    echo "Running tests..."
    echo "All tests passed!"
    exit 0
else
    echo "Error: Dependencies not installed. Run npm install first."
    exit 1
fi
""")
    test_script.chmod(0o755)

    # Create src directory with some code
    src_dir = repo_path / "src"
    src_dir.mkdir()
    (src_dir / "index.js").write_text("""
function add(a, b) {
    return a + b;
}

module.exports = { add };
""")

    # Commit everything
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add dependencies and test infrastructure"],
        cwd=repo_path,
        check=True,
    )

    return repo_path


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


def measure_disk_usage(path: Path) -> int:
    """Measure disk usage of a directory in bytes."""
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.islink(fp):
                continue
            total += os.path.getsize(fp)
    return total


def make_test_changes(repo_path: Path, filename: str = "src/index.js"):
    """Make a test change that could conflict with other changes."""
    configure_git_repo(repo_path)
    # Generate random changes to simulate real conflicts
    random_suffix = "".join(random.choices(string.ascii_letters, k=6))

    content = f"""
function add(a, b) {{
    // Modified by test_{random_suffix}
    console.log('Adding numbers:', a, b);
    return a + b;
}}

function subtract_{random_suffix}(a, b) {{
    return a - b;
}}

module.exports = {{ add, subtract_{random_suffix} }};
"""

    test_file = repo_path / filename
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(content)
    subprocess.run(["git", "add", filename], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"Modify {filename} - {random_suffix}"], cwd=repo_path, check=True
    )


def verify_deps_available(repo_path: Path) -> bool:
    """Check if dependencies and tooling are available by running test.sh."""
    test_script = repo_path / "test.sh"
    if not test_script.exists():
        return False

    result = subprocess.run(["./test.sh"], cwd=repo_path, capture_output=True, check=False)
    return result.returncode == 0


# Strategy 1: Worktree Operations


def test_worktree_branch_checkout_restriction(repo_with_deps):
    """Test that branches in worktrees cannot be checked out in main repo."""
    repo_path = repo_with_deps

    # Create worktree with branch
    worktree_path = create_worktree(repo_path, "test-branch")

    # Try to checkout that branch in main repo (should fail)
    result = subprocess.run(
        ["git", "checkout", "test-branch"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    # Different git versions use different messages
    error_msg = result.stderr.lower()
    assert any(
        phrase in error_msg
        for phrase in ["already checked out", "already used by worktree", "is checked out at"]
    )

    # Remove worktree
    subprocess.run(["git", "worktree", "remove", str(worktree_path)], cwd=repo_path, check=True)

    # Try checkout again (should succeed)
    result = subprocess.run(
        ["git", "checkout", "test-branch"], cwd=repo_path, capture_output=True, check=False
    )
    assert result.returncode == 0

    # Verify we're on the branch
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "test-branch"


def test_worktree_temporary_branch_swap(repo_with_deps):
    """Test workaround using temporary branches for swapping."""
    repo_path = repo_with_deps

    # Record original branch
    original_branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    # Create worktree with mc-feature
    worktree_path = create_worktree(repo_path, "mc-feature")

    # Make changes in worktree
    make_test_changes(worktree_path)

    # Get the commit hash from worktree
    subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=worktree_path, capture_output=True, text=True, check=True
    ).stdout.strip()

    # Create temp branch from mc-feature
    subprocess.run(["git", "branch", "temp-mc-feature", "mc-feature"], cwd=repo_path, check=True)

    # Remove worktree
    subprocess.run(["git", "worktree", "remove", str(worktree_path)], cwd=repo_path, check=True)

    # Checkout mc-feature in main
    subprocess.run(["git", "checkout", "mc-feature"], cwd=repo_path, check=True)

    # Verify changes are present and deps work
    assert (repo_path / "src" / "index.js").read_text().find("Modified by test_") != -1
    assert verify_deps_available(repo_path)

    # Switch back to original branch
    subprocess.run(["git", "checkout", original_branch], cwd=repo_path, check=True)

    # Recreate worktree from existing branch (not creating new branch)
    worktree_path_new = create_worktree(
        repo_path, "mc-feature", "mc-feature-restored", create_new_branch=False
    )

    # Verify worktree has changes
    assert (worktree_path_new / "src" / "index.js").read_text().find("Modified by test_") != -1

    # Cleanup temp branch
    subprocess.run(["git", "branch", "-D", "temp-mc-feature"], cwd=repo_path, check=False)


def test_worktree_patch_based_swap(repo_with_deps):
    """Test using patches to move changes between worktree and main."""
    repo_path = repo_with_deps

    # Setup: Create worktree, make changes
    worktree_path = create_worktree(repo_path, "mc-patch-test")
    make_test_changes(worktree_path)

    # Record main repo's current branch
    subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    # Create patches directory
    patches_dir = repo_path / "patches"
    patches_dir.mkdir(exist_ok=True)

    # Generate patches from worktree (last commit)
    patch_result = subprocess.run(
        ["git", "format-patch", "-1", "HEAD", "-o", str(patches_dir)],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        check=True,
    )
    patch_file = patch_result.stdout.strip()

    # Apply patches to main repo
    subprocess.run(["git", "am", patch_file], cwd=repo_path, capture_output=True, check=True)

    # Verify changes applied correctly and deps available
    assert (repo_path / "src" / "index.js").read_text().find("Modified by test_") != -1
    assert verify_deps_available(repo_path)

    # Make additional changes in main
    make_test_changes(repo_path, "src/new_file.js")

    # Generate reverse patches for new changes
    new_patch_result = subprocess.run(
        ["git", "format-patch", "-1", "HEAD", "-o", str(patches_dir)],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    new_patch_file = new_patch_result.stdout.strip()

    # Apply patches back to worktree
    subprocess.run(
        ["git", "am", new_patch_file], cwd=worktree_path, capture_output=True, check=True
    )

    # Verify bidirectional sync worked
    assert (worktree_path / "src" / "new_file.js").exists()
    assert (worktree_path / "src" / "index.js").read_text().find("Modified by test_") != -1


# Strategy 2: Local Clone Network


def test_bare_clone_as_hub(repo_with_deps):
    """Test using bare clone as central hub for multiple working repos."""
    repo_path = repo_with_deps
    base_dir = repo_path.parent

    # Create bare clone from original
    bare_path = base_dir / "bare-hub.git"
    subprocess.run(["git", "clone", "--bare", str(repo_path), str(bare_path)], check=True)

    # Clone from bare for "main" work repo (with deps)
    main_clone = base_dir / "main-work"
    subprocess.run(["git", "clone", str(bare_path), str(main_clone)], check=True)

    # Copy node_modules to main clone to simulate installed deps
    if (main_clone / "node_modules").exists():
        shutil.rmtree(main_clone / "node_modules")
    shutil.copytree(repo_path / "node_modules", main_clone / "node_modules")

    # Clone from bare for "task" repo
    task_clone = base_dir / "task-work"
    subprocess.run(["git", "clone", str(bare_path), str(task_clone)], check=True)

    # Create branch in task repo
    subprocess.run(["git", "checkout", "-b", "mc-feature"], cwd=task_clone, check=True)
    make_test_changes(task_clone)

    # Push to bare
    subprocess.run(["git", "push", "origin", "mc-feature"], cwd=task_clone, check=True)

    # Fetch/checkout branch in main repo
    subprocess.run(["git", "fetch", "origin"], cwd=main_clone, check=True)
    subprocess.run(["git", "checkout", "mc-feature"], cwd=main_clone, check=True)

    # Verify changes visible and deps work
    assert (main_clone / "src" / "index.js").read_text().find("Modified by test_") != -1
    assert verify_deps_available(main_clone)

    # Make changes in main, push back
    make_test_changes(main_clone, "src/main_changes.js")
    subprocess.run(["git", "push", "origin", "mc-feature"], cwd=main_clone, check=True)

    # Pull in task repo
    subprocess.run(["git", "pull", "origin", "mc-feature"], cwd=task_clone, check=True)
    assert (task_clone / "src" / "main_changes.js").exists()

    # Measure disk usage
    bare_size = measure_disk_usage(bare_path)
    main_size = measure_disk_usage(main_clone)
    task_size = measure_disk_usage(task_clone)

    # Bare should be smallest (no working tree)
    assert bare_size < main_size
    assert bare_size < task_size

    print(f"Bare hub size: {bare_size / 1024:.2f} KB")
    print(f"Main clone size: {main_size / 1024:.2f} KB")
    print(f"Task clone size: {task_size / 1024:.2f} KB")


def test_mirror_clone_approach(repo_with_deps):
    """Test using --mirror for efficient branch sharing."""
    repo_path = repo_with_deps
    base_dir = repo_path.parent

    # Create mirror clone
    mirror_path = base_dir / "mirror.git"
    subprocess.run(["git", "clone", "--mirror", str(repo_path), str(mirror_path)], check=True)

    # Create regular clone from mirror
    work_clone = base_dir / "work-from-mirror"
    subprocess.run(["git", "clone", str(mirror_path), str(work_clone)], check=True)

    # Create branch and push
    subprocess.run(["git", "checkout", "-b", "test-mirror"], cwd=work_clone, check=True)
    make_test_changes(work_clone)
    subprocess.run(["git", "push", "origin", "test-mirror"], cwd=work_clone, check=True)

    # Verify refs synchronized in mirror
    refs_result = subprocess.run(
        ["git", "ls-remote", str(mirror_path)], capture_output=True, text=True, check=True
    )
    assert "refs/heads/test-mirror" in refs_result.stdout

    # Compare disk usage
    mirror_size = measure_disk_usage(mirror_path)
    regular_bare = base_dir / "regular-bare.git"
    subprocess.run(["git", "clone", "--bare", str(repo_path), str(regular_bare)], check=True)
    regular_size = measure_disk_usage(regular_bare)

    # Mirror includes all refs, might be slightly larger
    # But should be in same ballpark
    size_ratio = mirror_size / regular_size if regular_size > 0 else 1
    assert 0.9 < size_ratio < 1.5

    print(f"Mirror size: {mirror_size / 1024:.2f} KB")
    print(f"Regular bare size: {regular_size / 1024:.2f} KB")
    print(f"Size ratio: {size_ratio:.2f}")


def test_direct_clone_to_clone(repo_with_deps):
    """Test direct communication between local clones."""
    repo_path = repo_with_deps
    base_dir = repo_path.parent

    # Setup main repo with deps
    main_repo = base_dir / "main-with-deps"
    shutil.copytree(repo_path, main_repo)

    # Clone main repo for task
    task_clone = base_dir / "task-clone"
    subprocess.run(["git", "clone", str(main_repo), str(task_clone)], check=True)

    # Add main as remote in task clone (already origin)
    # Create branch in task clone
    subprocess.run(["git", "checkout", "-b", "mc-direct"], cwd=task_clone, check=True)
    make_test_changes(task_clone)

    # Push branch to main repo
    subprocess.run(["git", "push", "origin", "mc-direct"], cwd=task_clone, check=True)

    # Verify branch appears in main
    subprocess.run(["git", "fetch"], cwd=main_repo, check=True)
    branches_result = subprocess.run(
        ["git", "branch", "-a"], cwd=main_repo, capture_output=True, text=True, check=True
    )
    assert "mc-direct" in branches_result.stdout

    # Checkout and verify deps work
    subprocess.run(["git", "checkout", "mc-direct"], cwd=main_repo, check=True)
    assert verify_deps_available(main_repo)

    # Measure disk usage for full clones
    main_size = measure_disk_usage(main_repo)
    task_size = measure_disk_usage(task_clone)

    # Task clone should be smaller (no node_modules) or roughly equal
    # Git clones include node_modules in the repo
    assert task_size <= main_size * 1.1  # Allow 10% variance

    # Print sizes for reference
    print(f"Main repo size: {main_size / 1024 / 1024:.2f} MB")
    print(f"Task clone size: {task_size / 1024 / 1024:.2f} MB")
