# backend/src/services/session_store.py
import json
import os
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

SESSIONS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

def _get_session_file(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"

def save_session(session_id: str, data: Dict) -> bool:
    """Save session to file"""
    try:
        file_path = _get_session_file(session_id)
        data['saved_at'] = datetime.now().isoformat()
        file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return True
    except Exception as e:
        print(f"Failed to save session: {e}")
        return False

def load_session(session_id: str) -> Optional[Dict]:
    """Load session from file"""
    try:
        file_path = _get_session_file(session_id)
        if file_path.exists():
            return json.loads(file_path.read_text())
        return None
    except Exception as e:
        print(f"Failed to load session: {e}")
        return None

def list_sessions() -> List[Dict]:
    """List all saved sessions"""
    sessions = []
    for file_path in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(file_path.read_text())
            sessions.append({
                'id': data.get('id'),
                'title': data.get('title'),
                'createdAt': data.get('createdAt'),
                'updatedAt': data.get('updatedAt'),
                'saved_at': data.get('saved_at'),
            })
        except Exception:
            continue
    return sorted(sessions, key=lambda x: x.get('updatedAt', ''), reverse=True)

def delete_session(session_id: str) -> bool:
    """Delete session file"""
    try:
        file_path = _get_session_file(session_id)
        if file_path.exists():
            file_path.unlink()
        return True
    except Exception as e:
        print(f"Failed to delete session: {e}")
        return False
