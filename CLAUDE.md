# Multiclaude

CLI tool for managing parallel Claude Code instances using git worktrees. Each task gets its own isolated working directory and branch (prefixed with `mc-`).

## Key Files
- `multiclaude/cli.py` - Main CLI implementation (init, new, list commands)
- `.multiclaude/tasks.json` - Tracks active tasks (created by init)
- Worktrees stored in `~/multiclaude-worktrees/<repo-name>/mc-<branch>/`

## Usage

```bash
# Initialize in a repo
multiclaude init

# Create new task (launches Claude in worktree)
multiclaude new feature-xyz
multiclaude new bugfix --no-launch  # without launching Claude

# List tasks
multiclaude list
```

## Testing

```bash
# Run tests
pytest

# Use sandbox for manual testing
sandbox-admin reset  # Create fresh sandbox
mc-sandbox new test  # Run multiclaude in sandbox
```

Sandbox location: `repos/sandbox/main/` (repo), `repos/sandbox/worktrees/` (worktrees)

## Environment Variables
- `MULTICLAUDE_WORKTREE_DIR` - Override default worktree location (used in tests and sandbox)