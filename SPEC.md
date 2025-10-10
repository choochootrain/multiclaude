# Multiclaude CLI Tool Specification

See [README.md](README.md) for overview and usage.

## Phase Plan

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


### AI Effectiveness Tracking
**Goal:** Measure and improve AI-assisted development effectiveness

**Metrics:**
- Task success rate by type (bug/feature/refactor/docs)
- Prompt effectiveness patterns
- Code quality metrics (tests/lint/reviews)
- Manual intervention requirements

**Implementation:**
- Add metadata fields to tasks.json for tracking
- Create evaluation scripts in tools/
- Export metrics for analysis
- Build simple dashboard for trends

### Future Phases (Backlog/Unplanned)
- [ ] Branch name inference (`new "add dark mode"` → `mc-add-dark-mode`)
- [ ] Task completion detection - How to know when a task is done?
- [ ] Refactor to support multiple git strategies with easy switching
- [ ] Worktree strategy parity - Add `push.autoSetupRemote` config and ensure all branches are available (like clone strategy)
- [ ] Task dependencies/sequencing
- [ ] MCP integrations
- [ ] Remote execution
- [ ] Session management
- [ ] Custom Claude flags
- [ ] Multi-repo improvements
