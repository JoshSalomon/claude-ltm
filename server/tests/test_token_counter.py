"""Unit tests for token_counter.py - Offline Token Counting for Difficulty Scoring.

Test cases from Test Plan (docs/TEST_PLAN_TOKEN_COUNTING.md):
- TC-01 to TC-08: TokenCounter Class
- TC-10 to TC-15: Normalization
- TC-60 to TC-63: Real Tokenizer Tests
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add server directory to path for imports
# tests are at: server/tests/ -> go up one level to server/
_server_path = Path(__file__).parent.parent
sys.path.insert(0, str(_server_path))


# =============================================================================
# TC-01 to TC-08: TokenCounter Class Tests
# =============================================================================


class TestTokenCounterEnabled:
    """Tests for TokenCounter enabled/disabled states."""

    def test_always_enabled_by_default(self):
        """TC-01: TokenCounter is always enabled by default (no credentials needed)."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        assert counter.is_enabled() is True

    def test_disabled_via_config(self):
        """TC-02: Disabled via config returns 0."""
        from token_counter import TokenCounter

        config = {"token_counting": {"enabled": False}}
        counter = TokenCounter(config)
        assert counter.is_enabled() is False
        assert counter.count_tokens("Hello world") == 0


class TestTokenCounterCounting:
    """Tests for token counting behavior."""

    def test_count_returns_integer(self):
        """TC-03: Count returns integer >= 1 for non-empty text."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        result = counter.count_tokens("Hello world")
        assert isinstance(result, int)
        assert result >= 1

    def test_empty_string_returns_zero(self):
        """TC-04: Empty string returns 0."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        assert counter.count_tokens("") == 0

    def test_none_returns_zero(self):
        """TC-05: None returns 0."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        assert counter.count_tokens(None) == 0

    def test_deterministic_counting(self):
        """TC-06: Same input always produces same output."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        text = "The quick brown fox jumps over the lazy dog."
        result1 = counter.count_tokens(text)
        result2 = counter.count_tokens(text)
        assert result1 == result2
        assert result1 > 0

    def test_config_normalize_cap(self):
        """TC-07: Config normalize_cap affects normalization."""
        from token_counter import TokenCounter

        config = {"token_counting": {"normalize_cap": 50000}}
        counter = TokenCounter(config)
        # 50000 tokens with cap of 50000 should give 1.0
        assert counter.normalize(50000) == 1.0
        # 25000 tokens with cap of 50000 should give 0.5
        assert counter.normalize(25000) == 0.5

    def test_tokenizer_error_returns_zero(self):
        """TC-08: Tokenizer error returns 0 and logs warning."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        # Force an error by corrupting the tokenizer
        original_tokenizer = counter._tokenizer
        counter._tokenizer = MagicMock()
        counter._tokenizer.encode.side_effect = Exception("Tokenizer error")

        result = counter.count_tokens("Hello world")
        assert result == 0

        # Restore the tokenizer
        counter._tokenizer = original_tokenizer


# =============================================================================
# TC-10 to TC-15: Normalization Tests
# =============================================================================


class TestTokenNormalization:
    """Tests for token count normalization."""

    def test_half_of_cap(self):
        """TC-10: Half of cap gives 0.5."""
        from token_counter import TokenCounter

        counter = TokenCounter()  # Default cap is 100000
        assert counter.normalize(50000) == 0.5

    def test_at_cap(self):
        """TC-11: At cap gives 1.0."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        assert counter.normalize(100000) == 1.0

    def test_above_cap(self):
        """TC-12: Above cap gives 1.0 (capped)."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        assert counter.normalize(200000) == 1.0

    def test_zero_tokens(self):
        """TC-13: Zero tokens gives 0.0."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        assert counter.normalize(0) == 0.0

    def test_custom_cap(self):
        """TC-14: Custom cap in config works correctly."""
        from token_counter import TokenCounter

        config = {"token_counting": {"normalize_cap": 50000}}
        counter = TokenCounter(config)
        assert counter.normalize(25000) == 0.5

    def test_negative_tokens_normalize(self):
        """TC-15: Negative token count normalizes to 0.0."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        assert counter.normalize(-100) == 0.0


# =============================================================================
# TC-60 to TC-63: Real Tokenizer Tests
# =============================================================================


class TestRealTokenizer:
    """Tests using the real tokenizer (not mocked)."""

    def test_simple_text(self):
        """TC-60: Simple text produces token count > 0."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        assert counter.is_enabled() is True
        result = counter.count_tokens("Hello world")
        assert result > 0

    def test_unicode_text(self):
        """TC-61: Unicode text is tokenized correctly."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        result = counter.count_tokens("中文 emoji 日本語")
        assert result > 0

    def test_long_text(self):
        """TC-62: Long text produces proportionally more tokens."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        short_text = "Hello world"
        long_text = short_text * 100

        short_count = counter.count_tokens(short_text)
        long_count = counter.count_tokens(long_text)

        # Long text should have significantly more tokens
        assert long_count > short_count * 50  # At least 50x more

    def test_whitespace_only(self):
        """TC-63: Whitespace-only text is handled."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        result = counter.count_tokens("   \n\t  ")
        # May return 0 or small number depending on tokenizer
        assert result >= 0


# =============================================================================
# Additional Tests
# =============================================================================


class TestTokenCounterProperties:
    """Tests for TokenCounter properties."""

    def test_default_normalize_cap(self):
        """Default normalize_cap is 100000."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        assert counter.normalize_cap == 100000

    def test_is_enabled_with_none_config(self):
        """TokenCounter works with None config."""
        from token_counter import TokenCounter

        counter = TokenCounter(None)
        assert counter.is_enabled() is True


