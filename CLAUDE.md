# Multiclaude

CLI tool for managing parallel Claude Code instances using isolated git environments. Each task gets its own complete git clone with proper remote configuration.


See [SPEC.md](SPEC.md) for planned features to work on.
See [README.md](README.md) for overview and usage.

## Key Development Notes

- Use `pytest` for testing, `ruff` for linting/formatting
- Test with sandbox: `sandbox-admin reset` then `mc-sandbox new test`
- Clone strategy is default (creates full git clones vs worktrees)
- Tasks tracked in `.multiclaude/tasks.json`, branches use `mc-` prefix

### Development Workflow
1. Write tests for new features first
2. Test with sandbox for manual verification
3. Run `pytest`, `ruff check --fix`, `ruff format` before commits
