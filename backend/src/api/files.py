# backend/src/api/files.py
"""
DEPRECATED: 此 API 已废弃，请使用 Claude Code 工具进行文件操作。
- Read: 读取文件
- Glob: 搜索文件
- Grep: 内容搜索
- Edit: 编辑文件
- Write: 写入文件

保留此 API 仅用于向后兼容。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from src.services.file_manager import list_files, read_file, write_file, upload_file

router = APIRouter()

class FileWriteRequest(BaseModel):
    path: str
    content: str

class FileUploadRequest(BaseModel):
    path: str
    content: str  # base64 encoded

@router.get("/files")
async def list_files_api(path: str = ""):
    """List files in workspace"""
    files = list_files(path)
    return {"files": files, "path": path}

@router.get("/files/{path:path}")
async def read_file_api(path: str):
    """Read file content"""
    try:
        content = read_file(path)
        return {"path": path, "content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")

@router.post("/files")
async def write_file_api(request: FileWriteRequest):
    """Write file content"""
    success = write_file(request.path, request.content)
    return {"success": success, "path": request.path}

@router.post("/files/upload")
async def upload_file_api(request: FileUploadRequest):
    """Upload file"""
    success = upload_file(request.path, request.content)
    return {"success": success, "path": request.path}


@router.get("/browse-filesystem")
async def browse_filesystem(path: str = ""):
    """Browse filesystem for folder suggestions"""
    import os
    from pathlib import Path

    # Handle ~ expansion
    if path.startswith("~"):
        path = os.path.expanduser(path)

    # If path is empty or doesn't exist, start from home
    if not path or not Path(path).exists():
        path = os.path.expanduser("~")

    base_path = Path(path)

    # If it's a file, get parent directory
    if base_path.is_file():
        base_path = base_path.parent

    suggestions = []
    try:
        if base_path.exists() and base_path.is_dir():
            for item in sorted(base_path.iterdir()):
                if item.is_dir() and not item.name.startswith('.'):
                    suggestions.append({
                        "name": item.name,
                        "path": str(item),
                        "type": "directory"
                    })
    except PermissionError:
        pass

    return {
        "path": str(base_path),
        "suggestions": suggestions[:20]  # Limit to 20 suggestions
    }
