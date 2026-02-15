"""Offline token counting using Xenova/claude-tokenizer for difficulty scoring.

Uses the transformers library with GPT2TokenizerFast to load the
Xenova/claude-tokenizer from Hugging Face for local, deterministic
token counting. No API credentials required.

When transformers is not installed, falls back to a character-based
approximation (num_chars / 3.5) for containerless environments.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from transformers import GPT2TokenizerFast
    _TRANSFORMERS_AVAILABLE = True
except ImportError:
    _TRANSFORMERS_AVAILABLE = False


class TokenCounter:
    """Count tokens using offline Xenova/claude-tokenizer for difficulty scoring."""

    DEFAULT_NORMALIZE_CAP = 100000

    def __init__(self, config: dict | None = None):
        """
        Initialize the token counter.

        Args:
            config: Configuration dict that may contain:
                - token_counting.enabled: Whether to enable counting
                - token_counting.normalize_cap: Max tokens for 1.0 score
        """
        self._config = config or {}
        self._tokenizer = None
        self._use_char_fallback = False
        self._enabled = self._initialize()

    def _initialize(self) -> bool:
        """Initialize the tokenizer from Hugging Face, or fall back to char-based."""
        tc_config = self._config.get("token_counting", {})
        if tc_config.get("enabled") is False:
            return False

        if _TRANSFORMERS_AVAILABLE:
            try:
                self._tokenizer = GPT2TokenizerFast.from_pretrained(
                    "Xenova/claude-tokenizer"
                )
                logger.info("Token counting enabled via Xenova/claude-tokenizer")
                return True
            except Exception as e:
                logger.warning(f"Tokenizer initialization failed: {e}")

        # Fall back to character-based estimation
        self._use_char_fallback = True
        logger.info("Token counting enabled via char-based estimate (no transformers)")
        return True

    def is_enabled(self) -> bool:
        """Check if token counting is enabled."""
        return self._enabled

    @property
    def using_char_fallback(self) -> bool:
        """Check if using character-based fallback instead of real tokenizer."""
        return self._use_char_fallback

    @property
    def normalize_cap(self) -> int:
        """Get the normalization cap for token counts."""
        return self._config.get("token_counting", {}).get(
            "normalize_cap", self.DEFAULT_NORMALIZE_CAP
        )

    def count_tokens(self, text: str | None) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Token count, or 0 on error/disabled/empty
        """
        if not self._enabled or not text:
            return 0
        if self._use_char_fallback:
            return int(len(text) / 3.5)
        try:
            return len(self._tokenizer.encode(text))
        except Exception as e:
            logger.warning(f"Token counting failed: {e}")
            return 0

    def normalize(self, token_count: int) -> float:
        """Normalize token count to 0.0-1.0 score.

        Args:
            token_count: Raw token count

        Returns:
            Normalized score between 0.0 and 1.0
        """
        if token_count <= 0:
            return 0.0
        return min(1.0, token_count / self.normalize_cap)
