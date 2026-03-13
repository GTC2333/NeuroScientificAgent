"""
Sandbox Agentic Loop - Standalone agentic loop for sandbox containers.
Extracted from backend/src/services/claude_sdk.py, no dependency on config.py.
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Generator, List, Optional, Any

from anthropic import Anthropic

from sandbox.tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger("Sandbox.AgenticLoop")

MAX_TOOL_ITERATIONS = 30

MODEL_ALIASES = {
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-20250514",
    "haiku": "claude-haiku-4-20250514",
}


def resolve_model(model: str) -> str:
    return MODEL_ALIASES.get(model, model)


class AgenticLoop:
    """Standalone agentic loop for sandbox containers."""

    def __init__(
        self,
        api_key: str = None,
        auth_token: str = None,
        base_url: str = None,
        model: str = "sonnet",
        workspace_dir: str = "/workspace",
        claude_dir: str = "/app/claude",
    ):
        self.workspace_dir = workspace_dir
        self.claude_dir = Path(claude_dir)
        self.default_model = model
        self.max_tokens = 16384

        # Initialize Anthropic client
        client_kwargs = {"max_retries": 3}

        auth_token = auth_token or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL")
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

        if auth_token:
            client_kwargs["auth_token"] = auth_token
        elif api_key:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = Anthropic(**client_kwargs)
        logger.info(
            "[AgenticLoop] Initialized: model=%s, base_url=%s, workspace=%s",
            self.default_model, base_url or "default", self.workspace_dir,
        )

    def _load_agent_prompt(self, agent_type: str) -> str:
        agent_file = self.claude_dir / "agents" / f"{agent_type}.md"
        if agent_file.exists():
            return agent_file.read_text()
        return ""

    def _build_system_prompt(self, agent_type: str) -> str:
        agent_def = self._load_agent_prompt(agent_type)
        return f"""You are running in the Multi-Agent Scientific (MAS) Operating System.
Your role: {agent_type.upper()}

{agent_def}

You have access to tools: Bash, Read, Write, Edit, Glob, Grep.
Use tools to complete tasks. Write outputs to the file system.
Working directory: {self.workspace_dir}
"""

    def invoke(self, message: str, agent_type: str = "principal",
               model: str = None, session_id: str = None,
               skills: List[str] = None, history: List[dict] = None) -> str:
        events = list(self.invoke_streaming(
            message=message, agent_type=agent_type, model=model,
            session_id=session_id, skills=skills, history=history,
        ))
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

        messages = []
        if history:
            for msg in history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        logger.info("[AgenticLoop] Start: model=%s, history=%d msgs", model, len(messages) - 1)

        for iteration in range(MAX_TOOL_ITERATIONS):
            logger.info("[AgenticLoop] --- Iteration %d ---", iteration + 1)

            try:
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
                        if event.type == "content_block_start":
                            block = event.content_block
                            if block.type == "tool_use":
                                current_tool_use = {
                                    "id": block.id,
                                    "name": block.name,
                                    "input_json": "",
                                }
                        elif event.type == "content_block_delta":
                            delta = event.delta
                            if delta.type == "text_delta":
                                yield {"type": "text", "text": delta.text}
                            elif delta.type == "input_json_delta":
                                if current_tool_use is not None:
                                    current_tool_use["input_json"] += delta.partial_json
                        elif event.type == "content_block_stop":
                            if current_tool_use is not None:
                                try:
                                    tool_input = json.loads(current_tool_use["input_json"]) \
                                        if current_tool_use["input_json"] else {}
                                except json.JSONDecodeError:
                                    tool_input = {}
                                    logger.error("[AgenticLoop] Bad tool input: %s",
                                                 current_tool_use["input_json"][:200])

                                tool_block = {
                                    "type": "tool_use",
                                    "id": current_tool_use["id"],
                                    "name": current_tool_use["name"],
                                    "input": tool_input,
                                }
                                assistant_content_blocks.append(tool_block)
                                yield tool_block
                                current_tool_use = None

                    final_message = stream.get_final_message()

                for block in final_message.content:
                    if block.type == "text" and block.text:
                        assistant_content_blocks.append({
                            "type": "text",
                            "text": block.text,
                        })

                messages.append({
                    "role": "assistant",
                    "content": [self._block_to_dict(b) for b in final_message.content],
                })

                if final_message.stop_reason != "tool_use":
                    logger.info("[AgenticLoop] Done: stop_reason=%s, usage=%s",
                                final_message.stop_reason,
                                getattr(final_message, 'usage', 'N/A'))
                    break

                # Execute tools
                tool_uses = [b for b in assistant_content_blocks if b.get("type") == "tool_use"]
                logger.info("[AgenticLoop] Iteration %d: %d tool(s) to execute",
                            iteration + 1, len(tool_uses))
                tool_results = []
                for tool_use in tool_uses:
                    tool_name = tool_use["name"]
                    tool_id = tool_use["id"]
                    tool_input = tool_use["input"]

                    yield {"type": "status", "message": f"Executing {tool_name}..."}
                    logger.info("[AgenticLoop] Executing: %s(%s)",
                                tool_name, json.dumps(tool_input)[:100])

                    result = execute_tool(tool_name, tool_input, cwd=self.workspace_dir)

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

                messages.append({"role": "user", "content": tool_results})

            except Exception as e:
                logger.error("[AgenticLoop] Error iteration %d: %s", iteration + 1, e, exc_info=True)
                yield {"type": "error", "message": str(e)}
                break
        else:
            yield {"type": "status", "message": f"Reached max iterations ({MAX_TOOL_ITERATIONS})"}

    @staticmethod
    def _block_to_dict(block) -> dict:
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
