"""Offline token counting using Xenova/claude-tokenizer for difficulty scoring.

Uses the transformers library with GPT2TokenizerFast to load the
Xenova/claude-tokenizer from Hugging Face for local, deterministic
token counting. No API credentials required.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


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
        self._enabled = self._initialize()

    def _initialize(self) -> bool:
        """Initialize the tokenizer from Hugging Face."""
        tc_config = self._config.get("token_counting", {})
        if tc_config.get("enabled") is False:
            return False

        try:
            from transformers import GPT2TokenizerFast

            self._tokenizer = GPT2TokenizerFast.from_pretrained(
                "Xenova/claude-tokenizer"
            )
            logger.info("Token counting enabled via Xenova/claude-tokenizer")
            return True
        except ImportError:
            logger.warning("transformers package not installed")
            return False
        except Exception as e:
            logger.warning(f"Tokenizer initialization failed: {e}")
            return False

    def is_enabled(self) -> bool:
        """Check if token counting is enabled."""
        return self._enabled

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
