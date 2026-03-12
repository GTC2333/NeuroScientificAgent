"""
Claude SDK Service - Agentic loop with tool execution.
Uses Anthropic Python SDK with streaming + tool definitions.
Yields structured events for WebSocket consumption.
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Generator, List, Optional, Any

from anthropic import Anthropic

from src.config import get_config
from src.services.tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger("MAS.ClaudeSDK")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CLAUDE_DIR = PROJECT_ROOT / ".claude"

MAX_TOOL_ITERATIONS = 30  # Safety limit to prevent infinite loops

MODEL_ALIASES = {
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-20250514",
    "haiku": "claude-haiku-4-20250514",
}


def resolve_model(model: str) -> str:
    return MODEL_ALIASES.get(model, model)


class ClaudeSDKService:
    """Service to invoke Claude with agentic tool execution loop."""

    def __init__(self, project_dir: str = None):
        config = get_config()
        project_root = Path(__file__).parent.parent.parent.parent
        default_workspace = project_root / config.workspace.temp_dir

        self.project_dir = project_dir or str(default_workspace)
        self.claude_dir = (PROJECT_ROOT / config.project.claude_dir).resolve()
        self.default_model = config.claude.model
        self.api_key = config.claude.api_key
        self.timeout = config.claude.timeout
        self.max_tokens = 16384

        # MCP configuration
        self.mcp_enabled = config.mcp.enabled if hasattr(config, 'mcp') else True
        self.mcp_servers = config.mcp.servers if hasattr(config, 'mcp') else []

        # Load env vars from settings.local.json
        env_vars = self._load_settings_env()
        for k, v in env_vars.items():
            os.environ.setdefault(k, v)

        if "ANTHROPIC_MODEL" in env_vars:
            self.default_model = env_vars["ANTHROPIC_MODEL"]

        # Initialize Anthropic client
        client_kwargs = {"max_retries": 3}
        auth_token = env_vars.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        base_url = env_vars.get("ANTHROPIC_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL")
        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")

        if auth_token:
            client_kwargs["auth_token"] = auth_token
        elif api_key:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = Anthropic(**client_kwargs)
        logger.info("[ClaudeSDK] Initialized with model: %s, base_url: %s",
                     self.default_model, base_url or "default")

    def _load_settings_env(self) -> dict:
        settings_file = self.claude_dir / "settings.local.json"
        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    return settings.get("env", {})
            except Exception as e:
                logger.warning(f"[ClaudeSDK] Failed to load settings: {e}")
        return {}

    def _load_agent_prompt(self, agent_type: str) -> str:
        agent_file = self.claude_dir / "agents" / f"{agent_type}.md"
        if agent_file.exists():
            return agent_file.read_text()
        return ""

    def _build_system_prompt(self, agent_type: str) -> str:
        """Build system prompt (without embedding the user message)."""
        agent_def = self._load_agent_prompt(agent_type)

        mcp_tools_context = ""
        if self.mcp_enabled and self.mcp_servers:
            mcp_tools = [s.get("type") for s in self.mcp_servers]
            if mcp_tools:
                mcp_tools_context = f"\n## Available MCP Tools\n{', '.join(mcp_tools)}"

        return f"""You are running in the Multi-Agent Scientific (MAS) Operating System.
Your role: {agent_type.upper()}

{agent_def}

