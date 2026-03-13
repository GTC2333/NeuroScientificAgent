"""
Session Manager - Manages sessions within sandboxes
Each session = conversation with Claude
"""
import json
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger("MAS.Session")

DATA_DIR = Path(__file__).parent.parent.parent / "data"
SESSIONS_FILE = DATA_DIR / "sessions.json"


def _load_sessions() -> Dict:
    if SESSIONS_FILE.exists():
        with open(SESSIONS_FILE, 'r') as f:
            return json.load(f)
    return {}


def _save_sessions(sessions: Dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SESSIONS_FILE, 'w') as f:
        json.dump(sessions, f, indent=2)


def create_session(sandbox_id: str, title: str = None, user_id: str = None) -> Dict:
    """Create new session in sandbox"""
    session_id = str(uuid.uuid4())

    session = {
        "id": session_id,
        "sandbox_id": sandbox_id,
        "user_id": user_id,
        "title": title or f"Session-{len(_load_sessions()) + 1}",
        "messages": [],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }

    sessions = _load_sessions()
    sessions[session_id] = session
    _save_sessions(sessions)

    logger.info(f"[Session] Created: {session_id} in sandbox {sandbox_id}")
    return session


def get_session(session_id: str) -> Optional[Dict]:
    """Get session by ID"""
    sessions = _load_sessions()
    return sessions.get(session_id)


def list_sandbox_sessions(sandbox_id: str) -> List[Dict]:
    """List all sessions in sandbox"""
    sessions = _load_sessions()
    return [s for s in sessions.values() if s.get('sandbox_id') == sandbox_id]


def list_user_sessions(user_id: str) -> List[Dict]:
    """List all sessions for user"""
    sessions = _load_sessions()
    return [s for s in sessions.values() if s.get('user_id') == user_id]


def add_message(session_id: str, role: str, content: str) -> Optional[Dict]:
    """Add message to session"""
    sessions = _load_sessions()
    if session_id not in sessions:
        return None

    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat()
    }

    sessions[session_id]["messages"].append(message)
    sessions[session_id]["updated_at"] = datetime.utcnow().isoformat()
    _save_sessions(sessions)

    return sessions[session_id]


def update_session(session_id: str, updates: Dict) -> Optional[Dict]:
    """Update session"""
    sessions = _load_sessions()
    if session_id not in sessions:
        return None

    sessions[session_id].update(updates)
    sessions[session_id]['updated_at'] = datetime.utcnow().isoformat()
    _save_sessions(sessions)
    return sessions[session_id]


def delete_session(session_id: str) -> bool:
    """Delete session"""
    sessions = _load_sessions()
    if session_id not in sessions:
        return False

    del sessions[session_id]
    _save_sessions(sessions)
    logger.info(f"[Session] Deleted: {session_id}")
    return True


def verify_session_access(session_id: str, user_id: str) -> bool:
    """Verify user has access to session"""
    from src.services.sandbox_service import get_sandbox_service

    session = get_session(session_id)
    if not session:
        return False
    service = get_sandbox_service()
    return service.verify_access(session['sandbox_id'], user_id)
