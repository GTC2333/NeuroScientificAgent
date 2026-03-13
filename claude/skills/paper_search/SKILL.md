---
name: paper-search
description: Search academic papers using Semantic Scholar API for research literature queries
version: 1.0.0
author: MAS System
---

# Paper Search Skill

## Trigger
User asks for:
- research papers
- academic literature
- citations
- "find papers on X"
- "search for papers about Y"

## Tools

### search_papers(query: string, limit?: number)
Search Semantic Scholar for academic papers via API.

**API Endpoint:** `GET /api/papers/search?q={query}&limit={limit}`

**Example:**
```
search_papers("transformer architecture", limit=5)
```

### get_paper(paperId: string)
Get detailed information about a specific paper.

**API Endpoint:** `GET /api/papers/{paperId}`

**Example:**
```
get_paper("10.48550/arXiv.1706.03762")
```

### get_citations(paperId: string, limit?: number)
Find papers that cite a given paper.

**API Endpoint:** `GET /api/papers/{paperId}/citations?limit={limit}`

**Example:**
```
get_citations("10.48550/arXiv.1706.03762", limit=10)
```

### get_references(paperId: string, limit?: number)
Find papers referenced by a given paper.

**API Endpoint:** `GET /api/papers/{paperId}/references?limit={limit}`

**Example:**
```
get_references("10.48550/arXiv.1706.03762", limit=10)
```

## Output Format

Always output results in markdown with:
- Paper title (as link if URL available)
- Authors (comma separated)
- Year
- Citation count (if available)
- Abstract (truncated to 200 chars if too long)

## Example Response

### Found 3 papers on "neural network pruning"

1. **[Learning Both Weights and Connections for Efficient Neural Networks](https://proceedings.neurips.cc/paper/2015/hash/ae0eb3eedcfdbed7c5e94bb6d3b05c4d-Abstract.html)**
   - Authors: Song Han, Jeff Pool, John Tran, William Dally
   - Year: 2015 | Citations: 5000+

   摘要: We present a method to reduce network complexity...

2. **[The Lottery Ticket Hypothesis: Finding Sparse, Trainable Neural Networks](https://arxiv.org/abs/1803.03635)**
   - Authors: Jonathan Frankle, Michael Carbin
   - Year: 2019 | Citations: 10000+

   摘要: We explore the lottery ticket hypothesis...

## Notes
- Semantic Scholar API may rate limit without an API key
- Use paper search for academic queries
- For non-academic queries, explain that web search is unavailable
