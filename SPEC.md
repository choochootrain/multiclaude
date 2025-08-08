# Multiclaude CLI Tool Specification

## Overview

Multiclaude is a CLI tool that orchestrates multiple parallel Claude Code instances using git worktrees. It allows developers to work on multiple tasks concurrently without conflicts, with each Claude Code instance operating in its own isolated git worktree.

### Core Concept
- Each task gets its own git worktree (isolated working directory)
- Claude Code instances run independently in their respective worktrees
- Lightweight metadata tracking without complex orchestration
- Direct interaction with Claude Code through terminal windows/tabs

## CLI Interface

### Commands

#### `multiclaude init`
Initialize multiclaude in the current git repository.

**Behavior:**
- Validates that current directory is a git repository
- Creates `.multiclaude/` directory structure
- Initializes metadata files
- Adds `.multiclaude` to `.git/info/exclude` to avoid polluting shared repos

**Error cases:**
- Not in a git repository → error with helpful message
- Already initialized → skip with success message

#### `multiclaude new <branch-name>`
Create a new Claude task with its own worktree and launch Claude Code.

**Behavior:**
1. Create branch with name `mc-<branch-name>`
2. Create git worktree in external directory (e.g., `~/multiclaude-worktrees/<repo-name>/mc-<branch-name>`)
3. Record task metadata (branch, timestamp)
4. Change to worktree directory and launch Claude Code
5. User provides task context/details directly in Claude Code prompt

**Options:**
- `--no-launch` - Create worktree without launching Claude (still changes to worktree directory)

**Error cases:**
- Branch already exists → fail with error
- Worktree creation fails → cleanup and error message

#### `multiclaude list`
List all multiclaude-managed tasks.

**Output format:**
```
Active multiclaude tasks:
- mc-dark-mode: branch mc-dark-mode (created 2h ago)
- mc-auth-fix: branch mc-auth-fix (created 30m ago)

Pruned tasks (metadata retained):
- mc-old-feature: branch mc-old-feature (pruned 1d ago)
```

**Behavior:**
- Read tasks from metadata
- Check actual worktree status via `git worktree list`
- Show active tasks first, pruned tasks last (or hidden by default)

#### `multiclaude prune [<task-name>]`
Remove a task's worktree and optionally delete its branch.

**Behavior without arguments (gc mode):**
1. List all active tasks
2. For each: prompt "Prune mc-xyz? [y/n/skip-all]"
3. Execute prune for selected tasks

**Behavior with task-name:**
1. Remove git worktree
2. Prompt: "Delete branch mc-xyz? [y/N]"
3. Mark task as "pruned" in metadata (keep record)

**Options:**
- `--force` - Skip confirmation prompts
- `--keep-branch` - Don't prompt for branch deletion
- `--all` - Prune all tasks (with confirmation)

## Architecture

### Directory Structure

**Repository (.multiclaude in repo root):**
```
.multiclaude/
├── config.json          # Repository configuration
└── tasks.json           # Task metadata
```

**Worktrees (external directory):**
```
~/multiclaude-worktrees/        # Configurable base directory
└── <repo-name>/
    ├── mc-task-1/
    └── mc-task-2/
```

### Metadata Storage

