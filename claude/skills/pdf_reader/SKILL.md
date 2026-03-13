# PDF Reader Skill

## Trigger
User wants to:
- Read a PDF file
- Search within a PDF
- Extract information from paper
- "read this PDF"
- "extract text from X.pdf"
- "search in paper"

## Tools

### read_pdf(path: string, maxPages?: number)
Extract text from PDF file.

**API Endpoint:** `POST /api/pdf/read`
```json
{"path": "/path/to/file.pdf", "max_pages": 20}
```

**Example:**
```
read_pdf("/research/papers/attention.pdf", maxPages=20)
```

### search_pdf(path: string, query: string)
Search for specific text in PDF.

**API Endpoint:** `POST /api/pdf/search`
```json
{"path": "/path/to/file.pdf", "query": "attention mechanism"}
```

**Example:**
```
search_pdf("/research/papers/attention.pdf", "attention mechanism")
```

### pdf_metadata(path: string)
Get PDF metadata (title, author, pages).

**API Endpoint:** `GET /api/pdf/metadata?path=/path/to/file.pdf`

**Example:**
```
pdf_metadata("/research/papers/attention.pdf")
```

## Path Rules

- Use absolute paths
- Allowed directories:
  - `temp_workspace/`
  - `~/Downloads/`
  - Project root
- Only `.pdf` files supported

## Output Format

### read_pdf response
Return structured output:
```
## PDF Content: filename.pdf (Page X of Y)

### Page 1
[Extracted text...]

### Page 2
[Extracted text...]
```

### search_pdf response
Return matches with context:
```
## Search Results for "query" in filename.pdf

### Page 5
...context around match...

### Page 8
...context around match...
```

## Notes
- Default max pages: 50
- Maximum file size: 50MB
- Supports both absolute and relative paths (resolved against allowed directories)
