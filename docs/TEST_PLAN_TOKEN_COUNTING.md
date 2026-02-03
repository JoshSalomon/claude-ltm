# Test Plan: Offline Token Counting for Difficulty Scoring

## 1. Overview

- **Feature:** Offline Token Counting
- **Scope:** TokenCounter module, priority calculation, hook integration
- **Approach:** Test-Driven Development (TDD)

### Feature Summary

This feature provides offline token counting using the [Xenova/claude-tokenizer](https://huggingface.co/Xenova/claude-tokenizer) to improve difficulty scoring accuracy. Higher token usage indicates more complex tasks, which should prioritize memories from those sessions.

**Current formula:** `difficulty = (failure_rate * 0.5) + (tool_count * 0.3) + (compaction * 0.2)`

**New formula:** `difficulty = (failure_rate * 0.25) + (tool_count * 0.15) + (tokens * 0.35) + (compaction * 0.25)`

### Implementation

The TokenCounter uses the `transformers` library with `GPT2TokenizerFast.from_pretrained('Xenova/claude-tokenizer')` for local, deterministic token counting. No API credentials are required - the tokenizer is always enabled unless explicitly disabled via config.

---

## 2. Test Categories

### 2.1 Unit Tests - TokenCounter Class

| ID | Test Case | Input | Expected Output | Priority |
|----|-----------|-------|-----------------|----------|
| TC-01 | Always enabled | Default config | is_enabled() -> True | High |
| TC-02 | Disabled via config | enabled=false | count_tokens() -> 0 | High |
| TC-03 | Count returns integer | "Hello world" | int >= 1 | High |
| TC-04 | Empty string handling | "" | 0 | High |
| TC-05 | None handling | None | 0 | High |
| TC-06 | Deterministic counting | Same input twice | Same output | High |
| TC-07 | Config normalize_cap | cap=50000 | normalize(50k) -> 1.0 | Medium |
| TC-08 | Tokenizer error handling | Mock exception | 0, logs warning | Medium |

### 2.2 Unit Tests - Normalization

| ID | Test Case | Input | Expected Output | Priority |
|----|-----------|-------|-----------------|----------|
| TC-10 | Half of cap | 50000/100000 | 0.5 | High |
| TC-11 | At cap | 100000/100000 | 1.0 | High |
| TC-12 | Above cap | 200000/100000 | 1.0 (capped) | High |
| TC-13 | Zero tokens | 0 | 0.0 | High |
| TC-14 | Custom cap | 25000/50000 | 0.5 | Medium |
| TC-15 | Negative tokens | -100 | 0.0 | Medium |

### 2.3 Unit Tests - Priority Calculator

| ID | Test Case | Input | Expected Output | Priority |
|----|-----------|-------|-----------------|----------|
| TC-20 | New weights sum | - | 0.25+0.15+0.35+0.25=1.0 | High |
| TC-21 | Token contribution | 100k tokens only | 0.35 | High |
| TC-22 | Backward compat | session_tokens=0 | Uses old formula | High |
| TC-23 | Max difficulty | All factors maxed | 1.0 | High |
| TC-24 | Old formula check | No tokens | 0.5+0.3+0.2 weights | High |

### 2.4 Integration Tests - Hook Handler

| ID | Test Case | Input | Expected Output | Priority |
|----|-----------|-------|-----------------|----------|
| TC-30 | Tokens counted | tool_response text | session_tokens > 0 | High |
| TC-31 | Tokens accumulate | Multiple calls | Sum of counts | High |
| TC-32 | Skip when disabled | enabled=false | session_tokens = 0 | High |
| TC-33 | Handle counter error | Mock failure | Graceful, continues | High |
| TC-34 | Session start notifies | Default | token_counting.enabled=true | High |

### 2.5 Token Reset Tests

| ID | Test Case | Scenario | Expected | Priority |
|----|-----------|----------|----------|----------|
| TC-40 | Tokens reset on store | store_memory called | session_tokens -> 0 | High |
| TC-41 | Tool counts reset on store | store_memory called | tool_failures/successes -> 0 | High |
| TC-42 | Two memories different difficulty | Debug(50k) -> store, Refactor(30k) -> store | Different difficulty values | High |
| TC-43 | No tokens before store | store_memory immediately | difficulty uses old formula | High |
| TC-44 | Accumulation between stores | 3 tool calls -> store | Tokens = sum of 3 calls | High |

### 2.6 Token Management Command Tests

| ID | Test Case | Scenario | Expected | Priority |
|----|-----------|----------|----------|----------|
| TC-50 | Status shows token info | ltm_status after tool calls | session_tokens in response | High |
| TC-51 | Reset tokens tool | reset_tokens called | session_tokens -> 0 | High |
| TC-52 | Reset shows before/after | reset_tokens response | before/after in response | High |
| TC-53 | Reset clears tool counts | reset_tokens called | tool_failures/successes -> 0 | High |

### 2.7 Real Tokenizer Tests

| ID | Test Case | Input | Expected Output | Priority |
|----|-----------|-------|-----------------|----------|
| TC-60 | Simple text | "Hello world" | token count > 0 | High |
| TC-61 | Unicode text | "中文 emoji" | token count > 0 | High |
| TC-62 | Long text | 10000 chars | token count proportional | Medium |
| TC-63 | Whitespace only | "   \n\t  " | token count >= 0 | Medium |

---

## 3. Test Data

### 3.1 Sample Tool Responses

```python
SAMPLE_TOOL_RESPONSES = {
    "short": {"text": "File created successfully."},
    "medium": {"text": "Error: File not found. The path '/src/utils/helper.py' does not exist. Please check the path and try again."},
    "long": {"text": "..." * 1000},  # Long response for token counting
    "empty": {"text": ""},
    "unicode": {"text": "Unicode test: 中文 emoji"},
}
```

### 3.2 Edge Cases

- Empty string: ""
- Very large text: 100k+ characters
- Special characters: Unicode, emoji, control characters
- Whitespace-only text

---

## 4. Pass/Fail Criteria

### 4.1 Blocking Requirements

- All **High** priority tests must pass
- 100% code coverage on new modules (token_counter.py)
- No regressions in existing test suite

### 4.2 Non-Blocking Requirements

- **Medium** priority tests should pass (non-blocking)

### 4.3 Coverage Requirements

Run coverage with:
```bash
pytest server/tests/ --cov=server --cov-fail-under=100 \
  --cov-report=term-missing --ignore=server/tests/test_container_integration.py
```

**Coverage Exclusions** (marked with `# pragma: no cover`):
- HTTP server initialization code
- Lines only reachable with running container
- Main entry points (`if __name__ == "__main__"`)

---

## 5. Dependencies

### 5.1 Python Packages

```
pytest
pytest-asyncio
pytest-mock
pytest-cov
transformers>=4.40.0
```

### 5.2 External Dependencies

- None for token counting (offline tokenizer)
- podman/docker for container tests (optional)

---

## 6. Test Execution

### 6.1 Unit Tests Only

```bash
pytest server/tests/test_token_counter.py -v
pytest server/tests/test_priority.py -v
```

### 6.2 Full Test Suite

```bash
pytest server/tests/ --cov=server --cov-fail-under=100 \
  --ignore=server/tests/test_container_integration.py -v
```

---

## 7. Tokenizer Behavior

The offline tokenizer:
- Is always enabled by default (no credentials needed)
- Can be disabled via `config.token_counting.enabled = false`
- Uses the Xenova/claude-tokenizer from Hugging Face
- Returns deterministic results (same input = same output)
- Handles errors gracefully (returns 0 on failure)

---

## 8. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2026-02-03 | Replace Anthropic API with offline Xenova tokenizer |
| 1.0.0 | 2026-02-03 | Initial test plan for FE-2 Token Counting |

---

*Document maintained as part of the Long-Term Memory system for Claude Code.*
