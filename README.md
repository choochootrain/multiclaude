# Multiclaude

Manage parallel Claude Code instances with isolated git environments. Each task gets its own complete git clone, allowing you to work on multiple features simultaneously without conflicts.

## Installation

### Prerequisites

- Git
- Claude Code CLI (`claude`)
- Python 3.11+
- uv
- mise (optional, for automatic tool installation)

### Quick Start

```bash
# Install tools (if using mise)
mise install

# Install multiclaude as a tool available on your path
uv tool install multiclaude

# Now you can use multiclaude from anywhere
cd $PROJECT; multiclaude --help
```

## Commands

### `multiclaude init`
Initialize multiclaude in the current git repository.
- Validates current directory is a git repository
- Creates `.multiclaude/` directory structure
- Initializes metadata files
- Adds `.multiclaude` to `.git/info/exclude`

**Options:**
- `--environments-dir <path>` - Directory to store environments (default: ~/multiclaude-environments)

### `multiclaude new <branch-name>`
Create new Claude task with isolated git environment and launch Claude Code.

**Options:**
- `--no-launch/-n` - Create environment without launching Claude
- `--base <ref>` - Branch from specific branch/tag/commit (default: main)
- `--agent/-a <command>` - Command to launch for this task's agent (defaults to config default_agent)

Creates branch `mc-<branch-name>` and isolated environment in `~/multiclaude-environments/<repo-name>/mc-<branch-name>/`

### `multiclaude list`
List all multiclaude-managed tasks with creation times and status.

**Options:**
- `--show-pruned` - Include pruned tasks in the output
- `-q/--quiet` - Output only task names (one per line)

### `multiclaude resume <task-name>`
Resume work on an existing task by launching the agent in the task environment.

- Supports partial task name matching (e.g., `resume feature` matches `mc-feature`)
- Changes to task directory and launches agent
- For Claude agent, uses `-r` flag to resume previous conversation
- When you exit the agent, you'll remain in the task directory

**Examples:**
```bash
# Resume by partial name
multiclaude resume feature

# Resume by full branch name
multiclaude resume mc-feature-auth
```

### `multiclaude cd <task-name>`
Open a shell in the task environment directory.

- Supports partial task name matching (e.g., `cd feature` matches `mc-feature`)
- Spawns a subshell in the task directory
- Type `exit` to return to your original location

**Examples:**
```bash
# Open shell in task directory
multiclaude cd feature
# ... do work ...
exit  # returns to original directory
```

### Shell Completion

Multiclaude ships with bash and zsh completions so `resume` and `cd` subcommands offer task suggestions (both full and short names).

```bash
# Bash
source /path/to/repo/completions/multiclaude

# Zsh (after compinit)
source /path/to/repo/completions/multiclaude
compdef _multiclaude_zsh_complete multiclaude
```

Add the relevant `source` line to your shell rc file to enable completions for future sessions.

### `multiclaude config <path>`
Get or set configuration values.

**Options:**
- `--write <value>` - Value to write to the configuration path

**Examples:**
```bash
# Read a config value
multiclaude config environments_dir
multiclaude config default_agent

# Set a config value
multiclaude config default_agent --write "claude"
```

### `multiclaude prune [<task-name>]`
Clean up completed or stale task environments.

**Options:**
- `--force` - Override safety checks and prune anyway
- `--dry-run` - Show what would be pruned without making changes
- `--yes` - Skip confirmation prompt

## How It Works

1. **Isolated Environments**: Each task gets a complete git clone in `~/multiclaude-environments/`
2. **Automatic Branching**: Creates branch `mc-<task-name>` from your specified base
3. **Remote Configuration**: Properly configures git remotes so `git push` works intuitively
4. **Claude Integration**: Automatically launches Claude Code in the task environment
5. **Metadata Tracking**: Tracks tasks in `.multiclaude/tasks.json` for easy management

## Why Clones Instead of Worktrees?

Git worktrees seem like the obvious choice for parallel development, but have limitations ([git-worktree bugs in git 2.52.0](https://git-scm.com/docs/git-worktree/2.52.0#_bugs)):

- **Submodule support is incomplete**: Support for worktrees containing submodules is incomplete
- **Multiple checkout is experimental**: Checking out the same branch in multiple worktrees is still experimental

Full clones provide complete flexibility for repos with submodules and allow checking out the same branch multiple times. The tradeoff is managing branch state between clones (pushing/fetching to sync changes).

The isolation strategy is extensible so worktrees can become the default when git natively addresses these limitations.

## Directory Structure

```
your-repo/
├── .multiclaude/           # Task metadata (gitignored)
│   ├── config.json
│   └── tasks.json
└── ... your code ...

~/multiclaude-environments/    # Environments location
└── your-repo/
    ├── mc-feature-1/          # Complete git clone
    └── mc-feature-2/          # Complete git clone
```

## Workflow Example

```bash
# Start a new feature
multiclaude new dark-mode

# In Claude Code prompt:
# "Add dark mode support to the settings page with a toggle switch"

# While Claude works, start another task in a new terminal
multiclaude new auth-bugfix

# Check on all tasks
multiclaude list

# Resume a task later
multiclaude resume dark-mode  # Resumes Claude with -r flag

# Or just open a shell in a task directory
multiclaude cd dark-mode      # Opens subshell in task directory
# ... manual work ...
exit

# When done, create PRs from each environment
multiclaude cd dark-mode
git add -A
git commit -m "Add dark mode support"
git push -u origin mc-dark-mode
gh pr create
exit  # Return to original directory
```

## Development

### Setup

```bash
# Install dev dependencies
uv sync --dev

# Or if you've activated the venv
uv pip install -e ".[dev]"
```

### Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_init.py

# Run with coverage (shows terminal report with missing lines)
pytest --cov=multiclaude --cov-report=term-missing

# Generate annotated coverage files showing code with coverage markers
./scripts/coverage-annotate.sh
# View annotated files in coverage/ directory
# Lines marked with '>' are covered, '!' are uncovered
```

### Manual Testing with Sandbox

```bash
# Reset sandbox environment
sandbox-admin reset          # Create fresh sandbox repo and initialize

# Run multiclaude commands in sandbox
mc-sandbox list             # List tasks in sandbox
mc-sandbox new test-feature --no-launch  # Create task in sandbox
mc-sandbox init             # Initialize (if needed)

# Check sandbox status
sandbox-admin status        # Show sandbox state
sandbox-admin clean         # Clean environments only
```

### Code Quality

Pre-commit hooks are configured to run automatically on every commit:

```bash
# Install pre-commit hooks (one-time setup)
pre-commit install

# Run all checks manually
pre-commit run --all-files

# Or run individual checks:
# Type checking (strict mypy)
mypy multiclaude/

# Linting and auto-fix
ruff check --fix

# Code formatting
ruff format
```

See [SPEC.md](SPEC.md) for planned features and roadmap.
