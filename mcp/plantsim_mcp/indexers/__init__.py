"""Indexers that populate the storage layer.

Each indexer is a callable that turns one kind of source (markdown tree,
``.psfm`` folder, ...) into :class:`~plantsim_mcp.storage.base.Doc`
records and writes them through an :class:`Index`.
"""
