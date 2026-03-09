"""
PDF API - PDF reading and searching endpoints
"""

import os
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from src.services.pdf_reader import read_pdf, search_pdf, extract_pdf_metadata

router = APIRouter()

class PDFReadRequest(BaseModel):
    path: str
    max_pages: int = 50

class PDFSearchRequest(BaseModel):
    path: str
    query: str

@router.post("/pdf/read")
async def read_pdf_endpoint(request: PDFReadRequest):
    """Read PDF and extract text"""
    result = read_pdf(request.path, request.max_pages)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.post("/pdf/search")
async def search_pdf_endpoint(request: PDFSearchRequest):
    """Search for query in PDF"""
    if not os.path.exists(request.path):
        raise HTTPException(status_code=404, detail="File not found")
    return search_pdf(request.path, request.query)

@router.get("/pdf/metadata")
async def metadata_endpoint(path: str = Query(..., description="PDF file path")):
    """Get PDF metadata"""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return extract_pdf_metadata(path)
