import fitz  # PyMuPDF
from typing import Dict, List, Optional
import logging
import os

logger = logging.getLogger("MAS.PDFReader")

def read_pdf(path: str, max_pages: int = 50) -> Dict:
    """Extract text from PDF"""
    try:
        if not os.path.exists(path):
            return {"error": "File not found", "path": path}

        with fitz.open(path) as doc:  # Use context manager
            total_pages = len(doc)
            pages = []

            for i in range(min(total_pages, max_pages)):
                page = doc[i]
                text = page.get_text()
                pages.append({
                    "page": i + 1,
                    "text": text
                })

            return {
                "path": path,
                "total_pages": total_pages,
                "pages": pages
            }
    except Exception as e:
        logger.error(f"PDF read error: {e}")
        return {"error": str(e)}

def search_pdf(path: str, query: str) -> List[Dict]:
    """Search for query in PDF"""
    try:
        if not os.path.exists(path):
            return []

        with fitz.open(path) as doc:  # Use context manager
            results = []

            for page_num, page in enumerate(doc):
                text = page.get_text().lower()
                query_lower = query.lower()

                if query_lower in text:
                    # Find context around match
                    idx = text.find(query_lower)
                    start = max(0, idx - 100)
                    end = min(len(text), idx + len(query) + 100)
                    context = text[start:end]

                    results.append({
                        "page": page_num + 1,
                        "context": context
                    })

            return results
    except Exception as e:
        logger.error(f"PDF search error: {e}")
        return []

def extract_pdf_metadata(path: str) -> Dict:
    """Extract PDF metadata"""
    try:
        with fitz.open(path) as doc:  # Use context manager
            metadata = doc.metadata
            page_count = len(doc)
            return {
                "title": metadata.get("title", ""),
                "author": metadata.get("author", ""),
                "subject": metadata.get("subject", ""),
                "pages": page_count
            }
    except Exception as e:
        return {"error": str(e)}
