# backend/src/services/file_manager.py
import os
import shutil
from pathlib import Path
from typing import List, Dict
import base64

WORKSPACE_DIR = Path(__file__).parent.parent.parent.parent / "temp_workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

def list_files(path: str = "") -> List[Dict]:
    """List files in workspace"""
    target_dir = WORKSPACE_DIR / path if path else WORKSPACE_DIR
    if not target_dir.exists():
        return []

    files = []
    for item in target_dir.iterdir():
        files.append({
            "name": item.name,
            "type": "directory" if item.is_dir() else "file",
            "size": item.stat().st_size if item.is_file() else 0,
            "modified": item.stat().st_mtime,
        })
    return sorted(files, key=lambda x: (x["type"], x["name"]))

def read_file(path: str) -> str:
    """Read file content"""
    file_path = WORKSPACE_DIR / path
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return file_path.read_text(encoding='utf-8')

def write_file(path: str, content: str) -> bool:
    """Write file content"""
    try:
        file_path = WORKSPACE_DIR / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        return True
    except Exception as e:
        print(f"Failed to write file: {e}")
        return False

def upload_file(path: str, content: str) -> bool:
    """Upload file (content base64 encoded)"""
    try:
        file_path = WORKSPACE_DIR / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        data = base64.b64decode(content)
        file_path.write_bytes(data)
        return True
    except Exception as e:
        print(f"Failed to upload file: {e}")
        return False
