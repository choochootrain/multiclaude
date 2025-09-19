"""Administrative tools for sandbox environment."""

import argparse
import sys
from pathlib import Path

from .sandbox_utils import SandboxManager


def cmd_reset(args: argparse.Namespace) -> None:
    """Reset the sandbox environment."""
    print("Resetting sandbox environment...")

    sandbox = SandboxManager(Path("repos"), "sandbox")
    sandbox.reset_sandbox()

    # Initialize multiclaude by calling the function directly
    import os

    # Change to sandbox repo and run init
    original_dir = os.getcwd()
    try:
        os.chdir(sandbox.repo_path)

        # Import and run init directly
        from types import SimpleNamespace

        from multiclaude.cli import cmd_init

        # Initialize with environments_dir directly
        args = SimpleNamespace()
        args.environments_dir = sandbox.worktree_path
        cmd_init(args)

        result = SimpleNamespace(returncode=0, stdout="Initialized", stderr="")
    except Exception as e:
        result = SimpleNamespace(returncode=1, stdout="", stderr=str(e))
    finally:
        os.chdir(original_dir)

    if result.returncode == 0:
        print("✓ Sandbox reset complete")
        print(f"  Repo: {sandbox.repo_path}")
        print(f"  Environments: {sandbox.worktree_path}")
    else:
        print(f"Error initializing multiclaude: {result.stderr}")
        sys.exit(1)


def cmd_clean(args: argparse.Namespace) -> None:
    """Clean worktrees only."""
    print("Cleaning worktrees...")

    sandbox = SandboxManager(Path("repos"), "sandbox")
    if sandbox.worktree_path.exists():
        import shutil

        shutil.rmtree(sandbox.worktree_path)
        sandbox.worktree_path.mkdir(parents=True)

    print("✓ Worktrees cleaned")


def cmd_status(args: argparse.Namespace) -> None:
    """Show sandbox status."""
    sandbox = SandboxManager(Path("repos"), "sandbox")

    print("Sandbox status:")

    if sandbox.exists:
        print("  ✓ sandbox repo exists")
        if sandbox.is_initialized:
            print("  ✓ multiclaude initialized")
        else:
            print("  ✗ multiclaude not initialized (run: ./sandbox-admin.py reset)")
    else:
        print("  ✗ sandbox repo not found (run: ./sandbox-admin.py reset)")

    worktree_count = sandbox.get_worktree_count()
    if worktree_count > 0:
        print(f"  ✓ {worktree_count} worktree(s) in sandbox")
    else:
        print("  ✓ No worktrees created yet")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Administrative tools for sandbox environment")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # reset command
    parser_reset = subparsers.add_parser("reset", help="Delete and recreate sandbox environment")
    parser_reset.set_defaults(func=cmd_reset)

    # clean command
    parser_clean = subparsers.add_parser("clean", help="Remove worktrees only")
    parser_clean.set_defaults(func=cmd_clean)

    # status command
    parser_status = subparsers.add_parser("status", help="Show sandbox status")
    parser_status.set_defaults(func=cmd_status)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
