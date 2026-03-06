---
name: literature-review
description: Use this skill when searching academic papers, conducting literature surveys, finding related work, or summarizing research trends
version: 1.0.0
author: MAS System
---

# Literature Review Skill

Systematic approach to finding, evaluating, and synthesizing academic literature.

## Trigger Conditions

- User asks to search/acquire academic papers
- User wants to summarize research trends
- User needs to find related work
- User wants to conduct a survey of a research topic
- User needs to identify research gaps

## Search Strategy

### Step 1: Define Query
- Identify key concepts
- Create search terms (AND, OR, NOT)
- Consider synonyms

### Step 2: Select Sources
Search in priority order:
1. **arXiv** - Recent preprints, CS/Physics/Math
2. **Google Scholar** - Broad coverage
3. **Semantic Scholar** - Citation analysis
4. **PubMed** - Biomedical
5. **DBLP** - Computer science
6. **IEEE Xplore** - Engineering

### Step 3: Execute Search
- Use advanced search features
- Apply filters (year, citations, venue)
- Get 20-50 initial results

## Selection Criteria

### Inclusion
- Relevance to research question
- Peer-reviewed or credible source
- Sufficient detail to evaluate

### Exclusion
- Not accessible
- Duplicate work
- Low quality (no methodology, no evidence)

### Priority
Prefer:
- Highly cited papers
- Recent papers (last 2-3 years)
- Top venues (NeurIPS, ICML, CVPR, Nature, Science, etc.)
- Papers with official code

## Information Extraction

For each selected paper, extract:
```json
{
  "title": "Paper title",
  "authors": ["Author 1", "Author 2"],
  "year": 2024,
  "venue": "Conference/Journal",
  "citations": 100,
  "url": "link",
  "abstract": "Summary",
  "methodology": "Brief description",
  "key_results": "Main findings",
  "limitations": "Known issues",
  "code": "GitHub link if available"
}
```

## Synthesis Framework

### Thematic Analysis
- Group papers by topic/method
- Identify common approaches
- Note variations

### Gap Identification
- What is NOT addressed?
- What limitations exist?
- What has not been tried?

### Timeline Analysis
- How has the field evolved?
- What are the trends?

## Output Format

```markdown
## Search Summary
- Query: [search terms]
- Sources: [databases searched]
- Results: [papers found/selected]

## Papers Reviewed
[Table with key info]

## Key Themes
### Theme 1
[Description and papers]

### Theme 2
[Description and papers]

## Research Gaps
1. [Gap 1]
2. [Gap 2]

## Future Directions
1. [Direction 1]
2. [Direction 2]

## References
[Full citations]
```

## Tips

- Start broad, then refine
- Check reference lists of key papers
- Look for survey papers on topic
- Use citation graphs (Semantic Scholar)
- Track your search process for reproducibility