class TestTokenCounterInitialization:
    """Tests for TokenCounter initialization scenarios."""

    def test_tokenizer_import_error_falls_back_to_char(self):
        """Falls back to char-based estimation when transformers not installed."""
        from token_counter import TokenCounter

        # Create a TokenCounter instance and manually test initialization
        counter = TokenCounter.__new__(TokenCounter)
        counter._config = {}
        counter._tokenizer = None
        counter._use_char_fallback = False

        # Simulate _TRANSFORMERS_AVAILABLE = False
        with patch("token_counter._TRANSFORMERS_AVAILABLE", False):
            result = counter._initialize()
            assert result is True
            assert counter._tokenizer is None
            assert counter._use_char_fallback is True

    def test_tokenizer_load_failure_falls_back_to_char(self):
        """Falls back to char-based estimation when tokenizer cannot load."""
        from token_counter import TokenCounter

        counter = TokenCounter.__new__(TokenCounter)
        counter._config = {}
        counter._tokenizer = None
        counter._use_char_fallback = False

        # Mock the transformers module to raise on from_pretrained
        mock_transformers = MagicMock()
        mock_transformers.GPT2TokenizerFast.from_pretrained.side_effect = Exception(
            "Failed to load tokenizer"
        )

        with patch("token_counter._TRANSFORMERS_AVAILABLE", True):
            with patch("token_counter.GPT2TokenizerFast", mock_transformers.GPT2TokenizerFast):
                result = counter._initialize()
                assert result is True
                assert counter._use_char_fallback is True

    def test_initialization_with_empty_config(self):
        """TokenCounter initializes with empty config."""
        from token_counter import TokenCounter

        counter = TokenCounter({})
        assert counter.is_enabled() is True


class TestTokenCounterEdgeCases:
    """Edge case tests for TokenCounter."""

    def test_very_long_text(self):
        """Handle very long text without crashing."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        # 100KB of text
        long_text = "word " * 20000
        result = counter.count_tokens(long_text)
        assert result > 0

    def test_special_characters(self):
        """Handle special characters."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        text = "Special chars: @#$%^&*(){}[]|\\:\";<>?,./~`"
        result = counter.count_tokens(text)
        assert result > 0

    def test_mixed_content(self):
        """Handle mixed content (code, text, unicode)."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        text = """
        def hello():
            print("Hello, 世界!")
            return 42

        # Comment with emoji ❤️
        """
        result = counter.count_tokens(text)
        assert result > 0

    def test_newlines_and_formatting(self):
        """Handle text with newlines and formatting."""
        from token_counter import TokenCounter

        counter = TokenCounter()
        text = "Line 1\nLine 2\n\nLine 4\t\tTabbed"
        result = counter.count_tokens(text)
        assert result > 0
