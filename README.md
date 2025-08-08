# Multiclaude

CLI tool for managing parallel Claude Code instances using git worktrees. Work on multiple tasks concurrently without conflicts.

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

## Usage

### Initialize in a repository

```bash
cd your-repo
multiclaude init
```

This creates a `.multiclaude/` directory to track tasks and adds it to `.git/info/exclude`.

### Create a new task

```bash
# Create worktree and launch Claude Code
multiclaude new feature-xyz

# Create worktree without launching Claude
multiclaude new bugfix-123 --no-launch
```

This will:
1. Create a new branch `mc-feature-xyz`
2. Set up a worktree at `~/multiclaude-worktrees/<repo-name>/mc-feature-xyz/`
3. Launch Claude Code in the worktree directory
4. You can then provide task details directly to Claude

### List tasks

```bash
# Show active tasks
multiclaude list

# Include pruned tasks
multiclaude list --show-pruned
```

Example output:
```
Active multiclaude tasks:
  - mc-dark-mode: branch mc-dark-mode (created 2h ago)
  - mc-auth-fix: branch mc-auth-fix (created 30m ago)
```

## How It Works

1. Each task gets its own git worktree - an isolated working directory with its own branch
2. Claude Code runs in the worktree, allowing parallel development without conflicts
3. Worktrees are stored outside the main repository to avoid nesting issues
4. Task metadata is tracked in `.multiclaude/tasks.json`

## Directory Structure

```
your-repo/
├── .multiclaude/           # Task metadata (gitignored)
│   ├── config.json
│   └── tasks.json
└── ... your code ...

~/multiclaude-worktrees/    # Worktrees location
└── your-repo/
    ├── mc-feature-1/
    └── mc-feature-2/
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

# When done, create PRs from each worktree
cd ~/multiclaude-worktrees/my-repo/mc-dark-mode
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

# Run with coverage
pytest --cov=multiclaude
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
sandbox-admin clean         # Clean worktrees only
```

### Code Quality

```bash
# Format code
ruff format multiclaude/

# Lint
ruff check multiclaude/

# Run type checking (if using mypy)
mypy multiclaude/
```

## Roadmap

- Phase 1 (Current): Basic init, new, list commands
- Phase 2: Task status tracking and notifications  
- Phase 3: PR creation and review tools
- Phase 4: Environment setup automation
- Phase 5: Cleanup and lifecycle management

See [SPEC.md](SPEC.md) for detailed specifications.