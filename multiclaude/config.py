"""Configuration management for multiclaude."""

import json
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import MultiClaudeError, NotInitializedError
from .git_utils import get_default_branch

DEFAULT_AGENT = "claude"
DEFAULT_ENVIRONMENTS_DIR = Path.home() / "multiclaude-environments"
DEFAULT_STRATEGY = "clone"

# Configuration constraints
READ_ONLY_FIELDS = {"version", "repo_root", "created_at"}
VALID_STRATEGIES = {"clone", "worktree"}


@dataclass
class Config:
    """Typed configuration for multiclaude."""

    version: str
    repo_root: Path
    default_branch: str
    created_at: str
    environment_strategy: str
    default_agent: str
    environments_dir: Path

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        data = asdict(self)
        # Convert Path objects to strings
        for key, val in data.items():
            if isinstance(val, Path):
                data[key] = str(val)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        """Create Config from dict with defaults and transformations."""
        # Apply defaults
        defaults = {
            "environment_strategy": DEFAULT_STRATEGY,
            "default_agent": DEFAULT_AGENT,
            "environments_dir": DEFAULT_ENVIRONMENTS_DIR,
        }
        for key, val in defaults.items():
            data.setdefault(key, val)

        # Transform paths
        data["repo_root"] = Path(data["repo_root"])
        data["environments_dir"] = _resolve_path(data["environments_dir"])

        return cls(**data)

    @classmethod
    def field_names(cls) -> set[str]:
        """Get all field names."""
        return {f.name for f in fields(cls)}


def _resolve_path(path: Path | str) -> Path:
    """Resolve and expand a path."""
    return Path(path).expanduser().resolve()


def _get_config_file(repo_root: Path) -> Path:
    """Get path to config file."""
    return repo_root / ".multiclaude" / "config.json"


def config_exists(repo_root: Path) -> bool:
    """Check if multiclaude is initialized."""
    return _get_config_file(repo_root).exists()


def _update_git_exclude(repo_root: Path) -> None:
    """Add .multiclaude to git exclude file."""
    exclude_file = repo_root / ".git" / "info" / "exclude"
    if exclude_file.exists():
        content = exclude_file.read_text()
        if ".multiclaude" not in content:
            exclude_file.write_text(content + "\n.multiclaude\n")


def _validate_field(field: str, value: Any) -> Any:
    """Validate a configuration field value."""
    if field == "environments_dir":
        path = _resolve_path(value)
        if not path.parent.exists():
            raise MultiClaudeError(f"Parent directory does not exist: {path.parent}")
        return path

    if field == "environment_strategy":
        if value not in VALID_STRATEGIES:
            raise MultiClaudeError(
                f"Invalid environment strategy: {value}. Must be one of: {', '.join(VALID_STRATEGIES)}"
            )
        return value

    if field == "default_agent":
        if not isinstance(value, str) or not value.strip():
            raise MultiClaudeError("Default agent must be a non-empty string")
        return value.strip()

    return value


def initialize_config(repo_root: Path, environments_dir: Path | None = None) -> Config:
    """Initialize multiclaude configuration."""
    from .cli import get_version  # noqa: PLC0415

    (repo_root / ".multiclaude").mkdir(exist_ok=True)

    config = Config(
        version=get_version(),
        repo_root=repo_root,
        default_branch=get_default_branch(repo_root),
        created_at=datetime.now().isoformat(),
        environment_strategy=DEFAULT_STRATEGY,
        default_agent=DEFAULT_AGENT,
        environments_dir=_resolve_path(environments_dir or DEFAULT_ENVIRONMENTS_DIR),
    )

    save_config(repo_root, config)
    _update_git_exclude(repo_root)

    return config


def save_config(repo_root: Path, config: Config) -> None:
    """Save Config to file."""
    _get_config_file(repo_root).write_text(json.dumps(config.to_dict(), indent=2))


def load_config(repo_root: Path) -> Config:
    """Load configuration for the current repository."""
    if not config_exists(repo_root):
        raise NotInitializedError("Multiclaude not initialized. Run 'multiclaude init' first.")

    data = json.loads(_get_config_file(repo_root).read_text())
    return Config.from_dict(data)


def get_config_value(config: Config, field: str) -> Any:
    """Get a configuration value by field name."""
    all_fields = Config.field_names()
    if field not in all_fields:
        raise MultiClaudeError(f"Unknown configuration field: {field}")
    return getattr(config, field, None)


def set_config_value(config: Config, field: str, value: Any) -> Config:
    """Set a configuration value and return updated Config."""
    all_fields = Config.field_names()
    if field not in all_fields:
        raise MultiClaudeError(f"Unknown configuration field: {field}")

    if field in READ_ONLY_FIELDS:
        raise MultiClaudeError(f"Configuration key '{field}' is read-only")

    value = _validate_field(field, value)
    new_config = replace(config, **{field: value})

    if not config_exists(config.repo_root):
        raise NotInitializedError("Multiclaude not initialized. Run 'multiclaude init' first.")

    save_config(config.repo_root, new_config)
    return new_config
