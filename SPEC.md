# Multiclaude CLI Tool Specification

See [README.md](README.md) for overview and usage.

## Phase Plan

### Phase 1.35 - Environment Recycling (COMPLETE)
**Goal:** Reuse existing clone environments to save time and disk space

**Features:**
- [x] Automatic recycling: When removing tasks, rename environments to `avail-{hash}` for reuse
- [x] Smart reuse: Check for available environments before creating new clones
- [x] Quick exploration: Add `-n` short flag for `--no-launch` to explore without Claude
- [x] Clear messaging: Show whether environment was reused or newly created

**Technical:**
- Available environments use naming pattern: `avail-{hash}` (e.g., `avail-a3f2b9`)
- Prefix `avail-` prevents collision with user-created branches like `mc new abc123`
- When creating new task with clone strategy:
  - Scan environment directory for `avail-{hash}` pattern
  - If found: rename to task name, reset to base ref, create new branch
  - If not: clone as usual
  - Returns tuple indicating whether environment was reused
- When removing task (clone strategy):
  - Generate short hash (6-8 alphanumeric chars)
  - Rename environment to `avail-{hash}` instead of deleting
  - Clean git state (remove uncommitted changes, reset to default branch)
- No tracking file needed - directory scan is sufficient
- Benefits: Saves clone time on large repos, reduces disk I/O

### Phase 1.36 - Prune Command (COMPLETE)
**Goal:** Clean up task environments intelligently

**Features:**
- [x] Smart detection: auto-prune if branch merged to default branch
- [x] Manual cleanup: detect and remove stale tasks.json entries
- [x] Selective pruning: `prune <task-name>` to prune specific task
- [x] Force mode: `prune <task> --force` to prune regardless of safety checks
- [x] Dry run: `--dry-run` shows what would happen without making changes
- [x] `multiclaude list` hides pruned entries by default with `--show-pruned` flag to reveal them

**Command Usage:**
```bash
multiclaude prune              # Prune all eligible (merged/stale) tasks
multiclaude prune <task-name>  # Prune specific task if eligible
multiclaude prune <task> --force  # Force prune (skip safety checks)
multiclaude prune --dry-run    # Show what would be pruned
multiclaude prune --yes        # Skip confirmation prompt when pruning
```

**Technical:**
- Check merge status: `git branch --merged <default-branch>`
- Check for uncommitted changes: `git status --porcelain`
- Check for unpushed commits: `git log origin/<branch>..HEAD`
- Skip environments with uncommitted/unpushed changes (unless --force)
- For clone strategy: Convert to available environment (`avail-{hash}`)
- For worktree strategy: Remove worktree (can't recycle)
- Update tasks.json to mark entries as pruned

**Safety:**
- Check for uncommitted and unpushed changes
- Skip unsafe environments (warn user)
- --force flag overrides all safety checks
- Confirm before destructive operations (unless --yes flag)

### Phase 1.37 - Multi-Agent Launch (COMPLETE)
**Goal:** Allow launching environments with agents other than Claude Code while keeping Claude as the default.

**Features:**
- [x] `multiclaude new ... --agent/-a <name>` to choose agent per task
- [x] Persist selected agent in `.multiclaude/tasks.json`
- [x] Surface agent information in `multiclaude list`
- [x] Optional repository-level default agent via `.multiclaude/config.json`

**Technical:**
- Treat agent name as the executable/command to invoke for launch
- On `init`, write `default_agent` (default `claude`) and migrate existing configs
- Extend `Task` schema to include `agent`
- Validate requested agent, ensure executable exists before environment creation
- Launch the selected agent process instead of hardcoded Claude command
- Ensure `--no-launch` skips agent invocation uniformly

**Safety & UX:**
- Invalid agent values (empty strings, whitespace) trigger clear CLI errors with guidance
- Missing executables warn users and exit without partial setup
- Document expected usage and agent configuration in `README.md` and `AGENTS.md`
- Add pytest coverage for agent flag parsing, config migration, validation, and launch logic

### Phase 1.44 - Resume Task Command
**Goal:** Allow users to resume work on existing tasks

**Features:**
- [ ] `resume <task-name>` - Change to task environment and resume Claude conversation
- [ ] Change working directory to task's environment
- [ ] Launch Claude Code with `/resume` to continue previous chat
- [ ] Support resuming by partial task name match
- [ ] Error handling for non-existent tasks

**Technical:**
- Lookup task in tasks.json
- Verify environment/worktree still exists
- Change to task directory before launching Claude
- Pass `/resume` flag to Claude Code for chat continuation

### Phase 1.45 - Swappable Environment Creation Strategy
**Goal:** Refactor to support multiple git strategies with easy switching

**Features:**
- [ ] Create strategy abstraction layer for environment creation
- [ ] Keep existing worktree strategy implementation
- [ ] Implement new Direct Clone-to-Clone strategy
- [ ] Configuration-based strategy selection
- [ ] Support repositories with submodules (clone strategy only)
- [ ] Maintain existing user interface (no breaking changes)

**Technical:**
- Abstract strategy interface for environment creation/deletion
- Worktree strategy: existing git worktree implementation
- Clone strategy: full repository clones with push/pull workflow (DEFAULT)
- Strategy selection via config.json or environment variable
- Manual submodule branch checkout for clone strategy
- Easy extensibility for future strategies

### Phase 1.6 - Environment Preparation Hooks
**Goal:** Automated post-clone environment setup

**Features:**
- [ ] `.multiclaude/config.json` support for `"prepare_environment"` hook
- [ ] Post-clone script execution (e.g., `npm install`, build tools)
- [ ] Hook failure handling and error reporting
- [ ] Manual configuration support (no CLI yet)

**Technical:**
- Configurable post-clone scripts in config.json
- Script execution in task worktree directory
- Failure detection and rollback handling

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
- [ ] Sync findings across environments

### Phase 4 - Environment Setup (TODO)
**Goal:** Automated environment preparation

**Features:**
- [ ] Auto-install dependencies (npm, pip, etc.)
- [ ] Setup tooling per environment
- [ ] Task templates/commands
- [ ] Copy CLAUDE.local.md to environments

### Phase 4.5 - Cost Tracking (TODO)
**Goal:** Monitor Claude usage per task

**Features:**
- [ ] Track token usage per task
- [ ] Cost reporting


### Future Phases (Backlog/Unplanned)
- [ ] Shell directory persistence - Keep user in task directory after Claude exits (complex shell interaction patterns)
- [ ] Concurrency locking - Prevent race conditions when multiple `multiclaude new` run simultaneously
  - File-based PID lock for critical sections (tasks.json updates, available environment claiming)
  - Stale lock detection using PID liveness check
  - Zero dependencies, Unix/Mac only (Windows unsupported)
  - Alternative: Migrate to SQLite for built-in transaction support
- [ ] Worktree strategy parity - Add `push.autoSetupRemote` config and ensure all branches are available (like clone strategy)
- [ ] Branch name inference (`new "add dark mode"` → `mc-add-dark-mode`)
- [ ] `config` command - Get/set configuration values like git config (e.g., `multiclaude config environment_strategy worktree`)
- [ ] Task completion detection - How to know when a task is done?
- [ ] Task dependencies/sequencing
- [ ] MCP integrations
- [ ] Remote execution
- [ ] Resume tasks
- [ ] Session management
- [ ] Custom Claude flags
- [ ] Multi-repo improvements
