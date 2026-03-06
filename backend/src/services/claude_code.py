"""
Claude Code Service - Invokes Claude Code CLI for agent responses
"""

import subprocess
import json
import os
from pathlib import Path
from typing import Generator, Optional
import asyncio
import os.path

from src.config import get_config

# Path to the project .claude directory
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CLAUDE_DIR = PROJECT_ROOT / ".claude"


class ClaudeCodeService:
    """Service to invoke Claude Code CLI"""

    def __init__(self, project_dir: str = None):
        config = get_config()

        # Use temp_workspace as default project directory
        project_root = Path(__file__).parent.parent.parent.parent
        default_workspace = project_root / config.workspace.temp_dir

        self.project_dir = project_dir or str(default_workspace)
        self.claude_dir = Path(config.project.claude_dir).resolve()
        self.claude_cli = os.path.expanduser(config.claude.cli_path)
        self.timeout = config.claude.timeout
        self.default_model = config.claude.model

    def _load_agent_prompt(self, agent_type: str) -> str:
        """Load agent definition from .claude/agents/"""
        agent_file = self.claude_dir / "agents" / f"{agent_type}.md"

        if agent_file.exists():
            return agent_file.read_text()
        return ""

    def _build_system_prompt(self, agent_type: str, message: str) -> str:
        """Build the full prompt for Claude Code"""
        # Load agent definition
        agent_def = self._load_agent_prompt(agent_type)

        # Build system prompt with MAS context
        system_prompt = f"""You are running in the Multi-Agent Scientific (MAS) Operating System.
Your role is: {agent_type.upper()}

{agent_def}

## Current Task
User message: {message}

## Instructions
1. Respond as the {agent_type} agent following its defined cognitive style
2. Use the skills available in {self.claude_dir}/skills/ when appropriate
3. If you need to perform actions, you may use available tools
4. Write any outputs to the file system in appropriate directories

Respond now as the {agent_type} agent:"""

        return system_prompt

    def invoke(self, message: str, agent_type: str = "principal",
               model: str = None) -> str:
        """Invoke Claude Code CLI and return response"""
        model = model or self.default_model

        system_prompt = self._build_system_prompt(agent_type, message)

        cmd = [
            self.claude_cli,
            "-p",
            "--print",
            "--output-format", "text",
            "--add-dir", str(self.claude_dir),
            "--setting-sources", "project",
            "--model", model,
            "--system-prompt", system_prompt,
            message
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.project_dir
            )

            if result.returncode != 0:
                error_msg = result.stderr or "Unknown error"
                # Filter out zprofile warnings
                error_lines = [l for l in error_msg.split('\n')
                              if 'zprofile' not in l and 'brew' not in l]
                return f"Error: {' '.join(error_lines)}"

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            return "Error: Request timed out (120s limit)"
        except Exception as e:
            return f"Error: {str(e)}"

    def invoke_streaming(self, message: str, agent_type: str = "principal",
                          model: str = None) -> Generator[str, None, None]:
        """Invoke Claude Code CLI with streaming output"""
        model = model or self.default_model

        system_prompt = self._build_system_prompt(agent_type, message)

        cmd = [
            self.claude_cli,
            "-p",
            "--print",
            "--output-format", "stream-json",
            "--include-partial-messages",
            "--add-dir", str(self.claude_dir),
            "--setting-sources", "project",
            "--model", model,
            "--system-prompt", system_prompt,
            message
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.project_dir
            )

            buffer = ""
            for char in iter(lambda: process.stdout.read(1), ''):
                if not char:
                    break

                buffer += char

                # Try to parse as JSON
                if buffer.endswith('}\n') or buffer.endswith('}\r\n'):
                    try:
                        data = json.loads(buffer)
                        if data.get('type') == 'content':
                            content = data.get('content', [])
                            for block in content:
                                if block.get('type') == 'text':
                                    yield block.get('text', '')
                        buffer = ""
                    except json.JSONDecodeError:
                        continue

            process.wait(timeout=self.timeout)

        except Exception as e:
            yield f"Error: {str(e)}"


# Singleton instance
_service: Optional[ClaudeCodeService] = None


def get_claude_service() -> ClaudeCodeService:
    """Get or create Claude Code service instance"""
    global _service
    if _service is None:
        _service = ClaudeCodeService()
    return _service
