# Multiclaude

Manage parallel Claude Code instances with isolated git environments. Each task gets its own complete git clone, allowing you to work on multiple features simultaneously without conflicts.

## Installation

### Prerequisites

- Git
- Claude Code CLI (`claude`)
- Python 3.11+
- mise (optional, for automatic tool installation)

### Quick Start

```bash
# Install tools (if using mise)
mise install

# Create virtual environment and install
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Now you can use multiclaude from anywhere (while venv is active)
multiclaude --help
```

Alternative using uv run (no activation needed):
```bash
# Create venv and install
uv venv
uv pip install -e .

# Run with uv (no activation needed)
uv run multiclaude --help
```

Alternative without installing:
```bash
# Make executable and run directly
chmod +x multiclaude.py
./multiclaude.py --help
```

## Commands

### `multiclaude init`
Initialize multiclaude in the current git repository.
- Validates current directory is a git repository
- Creates `.multiclaude/` directory structure
- Initializes metadata files
- Adds `.multiclaude` to `.git/info/exclude`

### `multiclaude new <branch-name>`
Create new Claude task with isolated git environment and launch Claude Code.

**Options:**
- `--no-launch` - Create environment without launching Claude
- `--base <ref>` - Branch from specific branch/tag/commit (default: main)

Creates branch `mc-<branch-name>` and isolated environment in `~/multiclaude-environments/<repo-name>/mc-<branch-name>/`

### `multiclaude list`
List all multiclaude-managed tasks with creation times and status.

### `multiclaude prune [<task-name>]` (planned)
Clean up task environments and branches (future feature).

## How It Works

1. **Isolated Environments**: Each task gets a complete git clone in `~/multiclaude-environments/`
2. **Automatic Branching**: Creates branch `mc-<task-name>` from your specified base
3. **Remote Configuration**: Properly configures git remotes so `git push` works intuitively
4. **Claude Integration**: Automatically launches Claude Code in the task environment
5. **Metadata Tracking**: Tracks tasks in `.multiclaude/tasks.json` for easy management

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

# When done, create PRs from each environment
cd ~/multiclaude-environments/my-repo/mc-dark-mode
git add -A
git commit -m "Add dark mode support"
git push -u origin mc-dark-mode
gh pr create
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