#### `config.json`
```json
{
  "version": "1.0.0",
  "repo_root": "/path/to/repo",
  "default_branch": "main",
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### `tasks.json`
```json
[
  {
    "id": "mc-dark-mode",
    "branch": "mc-dark-mode",
    "created_at": "2024-01-01T10:00:00Z",
    "status": "active",
    "worktree_path": "~/multiclaude-worktrees/my-repo/mc-dark-mode"
  },
  {
    "id": "mc-old-task",
    "branch": "mc-old-task",
    "created_at": "2024-01-01T08:00:00Z",
    "status": "pruned",
    "pruned_at": "2024-01-01T12:00:00Z",
    "worktree_path": "~/multiclaude-worktrees/my-repo/mc-old-task"
  }
]
```

### Git Worktree Integration

**Worktree naming convention:**
- Location: `~/multiclaude-worktrees/<repo-name>/<branch-name>`
- Branch: `mc-<branch-name>`

**Detection of multiclaude worktrees:**
- Check expected path pattern in worktree base directory
- Check branch prefix `mc-`
- Cross-reference with `tasks.json`

## Implementation Details

### Language Choice
**Typed Python with uv and ruff**
- Type hints for better code quality
- uv for dependency management
- ruff for linting/formatting
- Stdlib focus for portability

### Dependencies
- Minimal external dependencies
- Use stdlib as much as possible
- Package as portable script

### Git Operations
- Use git CLI commands via subprocess/exec
- Commands needed:
  - `git rev-parse --git-dir` - Verify git repo
  - `git worktree add <path> -b <branch>`
  - `git worktree list --porcelain`
  - `git worktree remove <path>`
  - `git branch -d <branch>`

### Claude Code Integration
- Change to worktree directory, then launch: `cd <path> && claude`
- Check claude is installed: `which claude`
- Detect if Claude Code not installed and provide helpful error
- CLAUDE.md passed via version control (in repo)

### Error Handling
- Validate git repo before operations
- Check claude installation on init/new
- Atomic operations (rollback on failure)
- Clear error messages with recovery suggestions

## Phase Plan

### Phase 1 - MVP (WIP)
**Goal:** Basic functionality to create and manage parallel Claude tasks

**Features:**
- [ ] `init` - Initialize multiclaude
- [ ] `new <branch-name>` - Create task with worktree and launch Claude
- [ ] `list` - Show all tasks

**Technical:**
- Simple JSON metadata storage
- Direct git CLI integration
- Basic error handling

### Phase 1.5 - Branch Name Inference (TODO)
**Goal:** Better UX for creating tasks

**Features:**
- [ ] Infer branch name from task description
- [ ] `new "add dark mode"` → `mc-add-dark-mode`

### Phase 2 - Enhanced Status (TODO)
**Goal:** Better visibility into task status

**Features:**
- [ ] Hook integration for Claude Code notifications
- [ ] Status tracking (active, waiting_input, completed)
- [ ] `status` command with detailed task info
- [ ] Worktree health checks

### Phase 3 - Collaboration Features (TODO)
**Goal:** Streamline code review and PR workflow

**Features:**
- [ ] `review <task>` - Open diff/changes for review
- [ ] `pr <task>` - Create GitHub PR from task branch
- [ ] Integration with GitHub issues
- [ ] PR description generation from Claude's work

**Technical:**
- GitHub CLI (`gh`) integration
- Diff visualization options

### Phase 3.5 - CLAUDE.md Updates (TODO)
**Goal:** Quick updates to CLAUDE.md based on findings

**Features:**
- [ ] Custom command to update CLAUDE.md with learnings
- [ ] Sync findings across worktrees

### Phase 4 - Environment Setup (TODO)
**Goal:** Automated worktree environment preparation

**Features:**
- [ ] Auto-install dependencies (npm, pip, etc.)
- [ ] Setup tooling per worktree
- [ ] Task templates/commands
- [ ] Copy CLAUDE.local.md to worktrees

### Phase 4.5 - Cost Tracking (TODO)
**Goal:** Monitor Claude usage per task

**Features:**
- [ ] Track token usage per task
- [ ] Cost reporting

### Phase 5 - Cleanup Management (TODO)
**Goal:** Manage task lifecycle

**Features:**
- [ ] `prune` - Remove individual task
- [ ] Batch cleanup mode
- [ ] Auto-cleanup after merge

### Future Phases (Backlog/Unplanned)
- [ ] Task dependencies/sequencing
- [ ] MCP integrations
- [ ] Remote execution
- [ ] Resume tasks
- [ ] Session management
- [ ] Custom Claude flags
- [ ] Multi-repo improvements

## Decisions Made

1. **Language:** Typed Python with uv and ruff
2. **Branch naming:** `mc-<branch-name>`, no customization, fail on conflict
3. **Task lifecycle:** Complete when user says (future phase feature)
4. **Claude Code integration:** CLAUDE.md via version control, detect if not installed, no custom flags for now
5. **Metadata persistence:** Keep forever, list pruned last/hidden, version JSON for migrations
6. **User workflow:** Tool launches Claude, user manages terminals, multi-repo works via repo-specific .multiclaude

## Open Questions (Future Phases)

1. **Worktree base directory:** Make configurable via env var or config file?
2. **Task completion detection:** How to know when a task is done?
3. **Schema migrations:** Versioning strategy for JSON files?

## Security Considerations

- Don't store sensitive data in metadata files
- Safe branch name generation (no command injection)
- Validate all user inputs

## Testing Strategy

**Manual testing scenarios:**
1. Init in non-git directory (should fail)
2. Create task with special characters in branch name
3. Prune task with uncommitted changes
4. Concurrent task creation

## Documentation Needs

- README with quick start guide
- --help for each command
- Example workflows