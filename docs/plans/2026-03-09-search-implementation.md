# 搜索功能实现计划（跳过 Tavily）

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** 实现论文搜索能力，绕过 MCP（因 minimaxi 不支持 function calling）

**Architecture:** 后端 API 代理模式 - Semantic Scholar API 直接从 Python 后端调用

**Tech Stack:**
- Python后端 (FastAPI)
- Semantic Scholar API (论文搜索)
- PyMuPDF (PDF 解析)

---

## 问题背景

### MCP 无法使用的原因
- minimaxi API 不支持 MCP 协议所需的 **function calling (工具调用)** 功能
- 证据：MCP 初始化超时 120s，WebSearch 返回 `invalid params, function name or parameters is empty`
- 解决方案：使用后端 API 代理模式，不依赖 Claude Code 的 MCP

### 采用方案
- **后端 API 代理**: 后端 Python 直接调用搜索 API，绕过 MCP
- **保留 minimaxi**: 继续使用 minimaxi 作为 LLM API

---

## 任务列表

### Task 1: 实现 Semantic Scholar 论文搜索 API

**Files:**
- Create: `backend/src/services/paper_search.py`
- Modify: `backend/src/api/__init__.py` (注册路由)
- Test: API 端点

**Step 1: 创建 paper_search.py**

```python
# backend/src/services/paper_search.py
import requests
from typing import List, Dict, Optional
import logging

logger = logging.getLogger("MAS.PaperSearch")

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"

def search_papers(query: str, limit: int = 10, offset: int = 0) -> List[Dict]:
    """Search papers via Semantic Scholar API"""
    url = f"{SEMANTIC_SCHOLAR_API}/paper/search"
    params = {
        "query": query,
        "limit": min(limit, 100),
        "offset": offset,
        "fields": "title,authors,year,abstract,citationCount,url,venue,openAccessPdf"
    }
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    except Exception as e:
        logger.error(f"Paper search error: {e}")
        return []

def get_paper(paper_id: str) -> Optional[Dict]:
    """Get paper details by ID"""
    url = f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}"
    params = {
        "fields": "title,authors,year,abstract,citationCount,references,url,openAccessPdf,venue"
    }
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Get paper error: {e}")
        return None

def get_paper_citations(paper_id: str, limit: int = 10) -> List[Dict]:
    """Get citations for a paper"""
    url = f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}/citations"
    params = {
        "limit": min(limit, 1000),
        "fields": "title,authors,year,abstract,citationCount,url"
    }
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return [c.get("citingPaper", {}) for c in data.get("data", [])]
    except Exception as e:
        logger.error(f"Get citations error: {e}")
        return []

def get_paper_references(paper_id: str, limit: int = 10) -> List[Dict]:
    """Get references for a paper"""
    url = f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}/references"
    params = {
        "limit": min(limit, 1000),
        "fields": "title,authors,year,abstract,citationCount,url"
    }
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return [c.get("citedPaper", {}) for c in data.get("data", [])]
    except Exception as e:
        logger.error(f"Get references error: {e}")
        return []
```

**Step 2: 创建 API 路由**

```python
# backend/src/api/papers.py
from fastapi import APIRouter, Query
from typing import Optional
from src.services.paper_search import search_papers, get_paper, get_paper_citations, get_paper_references

router = APIRouter()

@router.get("/api/papers/search")
async def search_papers_endpoint(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Search for academic papers"""
    results = search_papers(q, limit, offset)
    return {"query": q, "count": len(results), "papers": results}

@router.get("/api/papers/{paper_id}")
async def get_paper_endpoint(paper_id: str):
    """Get paper details by ID"""
    paper = get_paper(paper_id)
    if paper:
        return paper
    return {"error": "Paper not found"}, 404

@router.get("/api/papers/{paper_id}/citations")
async def get_citations_endpoint(
    paper_id: str,
    limit: int = Query(10, ge=1, le=1000)
):
    """Get papers that cite this paper"""
    citations = get_paper_citations(paper_id, limit)
    return {"paper_id": paper_id, "count": len(citations), "citations": citations}

@router.get("/api/papers/{paper_id}/references")
async def get_references_endpoint(
    paper_id: str,
    limit: int = Query(10, ge=1, le=1000)
):
    """Get papers referenced by this paper"""
    references = get_paper_references(paper_id, limit)
    return {"paper_id": paper_id, "count": len(references), "references": references}
```

