"""
Claude Code Service - Invokes Claude Code CLI for agent responses
Can also use Anthropic SDK directly via claude_sdk module
"""

import subprocess
import json
import os
import logging
from pathlib import Path
from typing import Dict, Generator, List, Optional
import asyncio
import os.path
import warnings

from src.config import get_config
from src.services.claude_sdk import get_claude_sdk_service, ClaudeSDKService

logger = logging.getLogger("MAS.ClaudeCode")

# Path to the project .claude directory
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CLAUDE_DIR = PROJECT_ROOT / "claude"

# Claude Code session environment directory
CLAUDE_SESSION_ENV_DIR = Path.home() / ".claude" / "session-env"


def _cleanup_session(session_id: str) -> None:
    """Clean up session directory when explicitly requested (not on every invocation)"""
    # NOTE: Session cleanup is now handled explicitly by the session management layer
    # Do NOT automatically clean up sessions here - we want to preserve conversation history
    pass


class ClaudeCodeService:
    """Service to invoke Claude Code CLI or SDK"""

    def __init__(self, project_dir: str = None, use_sdk: bool = True):
        config = get_config()

        # Use temp_workspace as default project directory
        project_root = Path(__file__).parent.parent.parent.parent
        default_workspace = project_root / config.workspace.temp_dir

        self.project_dir = project_dir or str(default_workspace)
        self.claude_dir = (PROJECT_ROOT / config.project.claude_dir).resolve()
        self.claude_cli = os.path.expanduser(config.claude.cli_path)
        self.timeout = config.claude.timeout
        self.default_model = config.claude.model
        self.api_key = config.claude.api_key
        self.use_sdk = use_sdk

        # MCP configuration
        self.mcp_enabled = config.mcp.enabled if hasattr(config, 'mcp') else True
        self.mcp_servers = config.mcp.servers if hasattr(config, 'mcp') else []

        # Initialize SDK service if enabled
        self.sdk_service: Optional[ClaudeSDKService] = None
        if self.use_sdk:
            try:
                self.sdk_service = get_claude_sdk_service()
                logger.info("[ClaudeCode] SDK mode enabled")
            except Exception as e:
                logger.warning(f"[ClaudeCode] Failed to initialize SDK: {e}, falling back to CLI")

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

    def _load_local_env(self) -> dict:
        """Load environment variables from local.yaml config"""
        config = get_config()
        env_vars = {}

        # Load from local.yaml env section
        if hasattr(config, 'mcp') and config.mcp.servers:
            # Check each server for API keys
            for server in config.mcp.servers:
                if server.get("type") == "tavily":
                    # Try to get from local.yaml env
                    env_vars["TAVILY_API_KEY"] = "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"

        return env_vars

    def _test_mcp_server(self, server_config: dict) -> bool:
        """Test if Claude Code CLI can communicate with MCP server"""
        import subprocess

        # Write temp MCP config
        import tempfile
        import json

        mcp_config = [server_config]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(mcp_config, f)
            mcp_config_path = f.name

        try:
            # Test CLI with MCP config using a simple prompt with short timeout
            cmd = [
                self.claude_cli,
                "-p",
                "--print",
                "--dangerously-skip-permissions",
                "--mcp-config", mcp_config_path,
                "--model", self.default_model,
                "Hi"
            ]

            env = os.environ.copy()
            env.update(server_config.get("env", {}))
            if self.api_key:
                env["ANTHROPIC_API_KEY"] = self.api_key

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.project_dir,
                env=env
            )

            try:
                stdout, stderr = proc.communicate(timeout=10)
                # If we get any response, the MCP integration works
                if proc.returncode == 0 and stdout:
                    logger.info(f"[ClaudeCode] MCP server {server_config.get('name')} CLI test passed")
                    return True
                else:
                    logger.warning(f"[ClaudeCode] MCP server {server_config.get('name')} CLI test failed: returncode={proc.returncode}")
                    return False
            except subprocess.TimeoutExpired:
                proc.kill()
                logger.warning(f"[ClaudeCode] MCP server {server_config.get('name')} CLI test timed out")
                return False
        except Exception as e:
            logger.warning(f"[ClaudeCode] MCP server {server_config.get('name')} test failed: {e}")
            return False
        finally:
            import os as os_module
            os_module.unlink(mcp_config_path)

    def _build_mcp_config(self) -> str:
        """Build MCP server configuration and save to file, return file path"""
        if not self.mcp_enabled or not self.mcp_servers:
            logger.info("[ClaudeCode] MCP disabled or no servers configured")
            return None

        # Load environment variables from local.yaml
        local_env = self._load_local_env()

        mcp_config = []
        for server in self.mcp_servers:
            if server.get("type") == "tavily":
                api_key = local_env.get("TAVILY_API_KEY")
                if api_key:
                    server_config = {
                        "name": "tavily",
                        "command": "npx",
                        "args": ["-y", "tavily-mcp"],
                        "env": {
                            "TAVILY_API_KEY": api_key
                        }
                    }

                    # Test if MCP server is working before adding to config
                    logger.info(f"[ClaudeCode] Testing MCP server: tavily")
                    if self._test_mcp_server(server_config):
                        mcp_config.append(server_config)
                        logger.info(f"[ClaudeCode] MCP server tavily passed health check")
                    else:
                        logger.warning(f"[ClaudeCode] MCP server tavily failed health check, skipping")

        if not mcp_config:
            logger.warning("[ClaudeCode] No working MCP servers, disabling MCP for this request")
            return None

        if mcp_config:
            config_json = json.dumps(mcp_config)
            logger.info(f"[ClaudeCode] MCP config: {config_json[:200]}...")

            # Write to temp file
            mcp_config_file = Path(self.project_dir) / "mcp_config.json"
            mcp_config_file.write_text(config_json)
            logger.info(f"[ClaudeCode] MCP config written to: {mcp_config_file}")

            return str(mcp_config_file)

        return None

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

        # Build MCP tools context
        mcp_tools_context = ""
        if self.mcp_enabled and self.mcp_servers:
            mcp_tools = []
            for server in self.mcp_servers:
                if server.get("type") == "tavily":
                    mcp_tools.extend(["tavily_search", "tavily_search_sublinks"])
            if mcp_tools:
                mcp_tools_context = f"\n## Available MCP Tools\nYou have access to the following search tools: {', '.join(mcp_tools)}\nUse these tools when you need to search the web for information."

        # Build system prompt with MAS context
        system_prompt = f"""You are running in the Multi-Agent Scientific (MAS) Operating System.
Your role is: {agent_type.upper()}

{agent_def}

## Current Task
User message: {message}
{skills_context}
{mcp_tools_context}

## Instructions
1. Respond as the {agent_type} agent following its defined cognitive style
2. Use the skills available in {self.claude_dir}/skills/ when appropriate
3. If you need to search the web, use the available MCP search tools (tavily_search, tavily_search_sublinks)
4. If you need to perform actions, you may use available tools
5. Write any outputs to the file system in appropriate directories

Respond now as the {agent_type} agent:"""

        return system_prompt

    def invoke(self, message: str, agent_type: str = "principal",
               model: str = None, session_id: str = None,
               skills: List[str] = None,
               history: List[dict] = None) -> str:
        """Invoke Claude Code CLI or SDK and return response"""

        # Use SDK if available
        if self.use_sdk and self.sdk_service:
            return self.sdk_service.invoke(
                message=message,
                agent_type=agent_type,
                model=model,
                session_id=session_id,
                skills=skills,
                history=history,
            )

        # Fallback to CLI
        return self._invoke_cli(message, agent_type, model, session_id, skills)

    def _invoke_cli(self, message: str, agent_type: str = "principal",
                    model: str = None, session_id: str = None,
                    skills: List[str] = None) -> str:
        """Invoke Claude Code CLI (fallback method)"""
        # Clean up existing session before creating new one
        _cleanup_session(session_id)

        model = model or self.default_model

        # Enhanced logging for invocation
        logger.info(f"[ClaudeCode] ===== INVOCATION START (CLI) =====")
        logger.info(f"[ClaudeCode] Agent: {agent_type}, Model: {model}, Session: {session_id}")
        logger.info(f"[ClaudeCode] Skills: {skills}")
        logger.info(f"[ClaudeCode] Message: {message[:200]}...")

        system_prompt = self._build_system_prompt(agent_type, message, skills)

        cmd = [
            self.claude_cli,
            "-p",
            "--print",
            "--debug", "mcp",
            "--output-format", "text",
            "--add-dir", str(self.claude_dir),
            "--setting-sources", "project",
            "--model", model,
            "--system-prompt", system_prompt,
        ]

        # Add session_id flag for Global Memory
        if session_id:
            cmd.extend(["--session-id", session_id])

        # Add MCP config if enabled
        mcp_config = self._build_mcp_config()
        if mcp_config:
            cmd.extend(["--mcp-config", mcp_config])

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
                logger.error(f"[ClaudeCode] ===== INVOCATION FAILED =====")
                logger.error(f"[ClaudeCode] Error: {result.stderr[:500] if result.stderr else 'Unknown'}")
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

            logger.info(f"[ClaudeCode] ===== INVOCATION SUCCESS =====")
            logger.info(f"[ClaudeCode] Response length: {len(result.stdout)}")
            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            logger.error("[ClaudeCode] Request timed out")
            return "Error: Request timed out (120s limit)"
        except Exception as e:
            logger.error(f"[ClaudeCode] Exception: {str(e)}", exc_info=True)
            return f"Error: {str(e)}"

    def invoke_streaming(self, message: str, agent_type: str = "principal",
                          model: str = None, session_id: str = None,
                          skills: List[str] = None,
                          history: List[dict] = None) -> Generator[Dict, None, None]:
        """Invoke Claude Code CLI or SDK with streaming output.

        Yields structured event dicts:
            {"type": "text", "text": "..."}
            {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
            {"type": "tool_result", "tool_use_id": "...", "content": "...", "is_error": bool}
        """
        # Use SDK if available
        if self.use_sdk and self.sdk_service:
            yield from self.sdk_service.invoke_streaming(
                message=message,
                agent_type=agent_type,
                model=model,
                session_id=session_id,
                skills=skills,
                history=history,
            )
            return

        # Fallback to CLI (wraps plain text in event format)
        for text in self._invoke_streaming_cli(message, agent_type, model, session_id, skills):
            yield {"type": "text", "text": text}

    def _invoke_streaming_cli(self, message: str, agent_type: str = "principal",
                              model: str = None, session_id: str = None,
                              skills: List[str] = None) -> Generator[str, None, None]:
        """Invoke Claude Code CLI with streaming output (fallback method)"""
        # Clean up existing session before creating new one
        _cleanup_session(session_id)

        model = model or self.default_model

        system_prompt = self._build_system_prompt(agent_type, message, skills)

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
        ]

        # Add session_id flag for Global Memory
        if session_id:
            cmd.extend(["--session-id", session_id])

        # Add MCP config if enabled
        mcp_config = self._build_mcp_config()
        if mcp_config:
            cmd.extend(["--mcp-config", mcp_config])

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
