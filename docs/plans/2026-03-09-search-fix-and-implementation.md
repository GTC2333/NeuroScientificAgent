# 搜索功能修复与实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** 修复 MCP 超时问题，实现完整的科研搜索能力（论文搜索 + 网络搜索 + PDF 阅读）

**Architecture:** 三层能力架构 - Paper Search (Semantic Scholar) / Web Search (Tavily) / PDF Reader (PyMuPDF)

**Tech Stack:**
- Claude Code CLI + MCP Protocol
- Semantic Scholar API (论文搜索)
- Tavily MCP (网络搜索)
- PyMuPDF (PDF 解析)

---

## 当前问题分析

### 问题 1: MCP 超时
- **现象**: 启用 MCP 配置后 CLI 超时 (120s)
- **根因**: 使用第三方 API (minimax) 而非官方 Anthropic API
- **证据**: `settings.local.json` 中配置了 `ANTHROPIC_BASE_URL: https://api.minimaxi.com/anthropic`

### 问题 2: 能力不完整
- 只有 MCP 网络搜索配置
- 缺少论文搜索 (Semantic Scholar)
- 缺少 PDF 阅读能力

---

## 任务列表

### Task 1: 修复 MCP 超时问题

**Files:**
- Modify: `.claude/settings.local.json`
- Test: `backend/src/services/claude_code.py`

**Step 1: 备份当前配置**

```bash
cp .claude/settings.local.json .claude/settings.local.json.backup
```

**Step 2: 修改 settings.local.json 使用官方 API**

方案 A - 使用官方 Anthropic API (推荐):
```json
{
  "env": {
    "ANTHROPIC_API_KEY": "sk-ant-your-key-here"
  }
}
```

方案 B - 保留第三方 API，但禁用 MCP:
```yaml
# local.yaml
mcp:
  enabled: false
```

**Step 3: 测试 CLI 是否正常**

```bash
claude -p --print "Say hi" --model sonnet --dangerously-skip-permissions
```

Expected: 返回 "hi" (5秒内)

**Step 4: 测试 MCP 是否工作**

```bash
claude -p --print "Search for transformer architecture" --model sonnet --mcp-config temp_workspace/mcp_config.json --dangerously-skip-permissions
```

Expected: 返回搜索结果

---

### Task 2: 实现 Semantic Scholar 论文搜索

**Files:**
- Create: `backend/src/services/paper_search.py`
- Modify: `backend/src/api/chat.py` (添加路由)
- Create: `.claude/skills/paper_search/SKILL.md`

**Step 1: 创建 paper_search.py**

```python
# backend/src/services/paper_search.py
import requests
from typing import List, Dict, Optional

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"

def search_papers(query: str, limit: int = 10) -> List[Dict]:
    """Search papers via Semantic Scholar API"""
    url = f"{SEMANTIC_SCHOLAR_API}/paper/search"
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,abstract,citationCount,url"
    }
    response = requests.get(url, params=params, timeout=30)
    return response.json().get("data", [])

def get_paper(paper_id: str) -> Dict:
    """Get paper details by ID"""
    url = f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}"
    params = {"fields": "title,authors,year,abstract,citationCount,references,url"}
    response = requests.get(url, timeout=30)
    return response.json()
```

**Step 2: 创建 API 路由**

```python
# backend/src/api/papers.py
@router.get("/api/papers/search")
async def search_papers(q: str, limit: int = 10):
    from src.services.paper_search import search_papers
    return search_papers(q, limit)
```

**Step 3: 创建 paper_search skill**

```markdown
# Paper Search Skill

## Trigger
- Query contains "paper", "research", "paper search"
- Topic is scientific/academic

## Tools
- `search_papers(query)` - Semantic Scholar 搜索
- `get_paper_metadata(paper_id)` - 获取论文详情
```

---

### Task 3: 实现网络搜索能力 (Tavily)

**Files:**
- Modify: `backend/src/services/claude_code.py`
- Modify: `local.yaml`
- Test: 搜索功能

**Step 1: 确认 local.yaml MCP 配置**

```yaml
# local.yaml
mcp:
  enabled: true
  servers:
    - type: tavily
      name: tavily
```

**Step 2: 测试 MCP 搜索**

```bash
curl -X POST http://localhost:9000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for attention mechanism", "agent": "theorist"}'
```

Expected: 返回 Tavily 搜索结果

---

### Task 4: 实现 PDF 阅读能力

**Files:**
- Create: `backend/src/services/pdf_reader.py`
- Modify: `backend/src/api/chat.py`
- Create: `.claude/skills/pdf_reader/SKILL.md`

**Step 1: 安装依赖**

```bash
pip install PyMuPDF
```

**Step 2: 创建 pdf_reader.py**

```python
# backend/src/services/pdf_reader.py
import fitz  # PyMuPDF
from typing import Dict, List

def read_pdf(path: str, max_pages: int = 50) -> str:
    """Extract text from PDF"""
    doc = fitz.open(path)
    text = ""
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        text += page.get_text()
    return text

def search_pdf(path: str, query: str) -> List[Dict]:
    """Search for query in PDF"""
    doc = fitz.open(path)
    results = []
    for page_num, page in enumerate(doc):
        text = page.get_text()
        if query.lower() in text.lower():
            results.append({
                "page": page_num + 1,
                "context": text[:500]
            })
    return results
```

**Step 3: 创建 pdf_reader skill**

```markdown
# PDF Reader Skill

## Trigger
- User wants to read/analyze PDF
- Query contains "pdf", "read paper", "extract"

## Tools
- `read_pdf(path)` - 提取 PDF 文本
- `search_pdf(path, query)` - PDF 内搜索
```

---

### Task 5: 创建搜索路由策略

**Files:**
- Modify: `.claude/agents/theorist.md`

**Step 1: 更新 Theorist agent prompt**

```markdown
## Search Strategy

Use paper_search when:
- query asks for research papers
- topic is scientific/academic
- needs citation information

Use web_search when:
- general knowledge
- news or definitions
- recent events

Use pdf_reader when:
- analyzing specific paper
- extracting sections/figures
```

---

### Task 6: 端到端测试

**Step 1: 测试论文搜索**

```bash
curl "http://localhost:9000/api/papers/search?q=transformer"
```

Expected: 返回论文列表

**Step 2: 测试网络搜索**

```bash
curl -X POST http://localhost:9000/api/chat \
  -d '{"message": "What is attention mechanism?", "agent": "theorist"}'
```

Expected: Agent 调用 Tavily 搜索并返回结果

**Step 3: 测试 PDF 读取**

```bash
curl -X POST http://localhost:9000/api/pdf/read \
  -d '{"path": "paper.pdf"}'
```

Expected: 返回 PDF 文本内容

---

## 执行顺序

1. **Task 1** (修复 MCP) - 阻塞其他任务
2. **Task 3** (Tavily 搜索) - 依赖 Task 1
3. **Task 2** (论文搜索) - 独立
4. **Task 4** (PDF 阅读) - 独立
5. **Task 5** (搜索路由) - 依赖 Task 2, 3, 4
6. **Task 6** (端到端测试) - 最后

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 官方 API 成本 | 使用免费 tier 或严格控制调用 |
| MCP 仍然超时 | 增加超时时间到 300s |
| Semantic Scholar 限流 | 添加缓存和请求间隔 |
