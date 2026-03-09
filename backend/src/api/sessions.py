# backend/src/api/sessions.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from src.services.session_store import save_session, load_session, list_sessions, delete_session

router = APIRouter()

class SessionSaveRequest(BaseModel):
    session_id: str
    title: str
    agents: List[str]
    skills: List[str]
    messages: List[Dict[str, Any]]
    createdAt: str
    updatedAt: str

class SessionResponse(BaseModel):
    success: bool
    session_id: Optional[str] = None

@router.post("/sessions")
async def save_session_endpoint(request: SessionSaveRequest):
    """Save session to backend"""
    data = request.dict()
    success = save_session(request.session_id, data)
    return SessionResponse(success=success, session_id=request.session_id if success else None)

@router.get("/sessions")
async def list_sessions_endpoint():
    """List all saved sessions"""
    sessions = list_sessions()
    return {"sessions": sessions}

@router.get("/sessions/{session_id}")
async def get_session_endpoint(session_id: str):
    """Get a specific session"""
    session = load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.delete("/sessions/{session_id}")
async def delete_session_endpoint(session_id: str):
    """Delete a session"""
    success = delete_session(session_id)
    return SessionResponse(success=success)