**Step 3: 注册路由**

```python
# backend/src/api/__init__.py
from . import papers
# 添加 router
app.include_router(papers.router)
```

**Step 4: 测试 API**

```bash
curl "http://localhost:9000/api/papers/search?q=transformer+attention"
```

Expected:
```json
{
  "query": "transformer attention",
  "count": 10,
  "papers": [
    {
      "title": "Attention Is All You Need",
      "authors": ["Ashish Vaswani", ...],
      "year": 2017,
      "citationCount": 90000,
      "url": "https://..."
    }
  ]
}
```

---

### Task 2: 创建论文搜索 Skill

**Files:**
- Create: `.claude/skills/paper_search/SKILL.md`
- Create: `.claude/skills/paper_search/paper_search.py` (可选辅助脚本)

**Step 1: 创建 SKILL.md**

```markdown
# Paper Search Skill

## Trigger
User asks for:
- research papers
- academic literature
- citations
- "find papers on X"

## Tools

### search_papers(query: string, limit?: number)
Search Semantic Scholar for academic papers.

**Example:**
```
search_papers("transformer architecture", limit=5)
```

### get_paper(paperId: string)
Get detailed information about a specific paper.

### get_citations(paperId: string, limit?: number)
Find papers that cite a given paper.

### get_references(paperId: string, limit?: number)
Find papers referenced by a given paper.

## Output Format

Always output results in markdown with:
- Paper title (link)
- Authors
- Year
- Citation count
- Abstract (truncated to 200 chars)

## Example Response

### Found 3 papers on "neural network pruning"

1. **[Learning Both Weights and Connections for Efficient Neural Networks](https://...)**
   - Authors: Song Han, Jeff Pool, John Tran, William Dally
   - Year: 2015 | Citations: 5000+

  摘要: We present a method to reduce network complexity...

2. **[The Lottery Ticket Hypothesis: Finding Sparse, Trainable Neural Networks](https://...)**
   - Authors: Jonathan Frankle, Michael Carbin
   - Year: 2019 | Citations: 10000+

  摘要: We explore the lottery ticket hypothesis...
```

---

### Task 3: 实现 PDF 阅读能力

**Files:**
- Create: `backend/src/services/pdf_reader.py`
- Create: `backend/src/api/pdf.py`
- Test: API 端点

**Step 1: 安装依赖**

```bash
pip install PyMuPDF
```

**Step 2: 创建 pdf_reader.py**

```python
# backend/src/services/pdf_reader.py
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

        doc = fitz.open(path)
        pages = []

        for i in range(min(len(doc), max_pages)):
            page = doc[i]
            text = page.get_text()
            pages.append({
                "page": i + 1,
                "text": text
            })

        doc.close()

        return {
            "path": path,
            "total_pages": len(doc),
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

        doc = fitz.open(path)
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

        doc.close()
        return results
    except Exception as e:
        logger.error(f"PDF search error: {e}")
        return []

def extract_pdf_metadata(path: str) -> Dict:
    """Extract PDF metadata"""
    try:
        doc = fitz.open(path)
        metadata = doc.metadata
        doc.close()
        return {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "subject": metadata.get("subject", ""),
            "pages": len(doc)
        }
    except Exception as e:
        return {"error": str(e)}
```

**Step 3: 创建 API 路由**

