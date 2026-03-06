---
name: scientific-writing
description: Use this skill when writing research papers, reports, documentation, or any scientific content that requires clear and precise communication
version: 1.0.0
author: MAS System
---

# Scientific Writing Skill

Systematic approach to producing clear, rigorous, and well-structured scientific documents.

## Trigger Conditions

- User asks to write a paper
- User needs a research report
- User wants documentation
- User needs to revise text
- User asks for writing feedback

## Writing Process

### 1. Planning

**Determine:**
- Document type (paper, report, blog)
- Target audience
- Target venue (journal, conference)
- Length requirements
- Key message

**Outline:**
```
[Document]
├── Abstract
├── Introduction
│   ├── Background
│   ├── Gap
│   └── Contribution
├── Methods
├── Results
├── Discussion
└── References
```

### 2. Drafting

**Approach:**
1. Start with figures/tables (for papers)
2. Write Methods (most concrete)
3. Write Results (what we found)
4. Write Introduction (context)
5. Write Discussion (interpret)
6. Write Abstract last

**Principles:**
- One idea per paragraph
- Topic sentence first
- Evidence supports claims
- Connect paragraphs

### 3. Revision

**Content:**
- Logical flow
- All claims supported
- No redundant sections
- Gaps addressed

**Style:**
- Active voice
- Past tense for completed work
- Precise language
- Defined acronyms

### 4. Polishing

**Check:**
- Citations complete
- Formatting consistent
- Grammar correct
- Figures clear

## Section Guidelines

### Abstract (200-300 words)
- Context (1-2 sentences)
- Gap (1 sentence)
- Approach (1-2 sentences)
- Results (1-2 sentences)
- Implications (1 sentence)

### Introduction
**Background:** What is known?
**Gap:** What is unknown?
**Contribution:** What do we add?

### Methods
- Sufficient detail to reproduce
- Organized logically
- Cite established methods
- Describe modifications

### Results
- Objective reporting
- Link to figures/tables
- Follows experimental order
- Primary then secondary

### Discussion
- Interpret findings
- Compare to prior work
- Acknowledge limitations
- Future directions

## Output Format

```markdown
## Document Spec
- Type: [Paper/Report/etc.]
- Audience: [Who]
- Venue: [Target]
- Length: [Words]

## Outline
[Section structure]

## Draft
[Full content]

## Notes
[Questions or clarifications needed]
```

## Writing Tips

### Clarity
- Use simple words
- Short sentences
- Define technical terms
- Examples help

### Precision
- Specific numbers
- Hedging where appropriate
- Avoid vague claims

### Flow
- Topic sentences
- Transitions
- Parallel structure
- Logical progression

### Citations
- Cite sources for claims
- Recent + classic papers
- Multiple perspectives

## LaTeX Templates

### Basic Structure
```latex
\documentclass{article}
\usepackage{amsmath}
\usepackage{graphicx}

\begin{document}
\title{Title}
\author{Author}
\date{\today}

\begin{abstract}
Abstract text
\end{abstract}

\section{Introduction}
\section{Methods}
\section{Results}
\section{Discussion}

\bibliographystyle{plain}
\bibliography{references}
\end{document}
```

### Figures
```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=0.8\textwidth]{fig1.png}
\caption{Caption}
\label{fig:example}
\end{figure}
```

### Tables
```latex
\begin{table}[htbp]
\centering
\begin{tabular}{|c|c|}
\hline
A & B \\
\hline
1 & 2 \\
\hline
\end{tabular}
\caption{Caption}
\label{tab:example}
\end{table}
```

## Checklist

- [ ] Abstract complete
- [ ] All claims cited
- [ ] Methods reproducible
- [ ] Results clearly presented
- [ ] Discussion interprets findings
- [ ] Limitations acknowledged
- [ ] Format matches venue
- [ ] Proofread
