---
name: code-generation
description: Use this skill when writing code, implementing algorithms, creating prototypes, or developing software for research
version: 1.0.0
author: MAS System
---

# Code Generation Skill

Systematic approach to writing clean, reproducible, and well-documented research code.

## Trigger Conditions

- User asks to implement an algorithm
- User needs code for data processing
- User wants to create a prototype
- User needs experiment scaffolding
- User asks for code review

## Implementation Workflow

### 1. Requirements Analysis

**Clarify:**
- Input/output specifications
- Performance requirements
- Environment constraints
- Dependencies allowed

**Design:**
- Algorithm/pseudocode
- Data structures
- Function signatures
- Error handling

### 2. Implementation

**Structure:**
```
project/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── utils.py
│   └── config.py
├── tests/
├── data/
├── notebooks/
├── requirements.txt
└── README.md
```

**Code Quality:**
- Clear variable names
- Docstrings for functions
- Type hints where helpful
- Constants at top
- No magic numbers

### 3. Testing

**Unit Tests:**
- Test each function
- Test edge cases
- Test error handling

```python
import pytest

def test_function():
    assert function(input) == expected
    assert function(bad_input) raises Error
```

**Integration Tests:**
- Test components together
- Test data pipeline end-to-end

### 4. Documentation

**README:**
```markdown
# Project Title

Brief description.

## Installation
```bash
pip install -r requirements.txt
```

## Usage
```python
import module
result = module.run(input)
```

## Example
[Run example and show output]

## Testing
```bash
pytest tests/
```
```

**Docstrings:**
```python
def function(param1: str, param2: int) -> dict:
    """
    Short description.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Dictionary with results

    Raises:
        ValueError: If param2 is negative
    """
```

## Output Format

```markdown
## Implementation Plan
- Language: Python
- Key functions: [list]
- Dependencies: [list]

## Code
[Full code with comments]

## Tests
[Test code]

## Documentation
[README content]

## Usage Example
[How to run]
```

## Best Practices

### Reproducibility
- Set random seeds
- Log versions
- Pin dependencies
- Include config files

### Performance
- Profile before optimizing
- Use appropriate data structures
- Consider vectorization
- Cache expensive computations

### Maintainability
- Modular design
- Single responsibility
- DRY principle
- Clear naming

## Common Patterns

### Config Management
```python
from dataclasses import dataclass

@dataclass
class Config:
    param1: str = "default"
    param2: int = 100
```

### Logging
```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

### CLI
```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--input", type=str)
args = parser.parse_args()
```

### Testing Fixtures
```python
import pytest

@pytest.fixture
def sample_data():
    return {"key": "value"}
```
