"""
Claude Code Service - Invokes Claude Code CLI for agent responses
"""

import subprocess
import json
import os
import logging
from pathlib import Path
from typing import Generator, List, Optional
import asyncio
import os.path
import warnings

from src.config import get_config

logger = logging.getLogger("MAS.ClaudeCode")

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
        self.api_key = config.claude.api_key

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
                        logger.info(f"[ClaudeCode] Loaded {len(env_vars)} env vars from settings.local.json")
            except Exception as e:
                logger.warning(f"[ClaudeCode] Failed to load settings.local.json: {e}")

        return env_vars

    def _load_agent_prompt(self, agent_type: str) -> str:
        """Load agent definition from .claude/agents/"""
        agent_file = self.claude_dir / "agents" / f"{agent_type}.md"

        if agent_file.exists():
            return agent_file.read_text()
        return ""

    def _build_system_prompt(self, agent_type: str, message: str, skills: List[str] = None) -> str:
        """Build the full prompt for Claude Code"""
        # Load agent definition
        agent_def = self._load_agent_prompt(agent_type)

        # Build skills context
        skills_context = ""
        if skills:
            skills_list = ", ".join(skills)
            skills_context = f"\n## Active Skills\nYou have access to the following skills: {skills_list}"

        # Build system prompt with MAS context
        system_prompt = f"""You are running in the Multi-Agent Scientific (MAS) Operating System.
Your role is: {agent_type.upper()}

{agent_def}

## Current Task
User message: {message}
{skills_context}

## Instructions
1. Respond as the {agent_type} agent following its defined cognitive style
2. Use the skills available in {self.claude_dir}/skills/ when appropriate
3. If you need to perform actions, you may use available tools
4. Write any outputs to the file system in appropriate directories

Respond now as the {agent_type} agent:"""

        return system_prompt

    def invoke(self, message: str, agent_type: str = "principal",
               model: str = None, session_id: str = None,
               skills: List[str] = None) -> str:
        """Invoke Claude Code CLI and return response"""
        model = model or self.default_model

        system_prompt = self._build_system_prompt(agent_type, message, skills)

        cmd = [
            self.claude_cli,
            "-p",
            "--print",
            "--dangerously-skip-permissions",
            "--output-format", "text",
            "--add-dir", str(self.claude_dir),
            "--setting-sources", "project",
            "--model", model,
            "--system-prompt", system_prompt,
        ]

        # Add session_id flag for Global Memory
        if session_id:
            cmd.extend(["--session-id", session_id])

        # Message must be the last argument
        cmd.append(message)

        logger.info(f"[ClaudeCode] ===== INVOCATION DETAILS =====")
        logger.info(f"[ClaudeCode] CLI path: {self.claude_cli}")
        logger.info(f"[ClaudeCode] Project dir: {self.project_dir}")
        logger.info(f"[ClaudeCode] Claude dir: {self.claude_dir}")
        logger.info(f"[ClaudeCode] Model: {model}")
        logger.info(f"[ClaudeCode] Agent type: {agent_type}")
        logger.info(f"[ClaudeCode] Skills: {skills}")
        logger.info(f"[ClaudeCode] Full command: {cmd}")
        logger.info(f"[ClaudeCode] Message: {message[:100]}...")

        # Prepare environment: start with current env, then load from settings.local.json
        env = os.environ.copy()

        # Load settings from settings.local.json (third-party API config)
        settings_env = self._load_settings_env()
        env.update(settings_env)

        # Override with explicit API key if provided in local.yaml
        if self.api_key:
            env["ANTHROPIC_API_KEY"] = self.api_key

        # which API/endpoint is being Log used
        if env.get("ANTHROPIC_BASE_URL"):
            logger.info(f"[ClaudeCode] Using third-party API: {env.get('ANTHROPIC_BASE_URL')}")
        if env.get("ANTHROPIC_MODEL"):
            logger.info(f"[ClaudeCode] Model: {env.get('ANTHROPIC_MODEL')}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.project_dir,
                env=env
            )

            logger.info(f"[ClaudeCode] Return code: {result.returncode}")
            logger.info(f"[ClaudeCode] Stdout length: {len(result.stdout)}")
            logger.info(f"[ClaudeCode] Stderr length: {len(result.stderr)}")

            # 详细打印 stdout 和 stderr 内容（用于调试）
            if result.returncode != 0:
                logger.error(f"[ClaudeCode] ===== ERROR DETAILS =====")
                logger.error(f"[ClaudeCode] Return code: {result.returncode}")
                logger.error(f"[ClaudeCode] Stdout (first 500 chars): {result.stdout[:500] if result.stdout else '(empty)'}")
                logger.error(f"[ClaudeCode] Stderr (first 500 chars): {result.stderr[:500] if result.stderr else '(empty)'}")

                # 尝试从 stdout 获取错误信息（因为 stderr 可能为空）
                error_msg = result.stderr or result.stdout or "Unknown error"
                # 过滤掉 zprofile 警告
                error_lines = [l for l in error_msg.split('\n')
                              if 'zprofile' not in l.lower() and 'brew' not in l.lower() and l.strip()]
                error_text = f"Error: {' '.join(error_lines)}"
                logger.error(f"[ClaudeCode] CLI Error: {error_text}")
                return error_text

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            logger.error("[ClaudeCode] Request timed out")
            return "Error: Request timed out (120s limit)"
        except Exception as e:
            logger.error(f"[ClaudeCode] Exception: {str(e)}", exc_info=True)
            return f"Error: {str(e)}"

    def invoke_streaming(self, message: str, agent_type: str = "principal",
                          model: str = None, session_id: str = None,
                          skills: List[str] = None) -> Generator[str, None, None]:
        """Invoke Claude Code CLI with streaming output"""
        model = model or self.default_model

        system_prompt = self._build_system_prompt(agent_type, message, skills)

        cmd = [
            self.claude_cli,
            "-p",
            "--print",
            "--dangerously-skip-permissions",
            "--output-format", "stream-json",
            "--include-partial-messages",
            "--add-dir", str(self.claude_dir),
            "--setting-sources", "project",
            "--model", model,
            "--system-prompt", system_prompt,
        ]

        # Add session_id flag for Global Memory
        if session_id:
            cmd.extend(["--session-id", session_id])

        # Message must be the last argument
        cmd.append(message)

        # Prepare environment: load from settings.local.json
        env = os.environ.copy()
        settings_env = self._load_settings_env()
        env.update(settings_env)
        if self.api_key:
            env["ANTHROPIC_API_KEY"] = self.api_key

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.project_dir,
                env=env
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
