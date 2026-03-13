---
name: data-analysis
description: Use this skill when analyzing data, performing statistical tests, creating visualizations, or extracting insights from datasets
version: 1.0.0
author: MAS System
---

# Data Analysis Skill

Systematic approach to analyzing research data and generating valid insights.

## Trigger Conditions

- User provides dataset for analysis
- User asks for statistical testing
- User needs visualizations
- User wants pattern detection
- User needs insights from data

## Analysis Pipeline

### 1. Data Understanding

**Examine structure:**
- Dimensions (rows, columns)
- Data types (numeric, categorical, text)
- Missing values
- Sample characteristics

**Initial exploration:**
- Summary statistics
- Distribution plots
- Correlation matrix

### 2. Data Preparation

**Cleaning:**
- Handle missing values (impute, drop, or flag)
- Detect and handle outliers
- Fix data type issues
- Standardize formats

**Transformation:**
- Scaling/normalization
- Encoding categorical variables
- Feature engineering
- Dimensionality reduction if needed

### 3. Analysis

**Descriptive:**
- Mean, median, mode
- Standard deviation, variance
- Percentiles
- Frequency counts

**Inferential:**
Choose appropriate test based on:
- Variable types (continuous/categorical)
- Number of groups (1, 2, >2)
- Paired/independent
- Assumptions (normality, homogeneity)

| Situation | Test |
|-----------|------|
| 2 groups, continuous, normal | t-test |
| 2 groups, continuous, non-normal | Mann-Whitney U |
| >2 groups, continuous, normal | ANOVA |
| >2 groups, continuous, non-normal | Kruskal-Wallis |
| Categorical variables | Chi-square |
| Continuous + categorical | Regression |
| Pre/post measurement | Paired t-test |

**Effect Sizes:**
- Cohen's d for t-tests
- Eta-squared for ANOVA
- Correlation coefficients
- Odds ratios

### 4. Visualization

**Choose appropriate chart:**

| Data | Chart Type |
|------|------------|
| Distribution | Histogram, Box plot |
| Comparison | Bar chart, Box plot |
| Relationship | Scatter plot |
| Proportion | Pie chart, Stacked bar |
| Time series | Line chart |
| Correlation | Heatmap |

**Principles:**
- Show data, not just summaries
- Use appropriate scales
- Include clear labels
- Consider accessibility

### 5. Interpretation

**Connect to hypothesis:**
- What do results mean?
- Do they support/refute hypothesis?
- Effect size interpretation

**Limitations:**
- Sample size
- Generalizability
- Confounds
- Assumptions met?

## Output Format

```markdown
## Data Overview
- Source: [where data came from]
- N: [sample size]
- Variables: [list]
- Missing: [%]

## Descriptive Statistics
[Summary statistics table]
[Key plots]

## Analysis Results
### Primary Analysis
[Test used, results, effect size]

### Secondary Analyses
[Additional findings]

## Visualizations
[Generated charts]

## Interpretation
[What results mean]

## Limitations
[Constraints]

## Recommendations
[Next steps]
```

## Python Libraries

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import statsmodels.api as sm
```

## Statistical Guidelines

1. Report all tests with full statistics
2. Correct for multiple comparisons
3. Always report effect sizes
4. Use confidence intervals
5. Be transparent about exclusions
