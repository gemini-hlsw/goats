"""Validators shared by GOATS forms."""

__all__ = ["MaxWordsValidator"]

from django.core.validators import BaseValidator


class MaxWordsValidator(BaseValidator):
    """Reject text with more than ``limit_value`` words.

    Parameters
    ----------
    limit_value : int
        The most words allowed. Words are runs of non-whitespace.
    """

    message = (
        "Ensure this value has at most %(limit_value)d words (it has %(show_value)d)."
    )
    code = "max_words"

    def compare(self, a: int, b: int) -> bool:
        return a > b

    def clean(self, x: str) -> int:
        return len(x.split())
