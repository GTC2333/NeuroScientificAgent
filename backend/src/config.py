"""
Configuration loader for MAS
Loads config.yaml first, then overrides with local.yaml if it exists
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass

PROJECT_ROOT = Path(__file__).parent.parent.parent


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 9000


@dataclass
class ClaudeConfig:
    cli_path: str = "~/.local/bin/claude"
    model: str = "sonnet"
    timeout: int = 120
    api_key: Optional[str] = None  # Anthropic API Key (from local.yaml)


@dataclass
class ProjectConfig:
    root_dir: str = "."
    claude_dir: str = ".claude"
    agents_dir: str = ".claude/agents"
    skills_dir: str = ".claude/skills"


@dataclass
class WorkspaceConfig:
    temp_dir: str = "temp_workspace"
    work_dir: str = "temp_workspace/work"
    logs_dir: str = "temp_workspace/logs"


@dataclass
class MCPConfig:
    enabled: bool = True
    servers: list = None

    def __post_init__(self):
        if self.servers is None:
            self.servers = []


@dataclass
class Config:
    server: ServerConfig
    claude: ClaudeConfig
    project: ProjectConfig
    workspace: WorkspaceConfig
    mcp: MCPConfig


def load_config() -> Config:
    """Load configuration, with local.yaml overriding config.yaml"""

    # Load default config
    config_file = PROJECT_ROOT / "config.yaml"
    config_data: Dict[str, Any] = {}

    if config_file.exists():
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f) or {}

    # Override with local config if exists
    local_config_file = PROJECT_ROOT / "local.yaml"
    if local_config_file.exists():
        with open(local_config_file, 'r') as f:
            local_data = yaml.safe_load(f) or {}
            # Merge configs (local overrides default)
            for key, value in local_data.items():
                if key in config_data and isinstance(config_data[key], dict) and isinstance(value, dict):
                    config_data[key].update(value)
                else:
                    config_data[key] = value

    # Build Config dataclass
    server_cfg = ServerConfig(**config_data.get('server', {}))
    claude_cfg = ClaudeConfig(**config_data.get('claude', {}))
    project_cfg = ProjectConfig(**config_data.get('project', {}))
    workspace_cfg = WorkspaceConfig(**config_data.get('workspace', {}))
    mcp_cfg = MCPConfig(**config_data.get('mcp', {}))

    return Config(server=server_cfg, claude=claude_cfg, project=project_cfg, workspace=workspace_cfg, mcp=mcp_cfg)


def get_config() -> Config:
    """Get cached config instance"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


_config: Optional[Config] = None


# Alias for backward compatibility
settings = get_config()
