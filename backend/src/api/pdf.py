"""
PDF API - PDF reading and searching endpoints
"""

import os
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from src.services.pdf_reader import read_pdf, search_pdf, extract_pdf_metadata

router = APIRouter()

# Project root path for security validation
PROJECT_ROOT = "/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system"


def validate_pdf_path(path: str) -> str:
    """Validate and resolve PDF path to prevent path traversal attacks"""
    # Get absolute path and resolve any symlinks
    abs_path = os.path.abspath(os.path.expanduser(path))

    # Allow paths in temp_workspace, project directory, or Downloads
    temp_dir = os.path.join(PROJECT_ROOT, "temp_workspace")
    downloads = os.path.expanduser("~/Downloads")

    allowed_dirs = [temp_dir, downloads, PROJECT_ROOT]

    for allowed in allowed_dirs:
        if abs_path.startswith(os.path.abspath(allowed) + os.sep):
            return abs_path

    # Also allow exact match for allowed directories themselves
    if any(abs_path == os.path.abspath(allowed) for allowed in allowed_dirs):
        return abs_path

    raise HTTPException(status_code=403, detail="Path not allowed - must be within temp_workspace, project directory, or Downloads")


class PDFReadRequest(BaseModel):
    path: str
    max_pages: int = 50

class PDFSearchRequest(BaseModel):
    path: str
    query: str


@router.post("/pdf/read")
async def read_pdf_endpoint(request: PDFReadRequest):
    """Read PDF and extract text"""
    # Issue #1: Path traversal validation
    validated_path = validate_pdf_path(request.path)

    # Issue #2: File type validation
    if not validated_path.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files supported")

    # Issue #4: Error handling - check file exists after validation
    if not os.path.exists(validated_path):
        raise HTTPException(status_code=404, detail="File not found")

    result = read_pdf(validated_path, request.max_pages)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/pdf/search")
async def search_pdf_endpoint(request: PDFSearchRequest):
    """Search for query in PDF"""
    # Issue #1: Path traversal validation
    validated_path = validate_pdf_path(request.path)

    # Issue #2: File type validation
    if not validated_path.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files supported")

    # Issue #4: Error handling - check file exists
    if not os.path.exists(validated_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Issue #5: Empty query validation
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    result = search_pdf(validated_path, request.query)
    return result


@router.get("/pdf/metadata")
async def metadata_endpoint(path: str = Query(..., description="PDF file path")):
    """Get PDF metadata"""
    # Issue #1: Path traversal validation
    validated_path = validate_pdf_path(path)

    # Issue #2: File type validation
    if not validated_path.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files supported")

    # Issue #4: Error handling - check file exists and handle errors
    if not os.path.exists(validated_path):
        raise HTTPException(status_code=404, detail="File not found")

    result = extract_pdf_metadata(validated_path)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
