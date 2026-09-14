"""Lint CSS colour literals for the mistakes that are easy to make by hand."""

from .linter import Finding, lint_text

__all__ = ["Finding", "lint_text"]
__version__ = "0.1.0"
