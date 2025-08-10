# Multiclaude

CLI tool for managing parallel Claude Code instances using isolated environments. Each task gets its own isolated working directory and branch (prefixed with `mc-`).

## Key Files
- `multiclaude/cli.py` - Main CLI implementation (init, new, list commands)
- `.multiclaude/tasks.json` - Tracks active tasks (created by init)
- Environments stored in `~/multiclaude-environments/<repo-name>/mc-<branch>/`

## Usage

```bash
# Initialize in a repo
multiclaude init

# Create new task (launches Claude in isolated environment)
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

Sandbox location: `repos/sandbox/main/` (repo), `repos/sandbox/worktrees/` (environments)

## Code Quality

When completing tasks, always run linting and formatting:

```bash
# Check and fix linting issues
ruff check --fix multiclaude/

# Format code consistently  
ruff format multiclaude/

# Run tests to ensure nothing broke
pytest
```

## Environment Variables
- `MULTICLAUDE_ENVIRONMENT_DIR` - Override default environment location (used in tests and sandbox)