"""
Claude SDK Service - Uses Anthropic Python SDK
Inspired by claudecodeui's claude-sdk.js approach
"""
import os
import json
import logging
from pathlib import Path
from typing import Generator, List, Optional
from anthropic import Anthropic

from src.config import get_config

logger = logging.getLogger("MAS.ClaudeSDK")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CLAUDE_DIR = PROJECT_ROOT / ".claude"


class ClaudeSDKService:
    """Service to invoke Claude using Anthropic Python SDK"""

    def __init__(self, project_dir: str = None):
        config = get_config()

        project_root = Path(__file__).parent.parent.parent.parent
        default_workspace = project_root / config.workspace.temp_dir

        self.project_dir = project_dir or str(default_workspace)
        self.claude_dir = Path(config.project.claude_dir).resolve()
        self.default_model = config.claude.model
        self.api_key = config.claude.api_key
        self.timeout = config.claude.timeout
        self.max_tokens = min(self.timeout * 10, 8192)  # Estimate based on timeout

        # MCP configuration
        self.mcp_enabled = config.mcp.enabled if hasattr(config, 'mcp') else True
        self.mcp_servers = config.mcp.servers if hasattr(config, 'mcp') else []

        # Initialize SDK client
        self.client = Anthropic(
            api_key=self.api_key,
            max_retries=3,
        )
        logger.info("[ClaudeSDK] Initialized with model: %s", self.default_model)

    def _load_settings_env(self) -> dict:
        """Load environment variables from settings.local.json"""
        settings_file = self.claude_dir / "settings.local.json"
        env_vars = {}

        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    if "env" in settings:
                        env_vars = settings["env"]
            except Exception as e:
                logger.warning(f"[ClaudeSDK] Failed to load settings: {e}")

        return env_vars

    def _load_agent_prompt(self, agent_type: str) -> str:
        """Load agent definition from .claude/agents/"""
        agent_file = self.claude_dir / "agents" / f"{agent_type}.md"
        if agent_file.exists():
            return agent_file.read_text()
        return ""

    def _build_system_prompt(self, agent_type: str, message: str, skills: List[str] = None) -> str:
        """Build system prompt for agent"""
        agent_def = self._load_agent_prompt(agent_type)

        skills_context = ""
        if skills:
            skills_context = f"\n## Active Skills\nYou have access to: {', '.join(skills)}"

        mcp_tools_context = ""
        if self.mcp_enabled and self.mcp_servers:
            mcp_tools = [s.get("type") for s in self.mcp_servers]
            if mcp_tools:
                mcp_tools_context = f"\n## Available MCP Tools\n{', '.join(mcp_tools)}"

        return f"""You are running in the Multi-Agent Scientific (MAS) Operating System.
Your role: {agent_type.upper()}

{agent_def}

## Current Task
User: {message}
{skills_context}
{mcp_tools_context}

Respond as {agent_type}:"""

    def invoke(self, message: str, agent_type: str = "principal",
               model: str = None, session_id: str = None,
               skills: List[str] = None) -> str:
        """Non-streaming invocation"""
        model = model or self.default_model

        logger.info(f"[ClaudeSDK] Invoke: agent={agent_type}, model={model}")

        system_prompt = self._build_system_prompt(agent_type, message, skills)

        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": message}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"[ClaudeSDK] Error: {e}")
            return f"Error: {str(e)}"

    def invoke_streaming(self, message: str, agent_type: str = "principal",
                        model: str = None, session_id: str = None,
                        skills: List[str] = None) -> Generator[str, None, None]:
        """Streaming invocation"""
        model = model or self.default_model

        logger.info(f"[ClaudeSDK] Streaming: agent={agent_type}, model={model}")

        system_prompt = self._build_system_prompt(agent_type, message, skills)

        try:
            with self.client.messages.stream(
                model=model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": message}]
            ) as stream:
                for text in stream.text_stream:
                    if text:
                        yield text
        except Exception as e:
            logger.error(f"[ClaudeSDK] Stream error: {e}")
            yield f"Error: {str(e)}"


_service: Optional[ClaudeSDKService] = None


def get_claude_sdk_service() -> ClaudeSDKService:
    global _service
    if _service is None:
        _service = ClaudeSDKService()
    return _service
