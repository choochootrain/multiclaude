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
