"""Compatibility facade for legacy read imports.

New code should prefer domain modules (`history_store_packets`, `history_store_chat`,
`history_store_connections`, `history_store_nodes`), but this module is retained to
avoid import churn for existing callers.
"""

from .history_store_chat import load_recent_chat
from .history_store_connections import load_connections
from .history_store_nodes import (
    load_node_capabilities,
    load_node_history,
    load_node_saved_counts,
    load_online_activity,
)
from .history_store_packets import load_recent_packets
from .history_store_summary import load_summary_metrics

__all__ = [
    "load_recent_packets",
    "load_recent_chat",
    "load_connections",
    "load_node_history",
    "load_online_activity",
    "load_summary_metrics",
    "load_node_saved_counts",
    "load_node_capabilities",
]