```python
# backend/src/api/pdf.py
from fastapi import APIRouter, Query, Body
from pydantic import BaseModel
from src.services.pdf_reader import read_pdf, search_pdf, extract_pdf_metadata

router = APIRouter()

class PDFReadRequest(BaseModel):
    path: str
    max_pages: int = 50

class PDFSearchRequest(BaseModel):
    path: str
    query: str

@router.post("/api/pdf/read")
async def read_pdf_endpoint(request: PDFReadRequest):
    """Read PDF and extract text"""
    return read_pdf(request.path, request.max_pages)

@router.post("/api/pdf/search")
async def search_pdf_endpoint(request: PDFSearchRequest):
    """Search for query in PDF"""
    return search_pdf(request.path, request.query)

@router.get("/api/pdf/metadata")
async def metadata_endpoint(path: str = Query(...)):
    """Get PDF metadata"""
    return extract_pdf_metadata(path)
```

**Step 4: 测试 API**

```bash
# Read PDF
curl -X POST http://localhost:9000/api/pdf/read \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/paper.pdf"}'

# Search in PDF
curl -X POST http://localhost:9000/api/pdf/search \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/paper.pdf", "query": "attention"}'
```

---

### Task 4: 创建 PDF Reader Skill

**Files:**
- Create: `.claude/skills/pdf_reader/SKILL.md`

**Step 1: 创建 SKILL.md**

```markdown
# PDF Reader Skill

## Trigger
User wants to:
- Read a PDF file
- Search within a PDF
- Extract information from paper

## Tools

### read_pdf(path: string, maxPages?: number)
Extract text from PDF file.

**Example:**
```
read_pdf("/research/papers/attention.pdf", maxPages=20)
```

### search_pdf(path: string, query: string)
Search for specific text in PDF.

**Example:**
```
search_pdf("/research/papers/attention.pdf", "attention mechanism")
```

### pdf_metadata(path: string)
Get PDF metadata (title, author, pages).

## Output Format

Return extracted text in structured format with page numbers.

## Notes
- Default max pages: 50
- Supports both absolute and relative paths
- Uses temp_workspace as base directory for relative paths
```

---

### Task 5: 更新 Theorist Agent 搜索策略

**Files:**
- Modify: `.claude/agents/theorist.md`

**Step 1: 添加搜索策略说明**

```markdown
## Search Strategy

### Paper Search (Semantic Scholar API)
Use `/api/papers/search` endpoint when:
- Query asks for research papers
- Topic is scientific/academic
- Needs citation information

### PDF Reading
Use `/api/pdf/read` when:
- User provides a specific PDF file
- Needs to extract content from paper

### Web Search (NOT AVAILABLE)
Web search via MCP is currently unavailable due to API limitations.
Use paper search as alternative for academic queries.
```

---

### Task 6: 端到端测试

**Step 1: 测试论文搜索 API**

```bash
curl "http://localhost:9000/api/papers/search?q=large+language+model&limit=3"
```

**Step 2: 测试获取论文详情**

```bash
# Use paper ID from previous response
curl "http://localhost:9000/api/papers/10.48550/arXiv.1706.03762"
```

**Step 3: 测试 PDF 读取**

```bash
curl -X POST http://localhost:9000/api/pdf/read \
  -d '{"path": "/Users/gtc/Downloads/paper.pdf", "max_pages": 5}'
```

**Step 4: 集成测试 - 通过 Chat 调用**

```bash
curl -X POST http://localhost:9000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Find papers on neural network pruning",
    "agent": "theorist"
  }'
```

Expected: Agent 使用 /api/papers/search 找到相关论文

---

## 执行顺序

1. **Task 1** - 实现 Semantic Scholar API (后端)
2. **Task 2** - 创建 paper_search skill
3. **Task 3** - 实现 PDF 阅读能力
4. **Task 4** - 创建 pdf_reader skill
5. **Task 5** - 更新 Theorist agent
6. **Task 6** - 端到端测试

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| Semantic Scholar 限流 | 添加请求间隔，限制频率 |
| PDF 路径问题 | 使用绝对路径或 temp_workspace |
| API 超时 | 设置 30s timeout |
