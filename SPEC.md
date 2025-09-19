# Multiclaude CLI Tool Specification

See [README.md](README.md) for overview and usage.

## Phase Plan

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
- [ ] Task completion detection - How to know when a task is done?
- [ ] Task dependencies/sequencing
- [ ] MCP integrations
- [ ] Remote execution
- [ ] Resume tasks
- [ ] Session management
- [ ] Custom Claude flags
- [ ] Multi-repo improvements
