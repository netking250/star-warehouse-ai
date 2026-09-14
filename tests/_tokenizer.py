"""Deterministic tokenizer doubles for hermetic tests."""


class DeterministicTokenEncoder:
    """Approximate token counts without loading external tokenizer assets."""

    def encode(self, text: str) -> list[int]:
        """Return stable synthetic token identifiers at four characters per token."""
        token_count = (len(text) + 3) // 4
        return list(range(token_count))