You have access to tools: Bash, Read, Write, Edit, Glob, Grep.
Use tools to complete tasks. Write outputs to the file system.
Working directory: {self.project_dir}
{mcp_tools_context}
"""

    def invoke(self, message: str, agent_type: str = "principal",
               model: str = None, session_id: str = None,
               skills: List[str] = None, history: List[dict] = None) -> str:
        """Non-streaming invocation with tool loop. Returns final text."""
        events = list(self.invoke_streaming(
            message=message, agent_type=agent_type, model=model,
            session_id=session_id, skills=skills, history=history,
        ))
        # Collect all text events
        return "".join(
            e.get("text", "") for e in events if e.get("type") == "text"
        )

    def invoke_streaming(self, message: str, agent_type: str = "principal",
                         model: str = None, session_id: str = None,
                         skills: List[str] = None,
                         history: List[dict] = None) -> Generator[Dict[str, Any], None, None]:
        """Streaming invocation with agentic tool execution loop.

        Yields structured events:
            {"type": "text", "text": "chunk"}
            {"type": "tool_use", "id": "...", "name": "Bash", "input": {...}}
            {"type": "tool_result", "tool_use_id": "...", "content": "...", "is_error": false}
            {"type": "status", "message": "Executing Bash..."}
            {"type": "error", "message": "..."}
        """
        model = resolve_model(model or self.default_model)
        system_prompt = self._build_system_prompt(agent_type)

        # Build messages array from history + current message
        messages = []
        if history:
            for msg in history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        logger.info(f"[ClaudeSDK] Agentic loop start: model={model}, history={len(messages)-1} msgs")

        for iteration in range(MAX_TOOL_ITERATIONS):
            logger.info(f"[ClaudeSDK] --- Iteration {iteration + 1} ---")

            try:
                # Call API with streaming and tool definitions
                assistant_content_blocks = []
                current_tool_use = None

                with self.client.messages.stream(
                    model=model,
                    max_tokens=self.max_tokens,
                    system=system_prompt,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                ) as stream:
                    for event in stream:
                        # Handle different stream event types
                        if event.type == "content_block_start":
                            block = event.content_block
                            if block.type == "tool_use":
                                current_tool_use = {
                                    "id": block.id,
                                    "name": block.name,
                                    "input_json": "",
                                }
                            elif block.type == "text":
                                pass  # Text will come via deltas

                        elif event.type == "content_block_delta":
                            delta = event.delta
                            if delta.type == "text_delta":
                                yield {"type": "text", "text": delta.text}
                            elif delta.type == "input_json_delta":
                                if current_tool_use is not None:
                                    current_tool_use["input_json"] += delta.partial_json

                        elif event.type == "content_block_stop":
                            if current_tool_use is not None:
                                # Parse accumulated tool input JSON
                                try:
                                    tool_input = json.loads(current_tool_use["input_json"]) \
                                        if current_tool_use["input_json"] else {}
                                except json.JSONDecodeError:
                                    tool_input = {}
                                    logger.error(f"[ClaudeSDK] Failed to parse tool input: {current_tool_use['input_json'][:200]}")

                                tool_block = {
                                    "type": "tool_use",
                                    "id": current_tool_use["id"],
                                    "name": current_tool_use["name"],
                                    "input": tool_input,
                                }
                                assistant_content_blocks.append(tool_block)
                                # Yield tool_use event to frontend
                                yield tool_block
                                current_tool_use = None

                    # Get the final message for stop_reason and text blocks
                    final_message = stream.get_final_message()

                # Collect text blocks from final message
                for block in final_message.content:
                    if block.type == "text" and block.text:
                        assistant_content_blocks.append({
                            "type": "text",
                            "text": block.text,
                        })

                # Add assistant message to conversation
                # Use the raw content from the final message for API compatibility
                messages.append({
                    "role": "assistant",
                    "content": [self._block_to_dict(b) for b in final_message.content],
                })

                # Check stop reason
                if final_message.stop_reason != "tool_use":
                    logger.info(f"[ClaudeSDK] Loop complete: stop_reason={final_message.stop_reason}")
                    break

                # Execute tools and collect results
                tool_uses = [b for b in assistant_content_blocks if b.get("type") == "tool_use"]
                tool_results = []
                for tool_use in tool_uses:
                    tool_name = tool_use["name"]
                    tool_id = tool_use["id"]
                    tool_input = tool_use["input"]

                    yield {"type": "status", "message": f"Executing {tool_name}..."}
                    logger.info(f"[ClaudeSDK] Executing tool: {tool_name}({json.dumps(tool_input)[:100]})")

                    result = execute_tool(tool_name, tool_input, cwd=self.project_dir)

                    tool_result_event = {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result["content"],
                        "is_error": result["is_error"],
                    }
                    yield tool_result_event

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result["content"],
                        "is_error": result.get("is_error", False),
                    })

                # Add tool results as user message (Anthropic API format)
                messages.append({"role": "user", "content": tool_results})

            except Exception as e:
                logger.error(f"[ClaudeSDK] Error in iteration {iteration + 1}: {e}", exc_info=True)
                yield {"type": "error", "message": str(e)}
                break
        else:
            yield {"type": "status", "message": f"Reached max iterations ({MAX_TOOL_ITERATIONS})"}
            logger.warning(f"[ClaudeSDK] Hit max iterations limit")

    @staticmethod
    def _block_to_dict(block) -> dict:
        """Convert an Anthropic SDK content block to a dict for messages array."""
        if block.type == "text":
            return {"type": "text", "text": block.text}
        elif block.type == "tool_use":
            return {
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            }
        return {"type": block.type}


_service: Optional[ClaudeSDKService] = None


def get_claude_sdk_service() -> ClaudeSDKService:
    global _service
    if _service is None:
        _service = ClaudeSDKService()
    return _service
