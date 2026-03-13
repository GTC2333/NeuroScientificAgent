"""
Chat API - Handles message exchanges with the agent team
Uses Claude Code CLI for actual agent responses
"""

import asyncio
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import json
import os

from src.services.claude_code import get_claude_service

logger = logging.getLogger("MAS.Chat")
router = APIRouter()


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = None
    agent_type: Optional[str] = None  # principal, theorist, experimentalist, analyst, writer
    session_id: Optional[str] = None  # For Global Memory
    selected_skills: Optional[List[str]] = None  # Skills selected for this session


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
    logger.info(f"[chat] ===== REQUEST DETAILS =====")
    logger.info(f"[chat] Agent: {agent_type}")
    logger.info(f"[chat] Message: {request.message[:100]}...")
    logger.info(f"[chat] History length: {len(request.history) if request.history else 0}")

    # Get Claude Code service
    claude_service = get_claude_service()

    # Invoke Claude Code CLI
    try:
        logger.info(f"[chat] Invoking Claude Code for {agent_type}...")
        logger.info(f"[chat] Call stack: src.api.chat.chat()")
        history_dicts = None
        if request.history:
            history_dicts = [{"role": m.role, "content": m.content} for m in request.history]
        response_text = claude_service.invoke(
            message=request.message,
            agent_type=agent_type,
            session_id=request.session_id,
            skills=request.selected_skills,
            history=history_dicts
        )
        logger.info(f"[chat] Response received, length: {len(response_text)}")
        logger.info(f"[chat] Response content: {response_text[:300]}")
    except Exception as e:
        logger.error(f"[chat] ===== EXCEPTION DETAILS =====")
        logger.error(f"[chat] Exception type: {type(e).__name__}")
        logger.error(f"[chat] Exception message: {str(e)}")
        logger.error(f"[chat] Exception location: src.api.chat.chat()")
        logger.error(f"[chat] Stack trace:", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Claude Code error: {str(e)}")

    return ChatResponse(
        reply=response_text,
        agent_type=agent_type,
        task_id=None
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat response from Claude Code"""
    agent_type = request.agent_type or "principal"
    logger.info(f"[chat/stream] Agent: {agent_type}, Message: {request.message[:50]}...")

    claude_service = get_claude_service()

    async def generate():
        try:
            history_dicts = None
            if request.history:
                history_dicts = [{"role": m.role, "content": m.content} for m in request.history]
            for chunk in claude_service.invoke_streaming(
                message=request.message,
                agent_type=agent_type,
                session_id=request.session_id,
                skills=request.selected_skills,
                history=history_dicts
            ):
                yield f"data: {json.dumps({'text': chunk})}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"
            logger.info(f"[chat/stream] Stream completed for {agent_type}")
        except Exception as e:
            logger.error(f"[chat/stream] Error: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
