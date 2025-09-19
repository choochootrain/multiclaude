"""Configuration management for multiclaude."""

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import MultiClaudeError, NotInitializedError

DEFAULT_AGENT = "claude"


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


# Known config paths that can be read/written
KNOWN_CONFIG_PATHS: set[str] = {
    "version",
    "repo_root",
    "default_branch",
    "created_at",
    "environment_strategy",
    "default_agent",
    "environments_dir",
}


def config_exists(repo_root: Path) -> bool:
    """Check if multiclaude is initialized."""
    config_dir = repo_root / ".multiclaude"
    config_file = config_dir / "config.json"
    return config_dir.exists() and config_file.exists()


def _get_default_branch(repo_root: Path) -> str:
    """Get the default branch name."""
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True,
            text=True,
            check=False,
            cwd=repo_root,
        )
        if result.returncode == 0:
            # refs/remotes/origin/main -> main
            return result.stdout.strip().split("/")[-1]
    except Exception:
        pass
    return "main"


def initialize_config(repo_root: Path, environments_dir: Path | None = None) -> Config:
    """Initialize multiclaude configuration."""
    from .cli import get_version

    config_dir = repo_root / ".multiclaude"
    config_file = config_dir / "config.json"
    config_dir.mkdir(exist_ok=True)

    config_dict = {
        "version": get_version(),
        "repo_root": str(repo_root),
        "default_branch": _get_default_branch(repo_root),
        "created_at": datetime.now().isoformat(),
        "environment_strategy": "clone",
        "default_agent": DEFAULT_AGENT,
    }

    # Set environments_dir if provided
    if environments_dir:
        config_dict["environments_dir"] = str(environments_dir.expanduser().resolve())

    config_file.write_text(json.dumps(config_dict, indent=2))

    # Add .multiclaude to .git/info/exclude
    exclude_file = repo_root / ".git" / "info" / "exclude"
    if exclude_file.exists():
        content = exclude_file.read_text()
        if ".multiclaude" not in content:
            exclude_file.write_text(content + "\n.multiclaude\n")

    # Return Config object
    return Config(
        version=config_dict["version"],
        repo_root=Path(config_dict["repo_root"]),
        default_branch=config_dict["default_branch"],
        created_at=config_dict["created_at"],
        environment_strategy=config_dict["environment_strategy"],
        default_agent=config_dict["default_agent"],
        environments_dir=Path(
            config_dict.get("environments_dir", Path.home() / "multiclaude-environments")
        )
        .expanduser()
        .resolve(),
    )


def _load_config_dict(repo_root: Path) -> dict[str, Any]:
    """Load raw configuration dictionary."""
    config_file = repo_root / ".multiclaude" / "config.json"
    if not config_exists(repo_root):
        raise NotInitializedError("Multiclaude not initialized. Run 'multiclaude init' first.")
    config = json.loads(config_file.read_text())
    if "default_agent" not in config or not isinstance(config["default_agent"], str):
        config["default_agent"] = DEFAULT_AGENT
    return config


def save_config(repo_root: Path, config: Config) -> None:
    """Save Config to file."""
    config_file = repo_root / ".multiclaude" / "config.json"
    if not config_exists(repo_root):
        raise NotInitializedError("Multiclaude not initialized. Run 'multiclaude init' first.")

    config_dict = {
        "version": config.version,
        "repo_root": str(config.repo_root),
        "default_branch": config.default_branch,
        "created_at": config.created_at,
        "environment_strategy": config.environment_strategy,
        "default_agent": config.default_agent,
        "environments_dir": str(config.environments_dir),
    }
    config_file.write_text(json.dumps(config_dict, indent=2))


def get_config_value(config: Config, path: str) -> Any:
    """Get a configuration value by path.

    Only allows reading known configuration paths.
    """
    # Check if the root path is known
    if path not in KNOWN_CONFIG_PATHS:
        raise MultiClaudeError(f"Unknown configuration path: {path}")

    return getattr(config, path, None)


def set_config_value(config: Config, path: str, value: Any) -> Config:
    """Set a configuration value by path and return updated Config.

    Validates the value based on the configuration key.
    Only allows writing to known configuration paths.
    """

    # Check if the root path is known
    if path not in KNOWN_CONFIG_PATHS:
        raise MultiClaudeError(f"Unknown configuration path: {path}")

    # Validate the value based on the key
    if path == "environments_dir":
        # Expand user path and convert to absolute
        expanded_path = Path(value).expanduser().resolve()
        # Check if parent directory exists (we'll create the dir itself if needed)
        if not expanded_path.parent.exists():
            raise MultiClaudeError(f"Parent directory does not exist: {expanded_path.parent}")
        value = expanded_path
    elif path == "environment_strategy":
        if value not in ["clone", "worktree"]:
            raise MultiClaudeError(
                f"Invalid environment strategy: {value}. Must be 'clone' or 'worktree'"
            )
    elif path == "default_agent":
        if not isinstance(value, str) or not value.strip():
            raise MultiClaudeError("Default agent must be a non-empty string")
        value = value.strip()
    elif path in ["version", "repo_root", "created_at"]:
        raise MultiClaudeError(f"Configuration key '{path}' is read-only")

    # Create new config with updated value
    config_dict = {
        "version": config.version,
        "repo_root": config.repo_root,
        "default_branch": config.default_branch,
        "created_at": config.created_at,
        "environment_strategy": config.environment_strategy,
        "default_agent": config.default_agent,
        "environments_dir": config.environments_dir,
    }
    config_dict[path] = value

    # Save and return new Config
    new_config = Config(**config_dict)
    save_config(config.repo_root, new_config)
    return new_config


def load_config(repo_root: Path) -> Config:
    """Load configuration for the current repository.

    Returns:
        Config with all configuration values

    Raises:
        NotInitializedError: If multiclaude is not initialized
    """
    config_dict = _load_config_dict(repo_root)

    # Convert to Config
    return Config(
        version=config_dict["version"],
        repo_root=Path(config_dict["repo_root"]),
        default_branch=config_dict["default_branch"],
        created_at=config_dict["created_at"],
        environment_strategy=config_dict.get("environment_strategy", "clone"),
        default_agent=config_dict.get("default_agent", DEFAULT_AGENT),
        environments_dir=Path(
            config_dict.get("environments_dir", Path.home() / "multiclaude-environments")
        )
        .expanduser()
        .resolve(),
    )
