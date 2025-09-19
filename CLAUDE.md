# Multiclaude

CLI tool for managing parallel Claude Code instances using isolated git environments. Each task gets its own complete git clone with proper remote configuration.


See [SPEC.md](SPEC.md) for planned features to work on.
See [README.md](README.md) for overview and usage.

## Key Development Notes

- Use `pytest` for testing, `ruff` for linting/formatting
- Clone strategy is default (creates full git clones vs worktrees)
- Tasks tracked in `.multiclaude/tasks.json`, branches use `mc-` prefix

### Development Workflow
1. Write tests for new features first, run with `pytest`
2. Run type/lint/format checks with `pre-commit run --all-files`

## Error Handling
- NEVER fail silently - always print warnings or errors when operations fail
- If an operation can't complete as expected, inform the user with clear messages
- When falling back to alternative behavior, explain what happened and why
