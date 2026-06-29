"""Storage layer for plantsim-mcp.

The :class:`~plantsim_mcp.storage.base.Index` abstract base class defines
the seam between indexers/tools and the underlying store. The v0.1
implementation is :class:`~plantsim_mcp.storage.sqlite.SQLiteFTSIndex`;
a vector-store implementation is planned for v0.2.
"""

from .base import Doc, Hit, Index

__all__ = ["Doc", "Hit", "Index"]
