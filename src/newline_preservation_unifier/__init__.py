"""Newline Preservation Unifier package.

Re-exports the public API from :mod:`newline_preservation_unifier.core`.
"""

from .core import NewlineUnifier, LineEnding, UnificationResult

__all__ = ["NewlineUnifier", "LineEnding", "UnificationResult"]
