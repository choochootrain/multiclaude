"""Run multiclaude commands in sandbox environment."""

import os
import sys
from pathlib import Path

from .cli import main as multiclaude_main


def main() -> None:
    """Run multiclaude in sandbox environment."""
    # Set up sandbox environment
    script_dir = Path(__file__).parent.parent
    sandbox_repo = script_dir / "repos" / "sandbox" / "main"

    # Change to sandbox repo
    if sandbox_repo.exists():
        os.chdir(sandbox_repo)
    else:
        print(f"Error: Sandbox repo not found at {sandbox_repo}", file=sys.stderr)
        print("Run 'sandbox-admin reset' to create it.", file=sys.stderr)
        sys.exit(1)

    # Run multiclaude with the same arguments
    multiclaude_main()


if __name__ == "__main__":
    main()
