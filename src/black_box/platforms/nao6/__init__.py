"""NAO6 (SoftBank Aldebaran) ingestion adapter + humanoid-specific taxonomy."""

from .adapter import NAO6Adapter
from .taxonomy import NAO6_TAXONOMY, NAO6BugClass, by_slug, to_global

__all__ = [
    "NAO6Adapter",
    "NAO6BugClass",
    "NAO6_TAXONOMY",
    "by_slug",
    "to_global",
]
