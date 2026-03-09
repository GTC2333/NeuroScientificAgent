"""
Paper Search Service - Semantic Scholar API integration
Enhanced with API key support, rate limiting, and batch queries
"""

import os
import time
import requests
import json
from typing import List, Dict, Optional
import logging

logger = logging.getLogger("MAS.PaperSearch")

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"

# API Key support - get from environment or config
API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")

# Rate limiting
_last_request_time = 0
MIN_REQUEST_INTERVAL = 1.1 if API_KEY else 2.0  # 1 req/s with key, slower without


def _rate_limit():
    """Apply rate limiting between requests"""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def _make_request(url: str, params: Dict, max_retries: int = 3) -> Optional[Dict]:
    """
    Make request with rate limiting and retry logic for 429 errors

    Returns None on failure after retries
    """
    headers = {}
    if API_KEY:
        headers["x-api-key"] = API_KEY

    for attempt in range(max_retries):
        _rate_limit()

        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                # Rate limited - exponential backoff
                wait_time = (2 ** attempt) + 1
                logger.warning(f"Rate limited, waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                continue
            elif response.status_code == 401:
                logger.error("API key is invalid")
                return {"error": "invalid_api_key"}
            elif response.status_code == 403:
                logger.error("Access forbidden - check API key permissions")
                return {"error": "forbidden"}
            else:
                logger.error(f"API returned status {response.status_code}")
                response.raise_for_status()

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None

    return {"error": "max_retries_exceeded"}


def search_papers(query: str, limit: int = 10, offset: int = 0, fields: str = "") -> List[Dict]:
    """
    Search papers via Semantic Scholar API

    Args:
        query: Search query string
        limit: Max results (1-100)
        offset: Pagination offset
        fields: Comma-separated fields to return (optional, uses defaults if empty)
    """
    # Default fields if not specified
    if not fields:
        fields = "title,authors,year,abstract,citationCount,url,venue,openAccessPdf"

    url = f"{SEMANTIC_SCHOLAR_API}/paper/search"
    params = {
        "query": query,
        "limit": min(limit, 100),
        "offset": offset,
        "fields": fields
    }

    data = _make_request(url, params)
    if data and "data" in data:
        return data.get("data", [])
    return []


def get_paper(paper_id: str, fields: str = "") -> Optional[Dict]:
    """
    Get paper details by ID

    Args:
        paper_id: Semantic Scholar paper ID or DOI
        fields: Comma-separated fields to return (optional)
    """
    if not fields:
        fields = "title,authors,year,abstract,citationCount,references,url,openAccessPdf,venue"

    url = f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}"
    params = {"fields": fields}

    data = _make_request(url, params)
    return data


def get_paper_citations(paper_id: str, limit: int = 10) -> List[Dict]:
    """Get papers that cite the given paper"""
    url = f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}/citations"
    params = {
        "limit": min(limit, 1000),
        "fields": "title,authors,year,abstract,citationCount,url"
    }

    data = _make_request(url, params)
    if data and "data" in data:
        return [c.get("citingPaper", {}) for c in data.get("data", [])]
    return []


def get_paper_references(paper_id: str, limit: int = 10) -> List[Dict]:
    """Get papers referenced by the given paper"""
    url = f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}/references"
    params = {
        "limit": min(limit, 1000),
        "fields": "title,authors,year,abstract,citationCount,url"
    }

    data = _make_request(url, params)
    if data and "data" in data:
        return [c.get("citedPaper", {}) for c in data.get("data", [])]
    return []


def get_papers_batch(paper_ids: List[str], fields: str = "") -> List[Dict]:
    """
    Batch query multiple papers at once (more efficient than individual queries)

    Args:
        paper_ids: List of Semantic Scholar paper IDs
        fields: Comma-separated fields to return (optional)

    Returns:
        List of paper details
    """
    if not fields:
        fields = "title,authors,year,abstract,citationCount,url,venue"

    url = f"{SEMANTIC_SCHOLAR_API}/paper/batch"
    params = {
        "ids": ",".join(paper_ids),
        "fields": fields
    }

    data = _make_request(url, params)
    if data and "data" in data:
        return data.get("data", [])
    return []
