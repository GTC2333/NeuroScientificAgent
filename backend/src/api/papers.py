"""
Papers API - Academic paper search and retrieval endpoints
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from src.services.paper_search import (
    search_papers, get_paper, get_paper_citations,
    get_paper_references, get_papers_batch, API_KEY
)

router = APIRouter()


# NOTE: Specific routes must come BEFORE parameterized routes (/papers/{paper_id})

@router.get("/papers/status")
async def papers_status():
    """Check API status and configuration"""
    return {
        "api_key_configured": bool(API_KEY),
        "rate_limit": "1 req/s (with API key)" if API_KEY else "shared (limited)"
    }


@router.get("/papers/search")
async def search_papers_endpoint(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    fields: str = Query("", description="Optional fields to return")
):
    """Search for academic papers"""
    results = search_papers(q, limit, offset, fields)
    return {"query": q, "count": len(results), "papers": results}


@router.get("/papers/batch")
async def papers_batch_endpoint(
    ids: str = Query(..., description="Comma-separated paper IDs"),
    fields: str = Query("", description="Optional fields to return")
):
    """Batch query multiple papers"""
    paper_ids = [pid.strip() for pid in ids.split(",") if pid.strip()]
    if not paper_ids:
        raise HTTPException(status_code=400, detail="No paper IDs provided")
    if len(paper_ids) > 100:
        raise HTTPException(status_code=400, detail="Max 100 papers per batch")

    results = get_papers_batch(paper_ids, fields)
    return {"count": len(results), "papers": results}


@router.get("/papers/{paper_id}")
async def get_paper_endpoint(
    paper_id: str,
    fields: str = Query("", description="Optional fields to return")
):
    """Get paper details by ID"""
    paper = get_paper(paper_id, fields)
    if paper and "error" not in paper:
        return paper
    if paper and paper.get("error"):
        raise HTTPException(status_code=400, detail=paper["error"])
    raise HTTPException(status_code=404, detail="Paper not found")


@router.get("/papers/{paper_id}/citations")
async def get_citations_endpoint(
    paper_id: str,
    limit: int = Query(10, ge=1, le=1000)
):
    """Get papers that cite this paper"""
    citations = get_paper_citations(paper_id, limit)
    return {"paper_id": paper_id, "count": len(citations), "citations": citations}


@router.get("/papers/{paper_id}/references")
async def get_references_endpoint(
    paper_id: str,
    limit: int = Query(10, ge=1, le=1000)
):
    """Get papers referenced by this paper"""
    references = get_paper_references(paper_id, limit)
    return {"paper_id": paper_id, "count": len(references), "references": references}
