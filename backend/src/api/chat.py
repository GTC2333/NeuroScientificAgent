"""
Chat API - Handles message exchanges with the agent team
Uses Claude Code CLI for actual agent responses
"""

import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import json
import os

from src.services.claude_code import get_claude_service

router = APIRouter()


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = None
    agent_type: Optional[str] = None  # principal, theorist, experimentalist, analyst, writer


class ChatResponse(BaseModel):
    reply: str
    agent_type: str
    task_id: Optional[str] = None


# Simulated agent responses (replace with actual Claude Code integration)
AGENT_PERSONALITIES = {
    "principal": "You are the Principal Investigator. Coordinate the research team, validate hypotheses, and ensure scientific rigor.",
    "theorist": "You are the Theorist. Generate hypotheses, develop theoretical frameworks, and provide domain expertise.",
    "experimentalist": "You are the Experimentalist. Design experiments, implement protocols, and execute research tasks.",
    "analyst": "You are the Analyst. Analyze data, perform statistical tests, and extract insights.",
    "writer": "You are the Writer. Document findings, draft papers, and ensure clear communication."
}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to the agent team"""
    agent_type = request.agent_type or "principal"

    # Get Claude Code service
    claude_service = get_claude_service()

    # Invoke Claude Code CLI
    try:
        response_text = claude_service.invoke(
            message=request.message,
            agent_type=agent_type
        )
    except Exception as e:
        raise HTTPException(f"Claude Code error: {str(e)}")

    return ChatResponse(
        reply=response_text,
        agent_type=agent_type,
        task_id=None
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat response from Claude Code"""
    agent_type = request.agent_type or "principal"

    claude_service = get_claude_service()

    async def generate():
        for chunk in claude_service.invoke_streaming(
            message=request.message,
            agent_type=agent_type
        ):
            yield f"data: {json.dumps({'text': chunk})}\n\n"

        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
